import unittest
from unittest.mock import MagicMock
from arr_manager.pin import hash_pin, verify_pin, authorize_action

class PinTests(unittest.TestCase):
    def test_hash_and_verify(self):
        pin = "1234"
        key, salt = hash_pin(pin)
        self.assertTrue(verify_pin(pin, key, salt))
        self.assertFalse(verify_pin("4321", key, salt))

    def test_authorize_action_not_destructive(self):
        settings = MagicMock()
        ui = MagicMock()
        self.assertTrue(authorize_action("status", settings, ui))
        ui.numeric_input.assert_not_called()

    def test_authorize_action_pin_disabled(self):
        settings = MagicMock()
        settings.pin_enabled = False
        ui = MagicMock()
        self.assertTrue(authorize_action("delete_exclude", settings, ui))
        ui.numeric_input.assert_not_called()

    def test_authorize_action_success(self):
        settings = MagicMock()
        settings.pin_enabled = True
        key, salt = hash_pin("1234")
        settings.pin_hash = key
        settings.pin_salt = salt
        ui = MagicMock()
        ui.numeric_input.return_value = "1234"
        self.assertTrue(authorize_action("delete_exclude", settings, ui))
        ui.numeric_input.assert_called_once()
        ui.notification.assert_not_called()

    def test_authorize_action_failure_exhaustion(self):
        settings = MagicMock()
        settings.pin_enabled = True
        key, salt = hash_pin("1234")
        settings.pin_hash = key
        settings.pin_salt = salt
        ui = MagicMock()
        ui.numeric_input.return_value = "9999"
        self.assertFalse(authorize_action("delete_exclude", settings, ui))
        self.assertEqual(ui.numeric_input.call_count, 3)
        self.assertEqual(ui.notification.call_count, 3)

    def test_authorize_action_cancel(self):
        settings = MagicMock()
        settings.pin_enabled = True
        key, salt = hash_pin("1234")
        settings.pin_hash = key
        settings.pin_salt = salt
        ui = MagicMock()
        ui.numeric_input.return_value = None
        self.assertFalse(authorize_action("delete_exclude", settings, ui))
        ui.numeric_input.assert_called_once()
        ui.notification.assert_not_called()

if __name__ == "__main__":
    unittest.main()
