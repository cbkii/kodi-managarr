import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.config import Settings


class Addon:
    def __init__(self, values=None): self.values = values or {}
    def getSetting(self, key): return self.values.get(key, "")
    def getAddonInfo(self, key): return "1.2.0" if key == "version" else ""


class InteractiveConfigTests(unittest.TestCase):
    def test_optional_services_are_disabled_and_do_not_require_configuration(self):
        settings = Settings(Addon())
        self.assertFalse(settings.prowlarr.enabled)
        self.assertFalse(settings.bazarr.enabled)
        self.assertTrue(settings.radarr.enabled)
        self.assertTrue(settings.sonarr.enabled)

    def test_request_defaults_and_languages_are_validated(self):
        settings = Settings(Addon({
            "request_radarr_root": "/movies", "request_radarr_profile": "2",
            "request_sonarr_root": "/shows", "request_sonarr_profile": "3",
            "request_sonarr_monitor": "missing",
            "bazarr_language_1": "EN", "bazarr_language_2": "en", "bazarr_language_3": "fr:forced",
        }))
        self.assertTrue(settings.request_defaults_ready("radarr"))
        self.assertTrue(settings.request_defaults_ready("sonarr"))
        self.assertEqual(settings.request_sonarr_monitor, "missing")
        self.assertEqual(settings.bazarr_languages, ["en", "fr:forced"])

    def test_invalid_optional_values_are_safely_ignored_or_defaulted(self):
        settings = Settings(Addon({
            "request_sonarr_monitor": "invalid", "bazarr_language_1": "../../secret",
            "bazarr_language_2": "es:hi",
        }))
        self.assertEqual(settings.request_sonarr_monitor, "future")
        self.assertEqual(settings.bazarr_languages, ["es:hi"])
        self.assertFalse(settings.request_defaults_ready("radarr"))


if __name__ == "__main__":
    unittest.main()
