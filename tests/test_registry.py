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
        self.assertGreater(len(ACTION_REGISTRY), 10)
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
        self.assertFalse(get_action_by_id("queue_remove")["destructive"])
        self.assertFalse(get_action_by_id("request_search")["destructive"])
        self.assertFalse(get_action_by_id("interactive_search")["destructive"])

    def test_simple_mode_is_remote_friendly_and_complete(self):
        simple = {action["id"] for action in ACTION_REGISTRY if action["simple_mode"]}
        self.assertEqual(simple, {
            "request_search", "status", "search_now", "dashboard", "find_subtitles",
            "delete_exclude", "delete_replace", "tools",
        })

    def test_new_actions_are_reachable_and_have_expected_selection_policy(self):
        for action_id in (
            "request_search", "interactive_search", "dashboard", "find_subtitles",
            "configure_request_defaults", "configure_subtitle_languages",
        ):
            action = get_action_by_id(action_id)
            self.assertIsNotNone(action)
            self.assertIs(get_action_by_mode(action["mode"]), action)
        self.assertTrue(get_action_by_id("request_search")["requires_selection"])
        self.assertFalse(get_action_by_id("dashboard")["requires_selection"])
        self.assertFalse(get_action_by_id("find_subtitles")["requires_selection"])

    def test_lookup_by_id_and_mode(self):
        status = get_action_by_id("status")
        self.assertEqual(status["mode"], "status")
        self.assertEqual(get_action_by_mode("delete_exclude")["id"], "delete_exclude")
        self.assertIsNone(get_action_by_id("retired_action"))
        self.assertIsNone(get_action_by_mode("retired_mode"))


if __name__ == "__main__":
    unittest.main()
