# Architecture

## Runtime boundaries

- `entrypoints.py` owns established Kodi routing, registry-driven dispatch, menu configuration and PIN management.
- `interactive_entrypoint.py` adds non-destructive interactive/settings modes without replacing the hardened entrypoint path.
- `registry.py` is the central action-policy registry for menu presentation and direct invocation.
- `actions_interactive.py` owns Request & Search, release selection, Dashboard MVP and optional service setup.
- `subtitle_service.py` owns playing-item resolution, Bazarr result filtering, short-lived result tokens and Kodi-accessible subtitle retrieval; root `subtitles.py` is the thin `xbmc.subtitle.module` adapter.
- `pin.py` owns local PIN validation, derivation and authorisation.
- `kodi.py` owns Kodi UI, selected-item extraction and targeted JSON-RPC synchronisation.
- `clients.py` and `http.py` own versioned service transport and response validation.
- `resolver.py` resolves stable external IDs first, then mapped paths, then exact title/year evidence.
- `history.py`, `fileops.py` and the destructive action mixins retain imported-release, VFS and transaction safety boundaries.

Kodi UI waits reuse one `xbmc.Monitor` for the lifetime of an action. Interactive features perform bounded foreground calls; the Dashboard is manually refreshed and does not install a polling service.

## Configuration isolation

Radarr and Sonarr remain the media-management authorities. Prowlarr and Bazarr are disabled by default and validated only when used. Invalid inactive optional-service settings do not block core Arr actions. Prowlarr exposes only status, health, indexer and informational-search operations; it has no media, download-grab, blocklist or deletion methods.

Request & Search stores one root folder and quality profile per Arr service. These are minimal persistent defaults needed by native add endpoints, not P2 per-request/multi-instance routing.

## Menus and entrypoints

Kodi registers one plain ASCII **Managarr** context item. The runtime registry records stable action IDs, localised labels, group, order, media types, mutation/destructive classification and selected-item requirements. Advanced is the upgrade-safe default. Direct keymap modes use the same action and authorisation path even when hidden from menus.

The interactive actions are registered at the root to avoid unsupported deep manifest nesting. Search, Dashboard and subtitle actions remain non-destructive and do not request the media-deletion PIN. Release grab still requires an explicit confirmation.

## Request & Search

For a managed item, Managarr reuses stable Arr identity, enables monitoring where required and starts the matching search. For an unmanaged item it:

1. requires the persistent service defaults;
2. prefers TMDb/TVDb lookup syntax;
3. rejects no-result and ambiguous cases unless the user selects an exact candidate;
4. submits the native Radarr/Sonarr add payload with automatic search disabled;
5. re-resolves by stable identity to prevent duplicates/races;
6. searches the movie, series or selected episode;
7. reports add-success/search-failure as partial success rather than deleting the new Arr record.

## Interactive releases and Prowlarr

Release search and grab use Radarr/Sonarr `/release`, preserving their acceptance/rejection, quality, custom-format, indexer and download-client authority. The chosen release is re-fetched and identity-matched immediately before submission. Prowlarr search is informational only when Arr has no result and never downloads directly.

## Dashboard MVP

Dashboard calls cheap status, health, bounded queue and one-record wanted resources. Optional service failures are isolated so healthy services still display. No browser, full-library aggregation or persistent polling is used.

## Bazarr subtitle service

Bazarr is rooted at `/api`, not a Servarr version path. Current integration uses system languages, provider-search resources and movie/episode subtitle download resources. Up to three ordered unique language keys are stored, including forced/HI qualifiers where configured.

Kodi's subtitle module resolves the playing library movie/spisode, resolves it to Radarr/Sonarr, filters Bazarr results and emits one selectable best-match entry per configured language/flag combination. A random short-lived profile token carries only sanitised result context. Selection asks Bazarr to download the language/flag combination, then returns a path only when it is already Kodi-accessible or safely mapped. Server filesystem paths are never handed directly to Android Kodi.

## Destructive safety

Existing Delete & Exclude/Delete & Replace planning, PIN scope, VFS protections, transaction state and targeted Kodi synchronisation remain unchanged. Optional interactive services do not gain deletion authority.

## Publication

The release package contains one `context.arr.manager/` root and now includes `subtitles.py` plus its declared `xbmc.subtitle.module` extension. Packaging remains deterministic and rejects symlinks, hidden files, bytecode and unexpected file types. Stable release and GitHub Pages repository publication remain owner-controlled; RC promotion is optional.
