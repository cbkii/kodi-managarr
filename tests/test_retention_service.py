import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.retention.auth import pin_generation
from arr_manager.retention.models import RetentionCandidate, RetentionEligibility, RetentionReportItem
from arr_manager.retention.service import RetentionService


def episode(db_id, season, episode_number, file_id=500, linked_episode_count=1):
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
        linked_episode_count=linked_episode_count,
    )


class Settings:
    pin_invalid = False
    pin_enabled = False
    pin_hash = b""
    pin_salt = b""


class Addon:
    def getLocalizedString(self, _string_id):
        return ""


class Progress:
    def __init__(self):
        self.updates = []
        self.closed = False

    def update(self, percentage, message):
        self.updates.append((percentage, message))

    def iscanceled(self):
        return False

    def close(self):
        self.closed = True


class UI:
    monitor = None

    def __init__(self):
        self.progress_dialog = Progress()

    def progress(self, _heading, _message):
        return self.progress_dialog


class Executor:
    def execute(self, candidate, dry_run):
        return RetentionReportItem(
            candidate.media_type,
            candidate.display_name,
            candidate.db_id,
            True,
            "Criteria met",
            "dry_run" if dry_run else "deleted",
        )


class RetentionServiceTests(unittest.TestCase):
    def test_shared_file_is_protected_when_any_linked_episode_is_protected(self):
        evaluated = [
            (episode(1, 1, 1, linked_episode_count=2), RetentionEligibility(True, "Criteria met")),
            (
                episode(2, 1, 2, linked_episode_count=2),
                RetentionEligibility(False, "Explicit episode exclusion"),
            ),
        ]
        protected = RetentionService._protect_shared_files(evaluated)
        self.assertFalse(protected[0][1].eligible)
        self.assertEqual(protected[0][1].reason, "Shared episode file contains a protected episode")
        self.assertFalse(protected[1][1].eligible)

    def test_shared_file_is_protected_when_a_linked_kodi_row_is_missing(self):
        evaluated = [
            (episode(1, 1, 1, linked_episode_count=2), RetentionEligibility(True, "Criteria met")),
        ]
        protected = RetentionService._protect_shared_files(evaluated)
        self.assertFalse(protected[0][1].eligible)
        self.assertEqual(protected[0][1].reason, "Shared episode file is missing linked Kodi episodes")

    def test_distinct_episode_files_are_evaluated_independently(self):
        evaluated = [
            (episode(1, 1, 1, file_id=500), RetentionEligibility(True, "Criteria met")),
            (episode(2, 1, 2, file_id=501), RetentionEligibility(False, "Not watched")),
        ]
        protected = RetentionService._protect_shared_files(evaluated)
        self.assertTrue(protected[0][1].eligible)
        self.assertFalse(protected[1][1].eligible)

    def test_missing_file_id_is_never_an_eligible_deletion_target(self):
        evaluated = [
            (episode(1, 1, 1, file_id=None), RetentionEligibility(True, "Criteria met")),
            (episode(2, 1, 2, file_id=501), RetentionEligibility(True, "Criteria met")),
        ]
        eligible = RetentionService._eligible_unique(evaluated)
        self.assertEqual([candidate.file_id for candidate in eligible], [501])

    def test_interactive_progress_reaches_100_percent(self):
        service = object.__new__(RetentionService)
        service.addon = Addon()
        service.ui = UI()
        summary = service._run_pass(
            [episode(1, 1, 1), episode(2, 1, 2, file_id=501)],
            Executor(),
            dry_run=True,
            interactive=True,
        )
        self.assertEqual(service.ui.progress_dialog.updates[-1][0], 100)
        self.assertTrue(service.ui.progress_dialog.closed)
        self.assertEqual(summary["planned"], 2)

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
