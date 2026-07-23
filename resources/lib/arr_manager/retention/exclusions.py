# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import time

from ..errors import SafetyError


class RetentionExclusions:
    SCHEMA = 1

    def __init__(self, profile):
        self.path = os.path.join(profile, "retention_exclusions.json")

    def load(self):
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            raise SafetyError("Retention exclusions could not be read safely") from exc
        if not isinstance(data, dict) or data.get("schema") != self.SCHEMA:
            raise SafetyError("Retention exclusions use an unsupported or malformed schema")
        rows = data.get("entries")
        if not isinstance(rows, list):
            raise SafetyError("Retention exclusions are malformed")
        clean = []
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise SafetyError("Retention exclusions are malformed")
            key = str(row.get("key") or "").strip()
            label = str(row.get("label") or "").strip()
            scope = str(row.get("scope") or "").strip()
            if not key or scope not in {"movie", "series", "season"} or key in seen:
                raise SafetyError("Retention exclusions contain an invalid entry")
            if "://" in key or "\n" in key or "\r" in key:
                raise SafetyError("Retention exclusions contain an unsafe key")
            seen.add(key)
            clean.append({"key": key, "label": label[:200], "scope": scope})
        return clean

    def _save(self, entries):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        temporary = self.path + ".tmp"
        payload = {"schema": self.SCHEMA, "updated": int(time.time()), "entries": entries}
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, self.path)

    def add(self, key, label, scope):
        entries = self.load()
        if any(row["key"] == key for row in entries):
            return False
        entries.append({"key": str(key), "label": str(label)[:200], "scope": scope})
        entries.sort(key=lambda row: (row["scope"], row["label"].lower(), row["key"]))
        self._save(entries)
        return True

    def remove(self, key):
        entries = self.load()
        kept = [row for row in entries if row["key"] != key]
        if len(kept) == len(entries):
            return False
        self._save(kept)
        return True

    def is_excluded(self, candidate):
        keys = {candidate.stable_key}
        if candidate.media_type == "episode":
            keys.update({candidate.series_key, candidate.season_key})
        return next((row for row in self.load() if row["key"] in keys), None)
