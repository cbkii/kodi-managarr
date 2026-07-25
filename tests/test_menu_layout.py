import os
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.menu_layout import (
    attach_menu_layout, derive_legacy_ranks, duplicate_ranks, normalise_all,
    rank_setting_id, resolve_actions, restore_defaults, set_flattened, set_rank,
)
from arr_manager.registry import ACTION_REGISTRY, MENU_GROUPS, get_action_by_id


class Addon:
    def __init__(self, **values):
        self.values = dict(values)

    def getSetting(self, key):
        return self.values.get(key, "")

    def setSetting(self, key, value):
        self.values[key] = value


class Settings:
    menu_mode = "1"

    def __init__(self, hidden_actions=None, action_order=None):
        self.hidden_actions = list(hidden_actions or [])
        self.action_order = list(action_order or [])


class MenuLayoutTests(unittest.TestCase):
    def test_legacy_layout_migrates_per_group_and_persists_version(self):
        addon = Addon(menu_layout_version="0")
        settings = Settings(
            hidden_actions=["status", "queue_remove"],
            action_order=["queue", "search_now", "status", "queue_remove", "queue_view"],
        )

        attach_menu_layout(settings, addon)

        self.assertEqual(settings.menu_ranks["status"], 0)
        self.assertEqual(settings.menu_ranks["queue"], 10)
        self.assertEqual(settings.menu_ranks["search_now"], 20)
        self.assertEqual(settings.menu_ranks["queue_remove"], 0)
        self.assertEqual(settings.menu_ranks["queue_view"], 10)
        self.assertEqual(addon.values["menu_layout_version"], "1")
        self.assertEqual(addon.values[rank_setting_id("status")], "0")

    def test_fresh_layout_uses_registry_defaults(self):
        ranks = derive_legacy_ranks([], [])
        for action in ACTION_REGISTRY:
            if action["group"] in MENU_GROUPS:
                self.assertEqual(ranks[action["id"]], action["default_rank"])

    def test_numeric_ranks_drive_visibility_and_order(self):
        addon = Addon(menu_layout_version="1")
        settings = attach_menu_layout(Settings(), addon)
        set_rank(addon, settings, "queue", 5)
        set_rank(addon, settings, "status", 0)

        ids = [action["id"] for action in resolve_actions(settings, "root")]
        self.assertEqual(ids[0], "queue")
        self.assertNotIn("status", ids)

    def test_duplicate_ranks_are_deterministic_and_reported(self):
        addon = Addon(menu_layout_version="1")
        settings = attach_menu_layout(Settings(), addon)
        set_rank(addon, settings, "status", 30)
        set_rank(addon, settings, "search_now", 30)

        ids = [action["id"] for action in resolve_actions(settings, "root")]
        self.assertLess(ids.index("status"), ids.index("search_now"))
        duplicates = duplicate_ranks(settings)
        self.assertTrue(any(group == "root" and rank == 30 for group, rank, _ in duplicates))

    def test_flattening_inserts_one_prefixed_block_at_parent_position(self):
        addon = Addon(menu_layout_version="1")
        settings = attach_menu_layout(Settings(), addon)
        set_flattened(addon, settings, "monitoring", True)

        actions = resolve_actions(settings, "root")
        ids = [action["id"] for action in actions]
        monitor_index = ids.index("monitor")
        self.assertEqual(ids[monitor_index:monitor_index + 3], [
            "monitor", "unmonitor", "change_quality_profile",
        ])
        self.assertNotIn("monitoring", ids)
        self.assertEqual(actions[monitor_index]["flattened_from"], "monitoring")
        self.assertEqual(actions[monitor_index]["parent_rank"], 50)

    def test_disabling_parent_hides_flattened_children_without_erasing_child_ranks(self):
        addon = Addon(menu_layout_version="1")
        settings = attach_menu_layout(Settings(), addon)
        set_flattened(addon, settings, "monitoring", True)
        child_rank = settings.menu_ranks["monitor"]
        set_rank(addon, settings, "monitoring", 0)

        ids = [action["id"] for action in resolve_actions(settings, "root")]
        self.assertNotIn("monitor", ids)
        self.assertEqual(settings.menu_ranks["monitor"], child_rank)

    def test_normalise_keeps_disabled_items_at_zero(self):
        addon = Addon(menu_layout_version="1")
        settings = attach_menu_layout(Settings(), addon)
        set_rank(addon, settings, "status", 0)
        set_rank(addon, settings, "queue", 7)
        set_rank(addon, settings, "request_search", 99)

        normalise_all(addon, settings)

        self.assertEqual(settings.menu_ranks["status"], 0)
        enabled_root = [
            settings.menu_ranks[action["id"]]
            for action in resolve_actions(settings, "root")
            if not action.get("flattened_from")
        ]
        self.assertEqual(enabled_root, sorted(enabled_root))
        self.assertTrue(all(rank % 10 == 0 for rank in enabled_root))

    def test_restore_defaults_resets_only_layout_state(self):
        addon = Addon(menu_layout_version="1", radarr_url="http://radarr")
        settings = attach_menu_layout(Settings(), addon)
        set_rank(addon, settings, "status", 0)
        set_flattened(addon, settings, "tools", True)

        restore_defaults(addon, settings)

        self.assertEqual(settings.menu_ranks["status"], get_action_by_id("status")["default_rank"])
        self.assertFalse(settings.flatten_groups)
        self.assertEqual(addon.values["radarr_url"], "http://radarr")

    def test_settings_page_exposes_every_menu_action_as_integer_edit_with_help(self):
        root = ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot()
        for action in ACTION_REGISTRY:
            if action["group"] not in MENU_GROUPS:
                continue
            setting = root.find(".//setting[@id='%s']" % rank_setting_id(action["id"]))
            self.assertIsNotNone(setting, action["id"])
            self.assertEqual(setting.get("type"), "integer")
            self.assertTrue((setting.get("help") or "").strip())
            control = setting.find("control")
            self.assertIsNotNone(control)
            self.assertEqual(control.get("type"), "edit")
            self.assertEqual(control.get("format"), "integer")
            self.assertEqual(setting.findtext("constraints/minimum"), "0")
            self.assertEqual(setting.findtext("constraints/maximum"), "999")


if __name__ == "__main__":
    unittest.main()
