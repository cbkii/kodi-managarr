import unittest
from arr_manager.registry import ACTION_REGISTRY, get_action_by_id, get_action_by_mode

class RegistryTests(unittest.TestCase):
    def test_registry_has_actions(self):
        self.assertGreater(len(ACTION_REGISTRY), 5)

    def test_get_action_by_id(self):
        action = get_action_by_id("status")
        self.assertIsNotNone(action)
        self.assertEqual(action["mode"], "status")

    def test_get_action_by_mode(self):
        action = get_action_by_mode("delete_exclude")
        self.assertIsNotNone(action)
        self.assertEqual(action["id"], "delete_exclude")
        self.assertTrue(action["destructive"])

if __name__ == "__main__":
    unittest.main()
