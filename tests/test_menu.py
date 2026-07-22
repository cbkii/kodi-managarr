import unittest
from unittest.mock import MagicMock
from arr_manager.entrypoints import _get_visible_actions

class MenuTests(unittest.TestCase):
    def test_simple_mode(self):
        settings = MagicMock()
        settings.menu_mode = "0"
        settings.hidden_actions = []
        settings.action_order = []
        actions = _get_visible_actions(settings, "root")
        ids = [a["id"] for a in actions]
        self.assertIn("status", ids)
        self.assertIn("search_now", ids)
        self.assertNotIn("monitoring", ids)

    def test_advanced_mode(self):
        settings = MagicMock()
        settings.menu_mode = "1"
        settings.hidden_actions = []
        settings.action_order = []
        actions = _get_visible_actions(settings, "root")
        ids = [a["id"] for a in actions]
        self.assertIn("status", ids)
        self.assertIn("search_now", ids)
        self.assertIn("monitoring", ids)

    def test_hidden_actions(self):
        settings = MagicMock()
        settings.menu_mode = "1"
        settings.hidden_actions = ["monitoring"]
        settings.action_order = []
        actions = _get_visible_actions(settings, "root")
        ids = [a["id"] for a in actions]
        self.assertNotIn("monitoring", ids)

    def test_action_ordering(self):
        settings = MagicMock()
        settings.menu_mode = "1"
        settings.hidden_actions = []
        settings.action_order = ["queue", "status", "search_now"]
        actions = _get_visible_actions(settings, "root")
        ids = [a["id"] for a in actions]
        # order is [items in action_order...] followed by the rest
        self.assertEqual(ids[0], "queue")
        self.assertEqual(ids[1], "status")
        self.assertEqual(ids[2], "search_now")

if __name__ == "__main__":
    unittest.main()
