from pathlib import Path


def replace(path, old, new):
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected text missing in {path}: {old!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# Explicit transaction outcomes and bounded command evidence.
replace(
    "resources/lib/arr_manager/models.py",
    '    command_result: str = ""\n',
    '    command_result: str = ""\n    command_elapsed_seconds: float = 0.0\n',
)
replace(
    "resources/lib/arr_manager/models.py",
    '    def record_command(self, description: str, command: dict) -> None:\n',
    '    def record_command(self, description: str, command: dict, elapsed_seconds: float = 0.0) -> None:\n',
)
replace(
    "resources/lib/arr_manager/models.py",
    '        self.command_result = str(command.get("result") or "")\n',
    '        self.command_result = str(command.get("result") or "")\n'
    '        try:\n'
    '            self.command_elapsed_seconds = max(0.0, float(elapsed_seconds or 0.0))\n'
    '        except (TypeError, ValueError):\n'
    '            self.command_elapsed_seconds = 0.0\n',
)
replace(
    "resources/lib/arr_manager/models.py",
    '    def as_dict(self, exc: Optional[Exception] = None) -> dict:\n        payload = {\n',
    '    def as_dict(self, exc: Optional[Exception] = None) -> dict:\n'
    '        command_terminal = self.command_status.lower() in {"completed", "complete"}\n'
    '        if exc is not None:\n'
    '            outcome = "committed_failed" if self.committed else "stopped_precommit"\n'
    '        elif self.command_id and not command_terminal:\n'
    '            outcome = "queued"\n'
    '        else:\n'
    '            outcome = "completed"\n'
    '        payload = {\n',
)
replace(
    "resources/lib/arr_manager/models.py",
    '            "status": "failed" if exc is not None else "completed",\n',
    '            "status": "failed" if exc is not None else "completed",\n'
    '            "outcome": outcome,\n',
)
replace(
    "resources/lib/arr_manager/models.py",
    '            "commandResult": self.command_result,\n',
    '            "commandResult": self.command_result,\n'
    '            "commandElapsedSeconds": round(self.command_elapsed_seconds, 3),\n',
)
replace(
    "resources/lib/arr_manager/entrypoints.py",
    '                "status": str(candidate.get("status", "")),\n'
    '                "errorType": str(candidate.get("errorType", "")),\n',
    '                "status": str(candidate.get("status", "")),\n'
    '                "outcome": str(candidate.get("outcome", "")),\n'
    '                "errorType": str(candidate.get("errorType", "")),\n',
)
replace(
    "resources/lib/arr_manager/entrypoints.py",
    '                "commandResult": str(candidate.get("commandResult", "")),\n',
    '                "commandResult": str(candidate.get("commandResult", "")),\n'
    '                "commandElapsedSeconds": float(candidate.get("commandElapsedSeconds", 0) or 0),\n',
)

Path("tests/test_transaction_outcomes.py").write_text('''import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.models import TransactionState


class TransactionOutcomeTests(unittest.TestCase):
    def test_queued_command_is_distinguished_from_completed_work(self):
        tx = TransactionState("movie replacement")
        tx.record_command("Radarr movie search", {"id": 91, "status": "queued"})
        tx.mark("replacement search queued")
        payload = tx.as_dict()
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["outcome"], "queued")
        self.assertEqual(payload["commandId"], 91)
        self.assertEqual(payload["commandElapsedSeconds"], 0.0)

    def test_precommit_and_committed_failures_are_distinct(self):
        precommit = TransactionState("episode replacement")
        precommit.begin("Kodi cleanup preflight")
        self.assertEqual(precommit.as_dict(RuntimeError("no"))["outcome"], "stopped_precommit")

        committed = TransactionState("episode replacement")
        committed.mark("episode file deletion", committed=True)
        committed.begin("replacement search submission")
        self.assertEqual(committed.as_dict(RuntimeError("no"))["outcome"], "committed_failed")


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

# User-facing and architecture documentation.
replace(
    "README.md",
    "- **Search & download now** - queues and verifies the appropriate Radarr movie, Sonarr series or Sonarr episode search.\n",
    "- **Search & download now** - submits the appropriate Radarr movie, Sonarr series or Sonarr episode search and reports the accepted Servarr command as queued.\n",
)
replace(
    "README.md",
    "- **Delete & Replace** - proves and blocklists the imported release, deletes the file, reconciles Servarr, searches for a replacement and synchronises Kodi.\n",
    "- **Delete & Replace** - proves and blocklists the imported release, deletes the file, performs any safety-critical reconciliation, queues a replacement search and synchronises Kodi. If an earlier attempt already removed the file, it safely queues only the exact recovery search.\n",
)
replace(
    "README.md",
    "- Servarr commands succeed only with terminal `Completed` status and `Successful` result.\n",
    "- Search commands are accepted once Servarr returns a valid, non-failed command ID; Managarr does not falsely fail a committed replacement while a search continues asynchronously. Terminal `Completed`/`Successful` polling remains mandatory only for rescans or reconciliation that later safety depends on.\n",
)
replace(
    "README.md",
    "- Partial commits are persisted without secrets and reported with completed transaction stages.\n",
    "- Partial commits and queued-search outcomes are persisted without secrets, including completed/failed stage, command ID/status/result and sanitised Kodi JSON-RPC evidence.\n",
)
replace(
    "README.md",
    "Validation covers the ASCII context root, registry dispatch, safe fresh-install defaults, localisation, PIN policy, optional-service isolation, subtitle entrypoint, metadata limits, release packaging and repository generation. CI runs Python 3.8 and 3.12 alongside actionlint, Ruff, archive integrity and Kodi add-on checker.\n",
    "Validation covers the ASCII context root, registry dispatch, safe fresh-install defaults, localisation, PIN policy, optional-service isolation, episode-tile JSON-RPC contracts, queued replacement recovery, subtitle entrypoint, metadata limits, release packaging and repository generation. CI runs Python 3.8 and 3.12 alongside actionlint, Ruff, archive integrity and Kodi add-on checker. See [replacement reliability](docs/REPLACEMENT_RELIABILITY.md) for the transaction and recovery contract.\n",
)
replace(
    "docs/ARCHITECTURE.md",
    "## Request & Search\n",
    "## Replacement reliability\n\nEpisode cleanup preflight uses Kodi's canonical `showtitle` property for `VideoLibrary.GetEpisodeDetails` and requests only `season`, `episode` and `file` when enumerating linked rows. Ordinary single-episode files do not trigger a whole-show scan; multi-episode files use a season-scoped lookup and reject contradictory or duplicate identities before any Servarr mutation.\n\nServarr search commands are asynchronous. A valid non-failed command ID is recorded as **queued** without waiting for the full indexer search to finish. Strict terminal polling remains limited to rescans and file-record reconciliation required before a later destructive or replacement stage can proceed. Transactions distinguish completed, queued, stopped-before-commit and committed-failure outcomes and preserve only sanitised stage, command and Kodi JSON-RPC evidence. An already-missing exact movie or episode enters search-only recovery and never repeats blocklisting, deletion or Kodi row removal.\n\n## Request & Search\n",
)
replace(
    "docs/ANDROID_KODI_VALIDATION.md",
    "## 5. PIN and existing safety\n",
    "## 5. Episode-tile replacement reliability\n\nUse a disposable episode and, separately, a disposable multi-episode file.\n\n1. From the episode tile, run Delete & Replace in dry-run mode and confirm Kodi accepts the episode-detail request without `Invalid params`.\n2. Confirm a normal single-episode file does not enumerate the entire show.\n3. For a multi-episode file, confirm all linked rows in the same season are planned and unrelated rows are untouched.\n4. Induce a Kodi JSON-RPC preflight failure and confirm no Sonarr history, delete or search mutation occurs; diagnostics must report `stopped_precommit`.\n5. Perform one disposable API-backend replacement and confirm the result reports the Sonarr search as queued rather than timing out while the command remains active.\n6. Repeat after the file is already absent and confirm Managarr queues only the exact recovery search without a second blocklist/delete/Kodi-row removal.\n7. Confirm transaction diagnostics contain no media path, URL, API key or credentials.\n\n## 6. PIN and existing safety\n",
)
for old, new in [
    ("## 6. Request & Search", "## 7. Request & Search"),
    ("## 7. Interactive release search and Dashboard", "## 8. Interactive release search and Dashboard"),
    ("## 8. Bazarr subtitle integration", "## 9. Bazarr subtitle integration"),
    ("## 9. Diagnostics and optional VFS", "## 10. Diagnostics and optional VFS"),
    ("## 10. Evidence summary", "## 11. Evidence summary"),
]:
    replace("docs/ANDROID_KODI_VALIDATION.md", old, new)
replace(
    "docs/ANDROID_KODI_VALIDATION.md",
    "| Episode parent-series identity / season zero | PASS/FAIL | |\n",
    "| Episode parent-series identity / season zero | PASS/FAIL | |\n| Episode-tile Delete & Replace / queued recovery | PASS/FAIL | |\n",
)
replace(
    "docs/RELEASE_CHECKLIST.md",
    "- [ ] Episode actions resolve the parent series through Kodi TV-show metadata, including season zero and API-backend/no-mapping use.\n",
    "- [ ] Episode actions resolve the parent series through Kodi TV-show metadata, including season zero and API-backend/no-mapping use.\n- [ ] Episode Delete & Replace uses Kodi-valid `showtitle`, minimal/season-scoped linked-row enumeration and makes no Servarr mutation after a failed Kodi preflight.\n- [ ] Accepted replacement searches report queued command evidence without waiting for indexer completion; safety-critical rescans still require terminal success.\n- [ ] Already-missing movie/episode recovery queues only the exact search and does not repeat blocklisting, deletion or Kodi cleanup.\n",
)
