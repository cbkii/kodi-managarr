import unittest

from arr_manager.registry import ACTION_REGISTRY, get_action_by_id, get_action_by_mode


class RegistryTests(unittest.TestCase):
    REQUIRED_FIELDS = {
        "id", "label_id", "default_label", "group", "mode", "default_mode",
        "default_order", "media_types", "mutating", "destructive",
        "requires_selection", "simple_mode", "advanced_mode", "is_submenu",
        "dispatcher_mode",
    }

    def test_registry_ids_modes_and_orders_are_unique(self):
        self.assertGreater(len(ACTION_REGISTRY), 5)
        self.assertEqual(len({action["id"] for action in ACTION_REGISTRY}), len(ACTION_REGISTRY))
        self.assertEqual(len({action["mode"] for action in ACTION_REGISTRY}), len(ACTION_REGISTRY))
        self.assertEqual(len({action["default_order"] for action in ACTION_REGISTRY}), len(ACTION_REGISTRY))

    def test_every_action_has_complete_policy_metadata(self):
        for action in ACTION_REGISTRY:
            with self.subTest(action=action["id"]):
                self.assertTrue(self.REQUIRED_FIELDS.issubset(action))
                self.assertEqual(action["dispatcher_mode"], action["mode"])
                self.assertTrue(action["advanced_mode"])
                self.assertTrue(set(action["media_types"]).issubset({"movie", "tvshow", "episode"}))
                if action["destructive"]:
                    self.assertTrue(action["mutating"])

    def test_destructive_pin_scope_is_media_deletion_only(self):
        destructive = {action["id"] for action in ACTION_REGISTRY if action["destructive"]}
        self.assertEqual(destructive, {"delete_exclude", "delete_replace"})
        queue_remove = get_action_by_id("queue_remove")
        self.assertTrue(queue_remove["mutating"])
        self.assertFalse(queue_remove["destructive"])

    def test_simple_mode_preserves_common_and_destructive_actions(self):
        simple = {action["id"] for action in ACTION_REGISTRY if action["simple_mode"]}
        self.assertEqual(
            simple,
            {"status", "search_now", "delete_exclude", "delete_replace", "tools"},
        )

    def test_lookup_by_id_and_mode(self):
        status = get_action_by_id("status")
        self.assertIsNotNone(status)
        self.assertEqual(status["mode"], "status")
        delete = get_action_by_mode("delete_exclude")
        self.assertIsNotNone(delete)
        self.assertEqual(delete["id"], "delete_exclude")
        self.assertIsNone(get_action_by_id("retired_action"))
        self.assertIsNone(get_action_by_mode("retired_mode"))


if __name__ == "__main__":
    unittest.main()
