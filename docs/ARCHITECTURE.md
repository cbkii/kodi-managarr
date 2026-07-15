# Architecture

## Kodi integration

`addon.xml` registers two context actions under the **(⁠●⁠_⁠_⁠●⁠) Managarr** submenu and exposes the add-on as the executable **Kodi Managarr** script. Kodi's documented `sys.listitem` object is used first; information-label fallbacks cover skins or builds that expose incomplete video tags.

Keymap Editor discovers enabled `xbmc.python.script` add-ons and generates one `RunAddon(addon_id)` action for each. It does not enumerate a context add-on's individual arguments. A no-argument Managarr launch therefore presents a focused Delete & Exclude / Delete & Replace chooser for the currently highlighted Kodi library item, while explicit `mode=delete_exclude` and `mode=delete_replace` arguments remain available to manually maintained keymaps.

## Resolution

The resolver uses stable external identifiers first:

- Radarr: TMDb ID.
- Sonarr: TVDb ID.

It then uses mapped file paths and exact normalised title/year matching. Ambiguous or low-confidence matches stop rather than selecting the first result.

## File deletion

The API backend is authoritative and recommended. Direct Kodi VFS backends use Kodi-managed SMB/SFTP URLs, queue the matching Servarr rescan command, poll the accepted command to completion, and only then poll until the corresponding file record is gone before any replacement search is queued.

Recursive folder deletion is used only by whole-movie/whole-series exclusion and is protected against root/share-root deletion.

## Release blocklisting

A Replace action first locates a `DownloadFolderImported` history event (`eventType=3`). Matching considers imported paths, dropped paths, source release titles, file names, episode IDs and download IDs. Before deletion, the add-on calls `POST /api/v3/history/failed/{id}` for every unique matched imported release. Servarr publishes its normal failed-download event, which creates the blocklist entry. Only after blocklisting succeeds does Managarr delete files, verify any direct-backend rescan reconciliation, and explicitly queue the requested search. Strict blocklist mode therefore cannot delete media without proven imported-history evidence.

## Episode exclusion

Sonarr's import-list exclusion model is series-level. For an episode item, Managarr first sets all episodes linked to that file to `monitored=false`, then deletes the episode file. If failure occurs before deletion is committed it restores monitoring; after confirmed deletion it preserves the safer unmonitored state and reports the failure stage. This correctly handles files containing multiple numbered episodes.

## Kodi library synchronisation

Destructive workflows use targeted Kodi JSON-RPC calls rather than a blind global library update. Movie and TV-show actions use the selected Kodi database ID for `VideoLibrary.RemoveMovie` or `VideoLibrary.RemoveTVShow`; episode actions remove the selected episode row with `VideoLibrary.RemoveEpisode`. If Kodi returns a JSON-RPC error after deletion is committed, the workflow reports Kodi synchronisation as a separate post-delete failure instead of claiming rollback.

## Non-strict replacement mode

When strict history matching is disabled, a file without an imported-history match may be deleted and searched without a blocklist call. Confirmation, dry-run and result text explicitly say that no release was blocklisted and that the same release may be reacquired. Duplicate history matches are collapsed by download ID before failed-history calls are made.

## Path and HTTP hardening

Path mapping parsing is strict: malformed entries, duplicate entries, overlapping remote roots and overlapping Kodi roots are rejected instead of silently ignored. Destructive path normalisation preserves POSIX and URL path case, rejects unsupported virtual schemes such as `videodb://`, `stack://` and `plugin://`, and rejects literal or encoded traversal/separator attempts before boundary checks.

The HTTP client validates absolute `http`/`https` base URLs without embedded credentials, validates API-version syntax such as `v3`, redacts logged URLs, rejects unexpected content types, and classifies invalid JSON as an API error. Polling loops retry only transient GET failures while preserving the original monotonic deadline.
