import os
import sys
import unittest

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
        "sonarr_verify_tls": "true",
    }

    def __init__(self, **values):
        self.values = dict(self.defaults)
        self.values.update(values)

    def getSetting(self, key):
        return self.values.get(key, "")

    def getAddonInfo(self, key):
        return "1.1.0" if key == "version" else ""


class ConfigTests(unittest.TestCase):
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
        self.assertEqual(settings.radarr.user_agent, "Kodi-Managarr/1.1.0")
        self.assertEqual(settings.sonarr.user_agent, "Kodi-Managarr/1.1.0")


if __name__ == "__main__":
    unittest.main()
