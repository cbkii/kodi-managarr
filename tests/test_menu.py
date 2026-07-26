import unittest

from arr_manager.menu_layout import resolve_actions
from arr_manager.registry import ACTION_REGISTRY


class Settings:
    def __init__(self, mode="1"):
        self.menu_mode = mode
        self.menu_ranks = {action["id"]: action["default_rank"] for action in ACTION_REGISTRY}
        self.flatten_groups = set()
        self.hidden_actions = []
        self.action_order = []


class MenuTests(unittest.TestCase):
    def test_simple_mode(self):
        settings = Settings("0")
        ids = [action["id"] for action in resolve_actions(settings, "root")]
        self.assertIn("status", ids)
        self.assertIn("search_now", ids)
        self.assertNotIn("monitoring", ids)
        self.assertNotIn("retention", ids)

    def test_advanced_mode_uses_group_parents(self):
        settings = Settings("1")
        ids = [action["id"] for action in resolve_actions(settings, "root")]
        self.assertIn("monitoring", ids)
        self.assertIn("queue", ids)
        self.assertIn("retention", ids)
        self.assertIn("tools", ids)
        self.assertNotIn("monitor", ids)
        self.assertNotIn("retention_cleanup", ids)
        self.assertNotIn("configure_request_defaults", ids)

    def test_zero_rank_hides_action(self):
        settings = Settings()
        settings.menu_ranks["monitoring"] = 0
        ids = [action["id"] for action in resolve_actions(settings, "root")]
        self.assertNotIn("monitoring", ids)

    def test_numeric_ordering(self):
        settings = Settings()
        settings.menu_ranks["queue"] = 5
        settings.menu_ranks["status"] = 6
        settings.menu_ranks["search_now"] = 7
        ids = [action["id"] for action in resolve_actions(settings, "root")]
        self.assertEqual(ids[:3], ["queue", "status", "search_now"])

    def test_flattened_children_form_one_parent_block(self):
        settings = Settings()
        settings.flatten_groups.add("queue")
        ids = [action["id"] for action in resolve_actions(settings, "root")]
        index = ids.index("queue_view")
        self.assertEqual(ids[index:index + 2], ["queue_view", "queue_remove"])
        self.assertNotIn("queue", ids)


if __name__ == "__main__":
    unittest.main()
