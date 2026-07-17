# Architecture

## Runtime boundaries

- `entrypoints.py` owns Kodi routing and native menus.
- `kodi.py` owns Kodi UI, selected-item extraction and targeted JSON-RPC synchronisation.
- `clients.py` and `http.py` own versioned Servarr transport and response validation.
- `resolver.py` resolves stable external IDs first, then mapped paths, then exact title/year evidence.
- `history.py` proves imported-release identity.
- `fileops.py` owns Kodi VFS inspection and deletion boundaries.
- `actions.py` owns preflight, transaction ordering, reconciliation and management operations.

## Management workflows

Status, search, monitoring, quality-profile and queue operations are executed entirely through localised Kodi-native dialogs and Servarr APIs. Movie profiles belong to Radarr movies; Sonarr profiles belong to series, so an episode-triggered profile change updates the parent series and says so explicitly.

Queue retrieval uses the product-specific `/queue` paging resource and stable movie/series filters. Removal calls `DELETE /queue/{id}` with `removeFromClient=true` and `blocklist=false` only after revalidating that the queue item still belongs to the selected media.

## Destructive planning

Direct VFS operations use a complete preflight plan before the first blocklist or deletion:

1. resolve one Servarr entity;
2. validate every file record and path;
3. map every remote path exactly once;
4. reject mapping roots, duplicates, protected paths and unsafe VFS entries;
5. prove imported-history evidence when strict mode is enabled;
6. confirm the exact action;
7. commit blocklist and deletion stages;
8. rescan and verify reconciliation;
9. run and verify replacement search;
10. apply a Kodi synchronisation plan that was resolved before mutation and contains only affected rows.

Transaction stages are persisted in the add-on profile without media paths, URLs or credentials. Failures state whether a destructive commit occurred and list completed stages.

## Servarr command completion

A command is accepted only when the initial response contains a valid command ID. Polling succeeds only when `status` is completed and `result` is successful. Failed, aborted, cancelled, orphaned, unsuccessful, indeterminate, malformed and timed-out commands are errors.

## Path identity

Missing paths are never converted to `/`. Scheme and host identity are normalised, but POSIX, SFTP and SMB path components retain case. Every configured Kodi-side mapping root is automatically protected against deletion.

## Publication

The package contains one `context.arr.manager/` root, `LICENSE.txt`, an opaque 512×512 icon, 1920×1080 fanart and runtime-only files. Packaging rejects symlinks, hidden files, bytecode and unexpected file types and is reproducible under `SOURCE_DATE_EPOCH`.
