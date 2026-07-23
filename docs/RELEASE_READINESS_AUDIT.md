# Android Kodi release-readiness audit

This document records the completed two-pass release-readiness audit of Kodi Managarr for Kodi 19+ on Android. Each item is classified as **Implemented**, **Verified**, **Post-merge device validation** or **Not applicable** so repository readiness is unambiguous.

## Destructive safety and defaults

- **Implemented:** Fresh installations enable **Dry run** by default in both the settings schema and runtime fallback. Existing explicit saved values remain authoritative.
- **Verified:** Regression tests cover unset, explicit true and explicit false values and the packaged XML default.
- **Verified:** Existing delete/exclude/replace preflight, confirmation, PIN, API-authority, transaction and VFS fail-closed boundaries were preserved.

## Kodi episode-to-series identity

- **Implemented:** Episode `uniqueid.tvdb` remains episode identity and is never reused as the parent-series TVDb ID.
- **Implemented:** `SelectedItem` stores separate parent-series unique IDs and year.
- **Implemented:** Episode selections and playing subtitle items obtain parent identity through `VideoLibrary.GetTVShowDetails` using the existing JSON-RPC adapter.
- **Implemented:** A transient parent-detail JSON-RPC failure falls back to available episode metadata; downstream Sonarr resolution still rejects insufficient or ambiguous identity.
- **Implemented:** Core Sonarr resolution, Request & Search and Bazarr subtitles use the parent-series fields.
- **Verified:** Tests cover stable parent TVDb resolution without path mapping, distinct episode/series IDs, season-zero identity and transient parent-detail failure.
- **Post-merge device validation:** Repeat on Android Kodi with a skin/view exposing incomplete list-item metadata.

## International-title compatibility

- **Implemented:** Title normalisation uses Unicode NFKD decomposition, removes combining marks, case-folds text and retains all Unicode alphanumeric scripts.
- **Verified:** Tests cover accented/decomposed Latin, `Straße` case-fold expansion, punctuation/whitespace, Turkish dotted I, CJK, Cyrillic, numeric and null inputs.

## Registry and entrypoint correctness

- **Implemented:** `default.py` is a thin adapter and the obsolete parallel interactive entrypoint was removed.
- **Implemented:** Registry modes are derived from `ACTION_REGISTRY`; only explicit utility modes and documented aliases remain separate.
- **Implemented:** Normal and query-style arguments are parsed with URL decoding.
- **Verified:** Validation rejects registry/dispatcher drift, invalid aliases and obsolete runtime modules. Tests cover direct dispatch and encoded arguments.
- **Verified:** Destructive menu and direct modes still pass through the same central `authorize_action()` PIN boundary.

## Bazarr subtitle correctness and Android safety

- **Implemented:** A base language accepts normal, forced and hearing-impaired variants; a qualified language accepts only its exact qualifier. Configured order and the three-language maximum are preserved.
- **Implemented:** The subtitle plugin reports explicit directory success/failure and disables result caching.
- **Implemented:** Cached result payloads contain stable IDs and sanitised exact provider identity only; media paths, service URLs and credentials are excluded.
- **Implemented:** Tokens are atomically consumed before the non-idempotent provider request, preventing replay. Payload type, age, media type, IDs, language and safe provider identity are validated.
- **Implemented:** Current playback type/database ID is revalidated before download submission; only an existing Kodi-accessible or safely mapped path is returned.
- **Verified:** Tests cover qualifier ordering, exact qualified filtering, cache replay, malformed payloads, playing parent-series identity, transient parent-detail failure and plugin success/failure completion.
- **Post-merge device validation:** Verify exact provider download and subtitle loading on Android Kodi against the configured Bazarr version and storage mapping.

## Release metadata and compatibility contract

- **Implemented:** The untagged feature target is `1.2.0`, newer than published `v1.1.1`.
- **Implemented:** `CHANGELOG.md` and `addon.xml` contain concise consolidated user-facing changes since v1.1.1.
- **Verified metadata limits:** Kodi's `<news>` advisory limit is enforced at **1500** characters. Project-defined UI limits are **160** characters for summary and **1000** for description; each required field must be present and nonempty.
- **Verified:** The owner-controlled release workflow remains direct and does not impose mandatory RC promotion or approval ceremony.
- **Verified:** Public release naming remains `managarr-addon_vX.Y.Z.zip`; internal packaging remains `context.arr.manager/`.

## Compatibility matrix

| Layer | Status | Contract |
|---|---|---|
| Kodi runtime | Supported | Kodi 19+ with the `xbmc.python` 3.0.0/Python 3 add-on API |
| Android Kodi | Supported target | Kodi 19+ Android installations; device evidence follows the validation runbook after merge |
| Kodi 18 / Python 2 | Unsupported | The add-on uses Kodi Matrix+ settings and Python 3 APIs |
| Host validation | Verified in CI | CPython 3.8 and 3.12 for pure Python, tests and packaging tools |
| Optional services/backends | Conditional | Exact configured Radarr/Sonarr/Prowlarr/Bazarr/SMB/SFTP versions and paths must be device-tested before being claimed |

The CPython 3.8/3.12 host matrix is not a claim that every Android Kodi build embeds those exact interpreter versions.

## Validation, packaging and documentation

- **Implemented:** Validation detects unsafe fresh-install defaults, metadata overflow, registry/dispatcher drift, invalid aliases, malformed localisation and obsolete runtime modules.
- **Implemented:** Packaging rejects obsolete modules, symlinks, hidden/unexpected files and unsafe archive contents; tests/docs/scripts/bytecode/generated output remain excluded.
- **Verified:** Deterministic ZIP output, safe non-executable permissions, one internal root and Kodi subtitle registration are retained.
- **Verified in CI:** Python 3.8 and 3.12 validation, Ruff, complete unit tests, release-version regression, deterministic packaging, archive inspection, Kodi add-on checker and actionlint pass on the final PR head.
- **Implemented:** README, architecture, Android validation and release checklist document final behaviour and compatibility boundaries.
- **Post-merge device validation:** Execute `docs/ANDROID_KODI_VALIDATION.md`; no physical Android result is claimed by this repository audit.

## Non-goals

- **Not applicable:** P2 multi-instance/per-request routing, P3 reconciliation, Jellyseerr/Overseerr and general diagnostics expansion.
- **Not performed:** Release publication or tag creation.
- **Not assumed:** Android root, shell, desktop filesystem or external scheduler access.
