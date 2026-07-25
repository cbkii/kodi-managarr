# Changelog

## 1.3.3 — 2026-07-26

- Rebuilt episode replacement reliability on the hardened retention base and corrected Kodi episode identity, asynchronous Servarr search acceptance, missing-file recovery and sanitised transaction evidence.
- Protected the Kodi subtitle-provider bootstrap so malformed invocation, import, search and download failures always close the subtitle directory cleanly.
- Aligned Bazarr movie and episode provider search/download requests with the authenticated `/api/providers/*` contract and added explicit unsupported-contract handling.
- Classified Bazarr authentication, permission, validation, connection, TLS, timeout, server and malformed-response failures without exposing URLs, API keys, payloads or private paths.
- Preserved forced, hearing-impaired and original-format flags with strict boolean parsing, bounded results to three configured languages, and preferred canonical Kodi `showtitle` episode identity.
- Enforced single-use subtitle result tokens, current-playback revalidation and Android-accessible delivery through verified Kodi paths, explicit mappings or newly visible SMB sidecars.
- Added read-only bounded Bazarr diagnostics, Kodi 21 empty-setting schema coverage and focused provider/delivery regression tests.

## 1.3.0 — 2026-07-25

- Added opt-in watched and age-aware retention previews, manual cleanup, bounded reports and optional periodic automation.
- Added explicit Kodi movie, episode, TV-series and season exclusions with fail-closed validation.
- Added configurable 0-10 movie-rating protection; unrated movies remain protected while the threshold is enabled.
- Revalidated Kodi and Radarr/Sonarr identity, file state and policy immediately before every API-only retention deletion.
- Protected shared multi-episode files unless every linked episode remains present and eligible.
- Defaulted movie/episode inclusion off and both manual and periodic retention to dry-run, with a hard per-pass deletion cap.
- Applied central PIN protection to real cleanup and periodic enablement, and invalidated periodic real-deletion authority after PIN changes.
- Added atomic locking, bounded non-secret reports, Kodi service packaging, Android-safe progress/cancellation and focused regression coverage.
- Hardened retention after full review with strict destructive-setting parsing, positive Arr/file IDs, duplicate physical-target protection, per-series Sonarr snapshots and fail-closed malformed timestamps.
- Added owned refreshable lock leases, unique atomic state/report writes, validated persistence schemas and a pre-armed scheduler safety hold so persistence failures cannot repeat a destructive pass.
- Rechecked periodic enable/PIN/dry-run state between targets, stopped in-flight passes after disablement, and reported committed Arr deletions accurately when later Kodi reconciliation fails.
- Kept linked Sonarr episodes unmonitored after an ambiguous episode-file DELETE failure to prevent automatic reacquisition of a file that may already have been removed.

## 1.2.0 — 2026-07-23

- Added smart **Request & Search** for managed or unmanaged movies, series and selected episodes.
- Added Arr-authoritative interactive release selection, a bounded service dashboard, optional read-only Prowlarr context and Kodi-native Bazarr subtitle search/download.
- Hardened episode-to-series identity through Kodi TV-show JSON-RPC metadata, including season-zero and no-path-mapping cases.
- Improved exact title matching for accented Latin, CJK, Cyrillic and other Unicode scripts.
- Centralised direct/Keymap dispatch in the action registry and removed the obsolete interactive entrypoint.
- Hardened subtitle language variants, provider-result identity, single-use download tokens, playback revalidation and Android-accessible path checks.
- Enabled **Dry run** by default for fresh installations while preserving existing saved settings.
- Expanded release validation, deterministic packaging and Android Kodi validation guidance.

## 1.1.0 — 2026-07-21

- Replaced the decorative context-menu glyph with the plain ASCII `Managarr` label for maximum Android Kodi skin/font compatibility.
- Centralised the expected context-menu structure across source validation, package validation and tests.
- Isolated inactive VFS configuration errors so API-backend actions remain usable while still failing closed when VFS is selected.
- Removed the installation-specific protected-path default; configured mapping roots remain protected automatically.
- Added the installed add-on version to normal Radarr/Sonarr HTTP User-Agent headers and rejected header-injection input.
- Reused one Kodi abort monitor per action instead of creating a monitor for every wait.
- Strengthened recursive Kodi VFS deletion by revalidating both files and directories and checking every removed folder against its parent listing.
- Added stateful VFS, configuration, HTTP and Kodi-runtime regression tests.
- Added a concise Android Kodi validation runbook and simplified owner-controlled stable release checklist.

## 1.0.2 — 2026-07-21

- Changed the root context-menu label to the compatible monochrome `⎘ Managarr` document marker.
- Added end-to-end tests proving every manifest action is forwarded by `context.py` and reaches the context dispatcher.
- Added validation for the exact root label, complete submenu grouping and generated ZIP menu/action structure.

## 1.0.1 — 2026-07-21

- Restored Kodi context-menu localisation by shipping the repaired PO message boundaries that were fixed after the v1.0.0 release was built.
- Replaced the unsupported colour-emoji submenu branding with the plain-text `Managarr` label.
- Added manifest regression coverage for the complete Kodi submenu tree and every registered action.

## 1.0.0

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
