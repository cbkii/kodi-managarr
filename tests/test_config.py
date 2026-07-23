import os
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.config import Settings
from arr_manager.errors import ConfigurationError


class Addon:
    defaults = {
        "deletion_backend": "api", "confirm_actions": "false", "dry_run": "false",
        "require_blocklist": "true", "debug": "false", "path_mappings": "",
        "protected_paths": "", "rescan_poll_timeout": "5", "http_timeout": "15",
        "radarr_enabled": "true", "radarr_url": "http://radarr", "radarr_api_key": "key",
        "radarr_api_version": "v3", "radarr_verify_tls": "true", "sonarr_enabled": "true",
        "sonarr_url": "http://sonarr", "sonarr_api_key": "key", "sonarr_api_version": "v3",
        "sonarr_verify_tls": "true", "menu_mode": "", "hidden_actions": "", "action_order": "",
        "pin_hash": "", "pin_salt": "",
    }

    def __init__(self, **values):
        self.values = dict(self.defaults)
        self.values.update(values)

    def getSetting(self, key):
        return self.values.get(key, "")

    def getAddonInfo(self, key):
        return "1.2.0" if key == "version" else ""


class ConfigTests(unittest.TestCase):
    def test_fresh_install_defaults_to_dry_run_but_saved_false_is_preserved(self):
        self.assertTrue(Settings(Addon(dry_run="")).dry_run)
        self.assertTrue(Settings(Addon(dry_run="true")).dry_run)
        self.assertFalse(Settings(Addon(dry_run="false")).dry_run)

        settings = ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot()
        dry_run = settings.find(".//setting[@id='dry_run']")
        self.assertIsNotNone(dry_run)
        self.assertEqual((dry_run.findtext("default") or "").strip().lower(), "true")

    def test_blank_menu_mode_preserves_existing_advanced_actions(self):
        self.assertEqual(Settings(Addon(menu_mode="")).menu_mode, "1")
        self.assertEqual(Settings(Addon(menu_mode="advanced")).menu_mode, "1")
        self.assertEqual(Settings(Addon(menu_mode="1")).menu_mode, "1")
        self.assertEqual(Settings(Addon(menu_mode="simple")).menu_mode, "0")
        self.assertEqual(Settings(Addon(menu_mode="0")).menu_mode, "0")

    def test_stale_menu_state_is_discarded_and_deduplicated(self):
        settings = Settings(Addon(
            hidden_actions="status,retired_action,status",
            action_order="queue,retired_action,queue,status",
        ))
        self.assertEqual(settings.hidden_actions, ["status"])
        self.assertEqual(settings.action_order, ["queue", "status"])

    def test_pin_state_absent_valid_incomplete_and_malformed(self):
        absent = Settings(Addon())
        self.assertFalse(absent.pin_enabled)
        self.assertFalse(absent.pin_invalid)

        valid = Settings(Addon(pin_hash="11" * 32, pin_salt="22" * 16))
        self.assertTrue(valid.pin_enabled)
        self.assertFalse(valid.pin_invalid)
        self.assertEqual(len(valid.pin_hash), 32)
        self.assertEqual(len(valid.pin_salt), 16)

        for values in (
            {"pin_hash": "11" * 32, "pin_salt": ""},
            {"pin_hash": "", "pin_salt": "22" * 16},
            {"pin_hash": "not-hex", "pin_salt": "22" * 16},
            {"pin_hash": "11", "pin_salt": "22"},
        ):
            with self.subTest(values=values):
                invalid = Settings(Addon(**values))
                self.assertTrue(invalid.pin_enabled)
                self.assertTrue(invalid.pin_invalid)
                self.assertEqual(invalid.pin_hash, b"")
                self.assertEqual(invalid.pin_salt, b"")

    def test_malformed_vfs_protected_paths_raise_configuration_error(self):
        with self.assertRaises(ConfigurationError):
            Settings(Addon(deletion_backend="vfs", protected_paths="/media/%zz"))

    def test_api_backend_ignores_inactive_protected_path_errors(self):
        settings = Settings(Addon(deletion_backend="api", protected_paths="/media/%zz"))
        self.assertEqual(settings.protected_paths, [])

    def test_api_backend_survives_malformed_inactive_mapping(self):
        settings = Settings(Addon(deletion_backend="api", path_mappings="not-a-mapping"))
        self.assertEqual(settings.path_mapper.mappings, [])
        self.assertIn("Invalid path mapping", settings.path_mapping_warning)

    def test_vfs_backend_rejects_malformed_mapping(self):
        with self.assertRaises(ConfigurationError):
            Settings(Addon(deletion_backend="vfs", path_mappings="not-a-mapping"))

    def test_valid_vfs_protected_paths_are_normalised(self):
        settings = Settings(Addon(
            deletion_backend="vfs",
            protected_paths="/media//Movies; smb://PI/Movies",
        ))
        self.assertEqual(settings.protected_paths, ["/media/Movies", "smb://pi/Movies"])

    def test_mapping_roots_are_automatically_protected_for_vfs(self):
        settings = Settings(Addon(
            deletion_backend="vfs",
            path_mappings="/media/Movies=>smb://pi/Movies",
        ))
        self.assertIn("smb://pi/Movies", settings.protected_paths)

    def test_service_config_uses_installed_addon_version(self):
        settings = Settings(Addon())
        self.assertEqual(settings.radarr.user_agent, "Kodi-Managarr/1.2.0")
        self.assertEqual(settings.sonarr.user_agent, "Kodi-Managarr/1.2.0")


if __name__ == "__main__":
    unittest.main()
