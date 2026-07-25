# Replacement reliability

Kodi Managarr treats Radarr and Sonarr searches as asynchronous commands. A valid Servarr command ID means the search was accepted and queued; it does not mean indexer work finished during the Kodi context-menu invocation.

## Delete & Replace transaction model

1. Resolve the exact Kodi and Arr item/file.
2. Complete Kodi cleanup planning before any destructive request.
3. Match and fail/blocklist imported history where available.
4. Delete the exact file.
5. For direct VFS/SFTP deletion only, wait for the safety-critical Arr rescan and file-record reconciliation.
6. Submit the replacement search and record its command ID/status as queued.
7. Apply the precomputed targeted Kodi cleanup plan.

A replacement is not reported as failed merely because a queued search remains active beyond the normal polling timeout. Immediate command rejection or malformed command acceptance still fails the operation and is recorded accurately.

When a previous attempt already removed the selected movie or episode file, invoking Delete & Replace again performs a search-only recovery. It does not repeat deletion, history failure/blocklisting, or Kodi row removal.

## Episode-tile JSON-RPC contract

Kodi 19-22 episode details use `showtitle`, not `tvshowtitle`. Managarr requests:

- episode details: `title`, `season`, `episode`, `file`, `tvshowid`, `showtitle`, `uniqueid`;
- episode lists: only `season`, `episode`, `file`, optionally restricted to the selected season.

The selected row is validated first. A broad show query is avoided for ordinary single-episode files and used only to identify additional Kodi rows linked to a multi-episode Sonarr file. Ambiguous or contradictory rows fail closed before any Arr mutation.

## Diagnostics

`last-transaction.json` and generated diagnostics include only non-secret transaction evidence:

- completed and failed stages;
- destructive commit state;
- accepted Servarr command ID/status/result;
- Kodi JSON-RPC method/code and bounded safe parameter detail.

Media paths, service URLs, API keys and credentials are not persisted.

## Android validation

After installation on Android Kodi, use disposable media to verify:

1. Delete & Replace from a normal episode tile.
2. A season-zero special.
3. A multi-episode physical file and all linked Kodi rows.
4. A forced Kodi JSON-RPC preflight failure causes no Sonarr/Radarr mutation.
5. A long-running accepted search is reported as queued rather than failed.
6. A second invocation after the file is already missing queues recovery only.
7. Unrelated episodes and the parent TV-show row remain present.
