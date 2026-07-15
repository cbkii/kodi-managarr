# Architecture

## Kodi integration

`addon.xml` registers two context actions under an **Arr Manager** submenu and also exposes an executable script used for settings tests and diagnostics. Kodi's documented `sys.listitem` object is used first; information-label fallbacks cover skins or builds that expose incomplete video tags.

## Resolution

The resolver uses stable external identifiers first:

- Radarr: TMDb ID.
- Sonarr: TVDb ID.

It then uses mapped file paths and exact normalised title/year matching. Ambiguous or low-confidence matches stop rather than selecting the first result.

## File deletion

The API backend is authoritative and recommended. Direct Kodi VFS backends use Kodi-managed SMB/SFTP URLs, queue the matching Servarr rescan command, poll the accepted command to completion, and only then poll until the corresponding file record is gone before any replacement search is queued.

Recursive folder deletion is used only by whole-movie/whole-series exclusion and is protected against root/share-root deletion.

## Release blocklisting

A Replace action first locates a `DownloadFolderImported` history event (`eventType=3`). Matching considers imported paths, dropped paths, source release titles, file names, episode IDs and download IDs. Before deletion, the add-on calls `POST /api/v3/history/failed/{id}` for every unique matched imported release. Servarr publishes its normal failed-download event, which creates the blocklist entry. Only after blocklisting succeeds does the add-on delete files, verify any direct-backend rescan reconciliation, and explicitly queue the requested search. Strict blocklist mode therefore cannot delete media without proven imported-history evidence.

## Episode exclusion

Sonarr's import-list exclusion model is series-level. For an episode item, the add-on first sets all episodes linked to that file to `monitored=false`, then deletes the episode file. If failure occurs before deletion is committed it restores monitoring; after confirmed deletion it preserves the safer unmonitored state and reports the failure stage. This correctly handles files containing multiple numbered episodes.
