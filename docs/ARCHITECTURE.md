# Architecture

## Runtime boundaries

- `entrypoints.py` owns Kodi routing and native menus.
- `kodi.py` owns Kodi UI, selected-item extraction and targeted JSON-RPC synchronisation.
- `clients.py` and `http.py` own versioned Servarr transport and response validation.
- `resolver.py` resolves stable external IDs first, then mapped paths, then exact title/year evidence.
- `history.py` proves imported-release identity.
- `fileops.py` owns Kodi VFS inspection and deletion boundaries.
- `actions.py` owns preflight, transaction ordering, reconciliation and management operations.
- `context_manifest.py` is the single source of truth for the required context-menu label, actions and submenu grouping used by validation and packaging.

Kodi UI waits reuse one `xbmc.Monitor` for the lifetime of the action. This keeps cancellation and shutdown checks responsive without repeatedly creating monitor instances.

## Configuration isolation

The Servarr API backend is the default. Valid path mappings may still help entity resolution, but stale malformed VFS mapping text is treated as an inactive-backend warning rather than blocking API actions. VFS mapping and protected-path validation remains strict when the VFS backend is selected.

Configured Kodi-side mapping roots are always added to the protected set for VFS operations. Product defaults protect only the filesystem root; installation-specific media roots must be configured by the user.

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
7. re-enumerate the complete VFS tree and require both file and directory sets to match the confirmed plan;
8. commit blocklist and deletion stages;
9. verify every removed file and directory against its parent listing;
10. rescan and verify reconciliation;
11. run and verify replacement search;
12. apply a Kodi synchronisation plan that was resolved before mutation and contains only affected rows.

Transaction stages are persisted in the add-on profile without media paths, URLs or credentials. Failures state whether a destructive commit occurred and list completed stages.

## Servarr command completion

A command is accepted only when the initial response contains a valid command ID. Polling succeeds only when `status` is completed and `result` is successful. Failed, aborted, cancelled, orphaned, unsuccessful, indeterminate, malformed and timed-out commands are errors.

Normal Servarr requests identify the installed add-on version in a validated `Kodi-Managarr/<version>` User-Agent. Header control characters and unreasonable values fall back to a safe generic identity.

## Path identity

Missing paths are never converted to `/`. Scheme and host identity are normalised, but POSIX, SFTP and SMB path components retain case. Every configured Kodi-side mapping root is automatically protected against deletion.

## Publication

The package contains one `context.arr.manager/` root, `LICENSE.txt`, an opaque 512×512 icon, 1920×1080 fanart and runtime-only files. Packaging rejects symlinks, hidden files, bytecode and unexpected file types and is reproducible under `SOURCE_DATE_EPOCH`.

Stable releases are owner-controlled. The manual workflow validates and packages the selected branch, while the concise Android Kodi runbook provides practical device evidence. A release-candidate promotion process is optional rather than mandatory.
