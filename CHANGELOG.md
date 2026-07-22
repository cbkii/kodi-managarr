# Changelog

## 1.2.0 — unreleased

- Added watched and age-aware retention previews and conditional deletion for movies and physical episode files.
- Added `0–9999` day thresholds since added/watched with all/any criteria and conservative timestamp selection.
- Added optional periodic cleanup through a shutdown-aware Kodi service, with dry-run default, batch caps, locking, sanitised reports and bounded replay protection.
- Integrated real manual/scheduled retention with the central destructive-action PIN policy and invalidated scheduled authorisation when PIN state changes.
- Added fresh Kodi/Servarr revalidation before every mutation, API-only deletion, multi-episode handling, monitoring rollback and targeted Kodi synchronisation.
- Expanded packaging, localisation, validation, tests and the Android Kodi runbook for retention.

## 1.1.1

- Added repository-based installation/updates, a configurable registry-driven menu and optional PIN protection for destructive media actions.
- Added clearer release metadata and public asset naming.

Earlier release history is available from the GitHub releases and commit history.
