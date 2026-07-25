import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.retention.auth import pin_generation
from arr_manager.retention.models import RetentionCandidate, RetentionEligibility
from arr_manager.retention.service import RetentionService


def episode(db_id, season, episode_number, file_id=500):
    return RetentionCandidate(
        media_type="episode",
        db_id=db_id,
        arr_id=50,
        file_id=file_id,
        title="Episode",
        display_name=f"Show S{season:02d}E{episode_number:02d}",
        watched=True,
        last_played=1,
        date_added=1,
        tvshow_db_id=5,
        season=season,
        episode=episode_number,
    )


class Settings:
    pin_invalid = False
    pin_enabled = False
    pin_hash = b""
    pin_salt = b""


class RetentionServiceTests(unittest.TestCase):
    def test_shared_file_is_protected_when_any_linked_episode_is_protected(self):
        evaluated = [
            (episode(1, 1, 1), RetentionEligibility(True, "Criteria met")),
            (episode(2, 1, 2), RetentionEligibility(False, "Explicit episode exclusion")),
        ]
        protected = RetentionService._protect_shared_files(evaluated)
        self.assertFalse(protected[0][1].eligible)
        self.assertEqual(protected[0][1].reason, "Shared episode file contains a protected episode")
        self.assertFalse(protected[1][1].eligible)

    def test_distinct_episode_files_are_evaluated_independently(self):
        evaluated = [
            (episode(1, 1, 1, file_id=500), RetentionEligibility(True, "Criteria met")),
            (episode(2, 1, 2, file_id=501), RetentionEligibility(False, "Not watched")),
        ]
        protected = RetentionService._protect_shared_files(evaluated)
        self.assertTrue(protected[0][1].eligible)
        self.assertFalse(protected[1][1].eligible)

    def test_pin_generation_changes_with_pin_material(self):
        settings = Settings()
        self.assertEqual(pin_generation(settings), "none")
        settings.pin_enabled = True
        settings.pin_hash = b"a" * 32
        settings.pin_salt = b"b" * 16
        first = pin_generation(settings)
        settings.pin_hash = b"c" * 32
        second = pin_generation(settings)
        self.assertNotEqual(first, second)
        settings.pin_invalid = True
        self.assertEqual(pin_generation(settings), "invalid")


if __name__ == "__main__":
    unittest.main()
