import unittest
from unittest.mock import MagicMock
from arr_manager.retention.config import RetentionSettings
from arr_manager.errors import ConfigurationError

class MockAddon:
    def __init__(self, settings):
        self.settings = settings
    def getSetting(self, key):
        return self.settings.get(key, "")

class TestRetentionConfig(unittest.TestCase):
    def test_default_values(self):
        settings_dict = {}
        addon = MockAddon(settings_dict)
        settings = RetentionSettings(addon)

        self.assertFalse(settings.enabled)
        self.assertFalse(settings.include_movies)
        self.assertFalse(settings.include_episodes)
        self.assertTrue(settings.watched_only)
        self.assertTrue(settings.use_added_age)
        self.assertEqual(settings.added_age_days, 0)
        self.assertEqual(settings.criteria_mode, "all")
        self.assertEqual(settings.notification_mode, "errors_only")

        with self.assertRaisesRegex(ConfigurationError, "Retention is disabled"):
            settings.validate()

    def test_validation_requires_media(self):
        settings_dict = {
            "retention_enabled": "true",
            "retention_include_movies": "false",
            "retention_include_episodes": "false",
        }
        addon = MockAddon(settings_dict)
        settings = RetentionSettings(addon)

        with self.assertRaisesRegex(ConfigurationError, "requires at least movies or episodes"):
            settings.validate()

if __name__ == "__main__":
    unittest.main()
