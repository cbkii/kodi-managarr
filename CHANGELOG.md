# Changelog

## 0.2.0 — unreleased

- Added Kodi-native Status, Search & download, Monitoring, quality-profile and Download queue controls.
- Added queue removal without blocklisting.
- Added strict API response validation and bounded HTTP bodies.
- Added same-origin redirect protection for API-key requests.
- Fixed empty-path root matching and made SMB path comparison case-sensitive.
- Protected configured mapping roots automatically.
- Added complete multi-file VFS preflight and duplicate-target rejection.
- Required successful Servarr command results, including orphaned-command handling.
- Added persistent non-secret transaction-stage reporting and precomputed Kodi cleanup limited to affected episode-file relationships.
- Localised runtime dialogs, confirmations, results and error summaries.
- Added remote-friendly progress and pre-commit cancellation for multi-file operations.
- Migrated to Kodi Matrix+ settings schema.
- Added opaque icon, fanart, `LICENSE.txt`, reproducible packaging and release-workflow hardening.
