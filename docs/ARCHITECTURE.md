# Architecture

## Runtime boundaries

- `entrypoints.py` owns Kodi routing, registry-driven dispatch, optional-service connection tests, menu configuration and PIN management.
- `registry.py` is the central action-policy registry for menu presentation and direct/Keymap invocation.
- `actions_interactive.py` owns Request & Search, release selection, Dashboard MVP and optional-service setup.
- `subtitle_service.py` owns playing-item resolution, Bazarr result filtering, single-use result tokens and Kodi-accessible subtitle retrieval; root `subtitles.py` is the thin `xbmc.subtitle.module` adapter.
- `kodi_selected.py` extracts the selected item and enriches an episode with its parent TV show's JSON-RPC identity.
- `pin.py` owns local PIN validation, derivation and authorisation.
- `kodi.py` owns Kodi UI, selected-item extraction and targeted JSON-RPC synchronisation.
- `clients.py`, `bazarr_client.py` and `http.py` own versioned service transport and response validation.
- `resolver.py` resolves stable external IDs first, then mapped paths, then exact Unicode-aware title/year evidence.
- `history.py`, `fileops.py` and the destructive action mixins retain imported-release, VFS and transaction safety boundaries.

Kodi UI waits reuse one `xbmc.Monitor` for an action. Interactive features perform bounded foreground calls; Dashboard is manually refreshed and does not install a polling service.

## Configuration and safety isolation

Radarr and Sonarr remain the media-management authorities. Prowlarr and Bazarr are disabled by default and validated only when used. Invalid inactive optional-service settings do not block core Arr actions. Prowlarr exposes status, health, indexer and informational-search operations only.

Fresh installs start with **Dry run** enabled. Existing saved settings survive upgrades. Destructive actions retain central PIN authorisation, confirmations, exact preflight, Servarr authority, VFS protections and non-secret transaction reporting.

Request & Search stores one root folder and quality profile per Arr service. These are minimal persistent defaults needed by native add endpoints, not P2 per-request/multi-instance routing.

## Menus and entrypoints

Kodi registers one plain ASCII **Managarr** context item. The runtime registry records stable action ID, localised label, group, order, media types, mutation/destructive classification and selected-item requirements. Advanced is the upgrade-safe default.

`default.py` is a thin adapter into `entrypoints.run_script()`. Registry modes are derived rather than duplicated, query-style arguments are URL-decoded, and direct/Keymap calls pass through the same selection and PIN boundary as menu calls. Obsolete parallel interactive routing is excluded from source and packages.

## Episode and series identity

Kodi episode unique IDs identify the episode and are not reused as parent-series IDs. For episode actions, Managarr obtains the Kodi TV-show database ID and calls `VideoLibrary.GetTVShowDetails` for the parent title, year and stable IDs. These fields are stored separately on `SelectedItem` and used by Sonarr resolution, Request & Search and Bazarr subtitle resolution.

This permits stable API-backend matching without path mappings, preserves season-zero specials and keeps exact fallback matching fail-closed. Unicode-aware normalisation retains accented Latin, CJK, Cyrillic and other alphanumeric scripts.

## Request & Search

For a managed item, Managarr reuses stable Arr identity, enables monitoring where required and starts the matching search. For an unmanaged item it:

1. requires persistent service defaults;
2. prefers TMDb/TVDb lookup syntax;
3. rejects no-result and ambiguous cases unless the user selects an exact candidate;
4. rechecks the library before adding to avoid races;
5. submits the native Radarr/Sonarr add payload with automatic search disabled;
6. re-resolves by stable identity;
7. searches the movie, series or selected episode;
8. reports add-success/search-failure as partial success rather than deleting the new record.

## Interactive releases and Prowlarr

Release search and grab use Radarr/Sonarr `/release`, preserving acceptance/rejection, quality, custom-format, indexer and download-client authority. The chosen release is re-fetched and identity-matched immediately before submission. Prowlarr is informational only and never downloads directly.

## Dashboard MVP

Dashboard calls cheap status, health, bounded queue and wanted resources. Optional-service failures are isolated so healthy services still display. No browser, full-library aggregation or persistent polling is used.

## Bazarr subtitle service

Bazarr is rooted at `/api`, not a Servarr version path. Up to three ordered unique language keys are stored. A base language accepts normal, forced and hearing-impaired variants; a qualified language accepts only its exact qualifier.

Kodi's subtitle module resolves the playing library movie/episode and parent TV show, filters Bazarr results, and emits the best exact provider result for each allowed variant. Cache state contains stable database IDs and sanitised provider identity only—never media paths, URLs or credentials. Download tokens are atomically consumed before the non-idempotent provider request, current playback is revalidated, and only an existing Kodi-accessible or safely mapped subtitle path is returned. The plugin closes its directory with explicit success/failure and disables result caching.

## Metadata, packaging and publication

Project-enforced English metadata limits are: summary 160 characters, description 1000 characters and news 1500 characters. The package contains one `context.arr.manager/` root, includes `subtitles.py`, excludes obsolete modules, tests, docs, bytecode and hidden/generated files, and remains deterministic with safe file permissions.

Host CI tests pure Python and packaging on CPython 3.8 and 3.12. Runtime support is Kodi 19+ with Kodi's Python 3 runtime; Kodi 18/Python 2 is unsupported. Stable release and GitHub Pages repository publication remain owner-controlled, and RC promotion is optional.
