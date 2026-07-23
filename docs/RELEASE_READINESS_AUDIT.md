# Android Kodi release-readiness audit

This checklist records the two-pass audit of Kodi Managarr for Kodi 19+ on Android. It is intentionally limited to release health, compatibility, correctness and safety; it does not add unrelated product scope.

## Destructive safety and defaults

- [ ] Make **Dry run** enabled by default for fresh installations while preserving existing saved user settings.
- [ ] Add regression coverage proving the packaged settings schema retains the safe default.
- [ ] Preserve delete/exclude/replace preflight, confirmation, PIN, API-authority and VFS fail-closed boundaries.

## Kodi episode-to-series identity

- [ ] Stop treating an episode's `uniqueid.tvdb` as the parent-series TVDb ID.
- [ ] Add explicit parent-series unique IDs and year to selected-item state.
- [ ] Enrich episode selections through `VideoLibrary.GetTVShowDetails` using the existing JSON-RPC adapter.
- [ ] Use parent-series identity consistently in core actions, Request & Search and Bazarr subtitle resolution.
- [ ] Preserve exact fallback behaviour and reject ambiguous matches.
- [ ] Cover API-backend/no-path-mapping, season-zero and incomplete-metadata cases.

## International-title compatibility

- [ ] Replace ASCII-only title normalisation with Unicode-aware normalisation and case folding.
- [ ] Preserve punctuation and whitespace collapsing without deleting non-Latin alphanumeric scripts.
- [ ] Cover accented Latin, CJK and Cyrillic titles.

## Registry and entrypoint correctness

- [ ] Remove duplicated direct-mode routing between `default.py`, `entrypoints.py` and the interactive adapter.
- [ ] Make the central action registry the source of truth for dispatchable action modes.
- [ ] Preserve explicit utility modes and supported aliases.
- [ ] Correctly parse both `mode=value` and query-style `?mode=value` invocations with URL decoding.
- [ ] Prove every registry leaf is reachable through context, launcher and direct/Keymap invocation.
- [ ] Preserve the central destructive PIN boundary with no direct-mode bypass.
- [ ] Remove obsolete runtime modules from source and package output.

## Bazarr subtitle correctness and Android safety

- [ ] Apply one language/qualifier policy for base, forced and hearing-impaired variants.
- [ ] Preserve configured language order and the three-language maximum.
- [ ] Reject mismatched qualifier downloads safely.
- [ ] Report subtitle directory failures to Kodi and disable inappropriate result caching.
- [ ] Make download tokens single-use around the non-idempotent Bazarr provider request.
- [ ] Validate cached payload type, timestamps, stable IDs and provider-result identity.
- [ ] Keep media paths, service URLs and credentials out of cache state.
- [ ] Revalidate the currently playing Kodi database item before download submission.
- [ ] Return only an existing Kodi-accessible or safely mapped subtitle path.
- [ ] Cover entrypoint success/failure, replay and malformed-cache cases.

## Release metadata and compatibility contract

- [ ] Set an untagged feature-release target newer than published v1.1.1.
- [ ] Add a concise consolidated changelog entry for all changes since v1.1.1.
- [ ] Keep `addon.xml` summary, description and `<news>` accurate, user-facing and within Kodi limits.
- [ ] Keep the owner-controlled release workflow straightforward, without mandatory RC or approval ceremony.
- [ ] Preserve `managarr-addon_vX.Y.Z.zip` and the Kodi-required internal archive root.

## Validation, packaging and documentation

- [ ] Detect registry/dispatcher drift and unsafe fresh-install settings.
- [ ] Exclude dead modules, tests, docs, bytecode, hidden files and generated output from the package.
- [ ] Preserve deterministic ZIP output, safe permissions and archive-root validation.
- [ ] Pass Python 3.8 and 3.12 validation, Ruff, full unit tests, deterministic packaging, archive inspection, Kodi add-on checker and actionlint.
- [ ] Inspect complete CI logs and resolve all valid review threads.
- [ ] Update README, architecture, Android validation and release guidance.
- [ ] Document physical Android Kodi checks still outstanding without claiming they were performed.

## Non-goals

- No unrelated product features.
- No P2 multi-instance/per-request routing, P3 reconciliation, Jellyseerr/Overseerr or general diagnostics expansion.
- No release publication or tag creation.
- No Android root, shell, desktop filesystem or external scheduler assumptions.
