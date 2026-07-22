import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from arr_manager.registry import ACTION_REGISTRY


ROOT = Path(__file__).resolve().parents[1]


class RetentionIntegrationTests(unittest.TestCase):
    def test_manifest_registers_one_kodi_service(self):
        addon = ET.parse(ROOT / "addon.xml").getroot()
        services = addon.findall("extension[@point='xbmc.service']")
        self.assertEqual(len(services), 1)
        self.assertEqual(services[0].attrib.get("library"), "service.py")
        self.assertNotIn("start", services[0].attrib)

    def test_settings_expose_required_retention_controls(self):
        settings = ET.parse(ROOT / "resources/settings.xml").getroot()
        category = settings.find(".//category[@id='retention']")
        self.assertIsNotNone(category)
        ids = {node.attrib.get("id") for node in category.findall(".//setting")}
        required = {
            "retention_enabled", "retention_include_movies", "retention_include_episodes",
            "retention_watched_only", "retention_use_added_age", "retention_added_age_days",
            "retention_use_watched_age", "retention_watched_age_days", "retention_criteria_mode",
            "retention_periodic_enabled", "retention_interval_hours", "retention_max_deletions",
            "retention_background_dry_run", "retention_notification_mode", "retention_preview",
            "retention_run", "retention_enable", "retention_disable", "retention_report",
        }
        self.assertTrue(required <= ids)
        periodic = category.find(".//setting[@id='retention_periodic_enabled']")
        self.assertEqual(periodic.findtext("level"), "4")

    def test_registry_keeps_retention_out_of_simple_mode(self):
        actions = {item["id"]: item for item in ACTION_REGISTRY}
        self.assertFalse(actions["retention"]["simple_mode"])
        self.assertTrue(actions["retention"]["is_submenu"])
        self.assertFalse(actions["retention_run"]["requires_selection"])
        self.assertFalse(actions["retention_enable"]["destructive"])

    def test_automation_source_has_no_direct_vfs_deletion_path(self):
        executor = (ROOT / "resources/lib/arr_manager/retention/executor.py").read_text(encoding="utf-8")
        forbidden = ("make_direct_backend", "xbmcvfs.delete", "xbmcvfs.rmdir", "delete_tree")
        for token in forbidden:
            self.assertNotIn(token, executor)
        self.assertIn("delete_movie", executor)
        self.assertIn("delete_episode_file", executor)

    def test_packager_includes_service_entrypoint(self):
        package = (ROOT / "scripts/package.py").read_text(encoding="utf-8")
        self.assertIn('"service.py"', package)
        self.assertIn("xbmc.service", package)


if __name__ == "__main__":
    unittest.main()
