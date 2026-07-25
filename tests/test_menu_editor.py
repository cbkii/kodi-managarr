import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.menu_entrypoints import (
    _edit_flattening, _edit_group_order, _edit_numeric, _edit_visibility,
    render_preview,
)
from arr_manager.menu_layout import attach_menu_layout, rank_for
from arr_manager.registry import get_action_by_id


class Entrypoints:
    @staticmethod
    def _s(addon, string_id, fallback):
        del addon, string_id
        return fallback


class Addon:
    def __init__(self, **values):
        self.values = dict(values)

    def getSetting(self, key):
        return self.values.get(key, "")

    def setSetting(self, key, value):
        self.values[key] = value


class Settings:
    menu_mode = "1"
    hidden_actions = []
    action_order = []


class UI:
    def __init__(self, choices=(), multiselects=(), numbers=()):
        self.choices = list(choices)
        self.multiselects = list(multiselects)
        self.numbers = list(numbers)
        self.notifications = []

    def select(self, heading, options):
        del heading, options
        return self.choices.pop(0)

    def multiselect(self, heading, options, preselect):
        del heading, options, preselect
        return self.multiselects.pop(0)

    def numeric_input(self, heading, default=""):
        del heading, default
        return self.numbers.pop(0)

    def notification(self, message, **kwargs):
        self.notifications.append((message, kwargs))


class MenuEditorTests(unittest.TestCase):
    def settings(self):
        addon = Addon(menu_layout_version="1")
        return addon, attach_menu_layout(Settings(), addon)

    def test_batch_visibility_disables_unselected_items_and_normalises_enabled_order(self):
        addon, settings = self.settings()
        visible_indexes = [index for index in range(12) if index != 1]
        ui = UI(choices=[0], multiselects=[visible_indexes])

        _edit_visibility(Entrypoints, addon, settings, ui)

        self.assertEqual(settings.menu_ranks["status"], 0)
        enabled = [
            settings.menu_ranks[action_id]
            for action_id in (
                "request_search", "search_now", "interactive_search", "monitoring", "queue",
                "dashboard", "find_subtitles", "retention", "delete_exclude", "delete_replace", "tools",
            )
        ]
        self.assertEqual(enabled, list(range(10, 120, 10)))

    def test_one_step_move_to_top_reorders_without_repeated_up_actions(self):
        addon, settings = self.settings()
        ui = UI(choices=[5, 0])

        _edit_group_order(Entrypoints, addon, settings, ui, "root")

        self.assertEqual(settings.menu_ranks["queue"], 10)
        self.assertEqual(settings.menu_ranks["request_search"], 20)
        self.assertEqual(settings.menu_ranks["status"], 30)

    def test_direct_numeric_zero_disables_selected_action(self):
        addon, settings = self.settings()
        ui = UI(numbers=["0"])

        _edit_numeric(
            Entrypoints, addon, settings, ui,
            group="root", action=get_action_by_id("status"),
        )

        self.assertEqual(settings.menu_ranks["status"], 0)

    def test_invalid_numeric_input_keeps_current_rank_and_reports_error(self):
        addon, settings = self.settings()
        before = rank_for(settings, get_action_by_id("status"))
        ui = UI(numbers=["1000"])

        _edit_numeric(
            Entrypoints, addon, settings, ui,
            group="root", action=get_action_by_id("status"),
        )

        self.assertEqual(settings.menu_ranks["status"], before)
        self.assertTrue(ui.notifications)
        self.assertTrue(ui.notifications[-1][1].get("error"))

    def test_flattening_is_selected_in_one_batch(self):
        addon, settings = self.settings()
        ui = UI(multiselects=[[0, 2]])

        _edit_flattening(Entrypoints, addon, settings, ui)

        self.assertEqual(settings.flatten_groups, {"monitoring", "retention"})

    def test_preview_shows_flattened_namespace_and_duplicate_warning(self):
        addon, settings = self.settings()
        settings.flatten_groups.add("monitoring")
        settings.menu_ranks["status"] = 30
        settings.menu_ranks["search_now"] = 30

        preview = render_preview(Entrypoints, addon, settings)

        self.assertIn("050/010  Monitoring › Monitor", preview)
        self.assertIn("Duplicate Main menu position 30", preview)
        self.assertIn("Registry default and action ID break the tie", preview)

    def test_simple_mode_preview_omits_mode_hidden_submenus(self):
        addon, settings = self.settings()
        settings.menu_mode = "0"

        preview = render_preview(Entrypoints, addon, settings)

        self.assertNotIn("\nMONITORING\n", preview)
        self.assertNotIn("\nDOWNLOAD QUEUE\n", preview)
        self.assertNotIn("\nRETENTION\n", preview)


if __name__ == "__main__":
    unittest.main()
