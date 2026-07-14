# Architecture

## Kodi integration

`addon.xml` registers two context actions under an **Arr Manager** submenu and also exposes an executable script used for settings tests and diagnostics. Kodi's documented `sys.listitem` object is used first; information-label fallbacks cover skins or builds that expose incomplete video tags.

## Resolution

The resolver uses stable external identifiers first:

- Radarr: TMDb ID.
- Sonarr: TVDb ID.

It then uses mapped file paths and exact normalised title/year matching. Ambiguous or low-confidence matches stop rather than selecting the first result.

## File deletion

The API backend is authoritative and recommended. Direct VFS/SFTP backends delete the file first, issue a Servarr rescan command, and poll until the corresponding file record is gone before searching.

Recursive folder deletion is used only by whole-movie/whole-series exclusion and is protected against root/share-root deletion.

## Release blocklisting

A Replace action first locates a `DownloadFolderImported` history event (`eventType=3`). Matching considers imported paths, dropped paths, source release titles, file names, episode IDs and download IDs. After deletion, the add-on calls `POST /api/v3/history/failed/{id}`. Servarr publishes its normal failed-download event, which creates the blocklist entry; the add-on then explicitly queues the requested search.

## Episode exclusion

Sonarr's import-list exclusion model is series-level. For an episode item, the add-on deletes the episode file and sets all episodes linked to that file to `monitored=false`. This correctly handles files containing multiple numbered episodes.
