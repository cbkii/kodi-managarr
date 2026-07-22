import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from arr_manager.pin import authorize_action, hash_pin, validate_pin, verify_pin


class Addon:
    def getLocalizedString(self, string_id): return ""


def settings(**values):
    defaults = {
        "addon": Addon(),
        "pin_enabled": False,
        "pin_invalid": False,
        "pin_hash": b"",
        "pin_salt": b"",
    }
    defaults.update(values)
    return SimpleNamespace(**defaults)


class PinTests(unittest.TestCase):
    def test_hash_and_verify_uses_salt_and_constant_time_boundary(self):
        first_key, first_salt = hash_pin("1234")
        second_key, second_salt = hash_pin("1234")
        self.assertNotEqual(first_salt, second_salt)
        self.assertNotEqual(first_key, second_key)
        self.assertTrue(verify_pin("1234", first_key, first_salt))
        self.assertFalse(verify_pin("4321", first_key, first_salt))
        with patch("arr_manager.pin.hmac.compare_digest", return_value=True) as compare:
            self.assertTrue(verify_pin("1234", first_key, first_salt))
            compare.assert_called_once()

    def test_pin_validation_boundary(self):
        for value in ("1234", "12345678"):
            self.assertEqual(validate_pin(value), value)
        for value in ("123", "123456789", "12a4", "", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_pin(value)
            with self.subTest(hash_value=value), self.assertRaises(ValueError):
                hash_pin(value)

    def test_verify_rejects_invalid_input_or_credentials(self):
        key, salt = hash_pin("1234")
        self.assertFalse(verify_pin("12a4", key, salt))
        self.assertFalse(verify_pin("1234", b"", salt))
        self.assertFalse(verify_pin("1234", key, b""))

    def test_non_destructive_and_queue_actions_do_not_prompt(self):
        ui = MagicMock()
        self.assertTrue(authorize_action("status", settings(pin_enabled=True), ui))
        self.assertTrue(authorize_action("queue_remove", settings(pin_enabled=True), ui))
        ui.numeric_input.assert_not_called()

    def test_pin_disabled_allows_media_deletion(self):
        ui = MagicMock()
        self.assertTrue(authorize_action("delete_exclude", settings(), ui))
        ui.numeric_input.assert_not_called()

    def test_authorize_action_success(self):
        key, salt = hash_pin("1234")
        ui = MagicMock(); ui.numeric_input.return_value = "1234"
        self.assertTrue(authorize_action(
            "delete_replace",
            settings(pin_enabled=True, pin_hash=key, pin_salt=salt),
            ui,
        ))
        ui.numeric_input.assert_called_once()
        ui.notification.assert_not_called()

    def test_authorize_action_failure_exhaustion(self):
        key, salt = hash_pin("1234")
        ui = MagicMock(); ui.numeric_input.return_value = "9999"
        self.assertFalse(authorize_action(
            "delete_exclude",
            settings(pin_enabled=True, pin_hash=key, pin_salt=salt),
            ui,
        ))
        self.assertEqual(ui.numeric_input.call_count, 3)
        self.assertEqual(ui.notification.call_count, 4)

    def test_authorize_action_cancel(self):
        key, salt = hash_pin("1234")
        ui = MagicMock(); ui.numeric_input.return_value = ""
        self.assertFalse(authorize_action(
            "delete_exclude",
            settings(pin_enabled=True, pin_hash=key, pin_salt=salt),
            ui,
        ))
        ui.numeric_input.assert_called_once()
        ui.notification.assert_not_called()

    def test_invalid_stored_state_fails_closed_without_prompt(self):
        ui = MagicMock()
        self.assertFalse(authorize_action(
            "delete_exclude",
            settings(pin_enabled=True, pin_invalid=True),
            ui,
        ))
        ui.numeric_input.assert_not_called()
        ui.notification.assert_called_once()


if __name__ == "__main__":
    unittest.main()
