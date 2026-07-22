# Architecture

## Runtime boundaries

- `entrypoints.py` owns Kodi routing, registry-driven dispatch and native menus.
- `registry.py` is the central action-policy registry for menu presentation and direct invocation.
- `pin.py` owns local PIN validation, derivation and authorisation.
- `kodi.py` owns Kodi UI, selected-item extraction and targeted JSON-RPC synchronisation.
- `clients.py` and `http.py` own versioned Servarr transport and response validation.
- `resolver.py` resolves stable external IDs first, then mapped paths, then exact title/year evidence.
- `history.py` proves imported-release identity.
- `fileops.py` owns Kodi VFS inspection and deletion boundaries.
- `actions.py` owns preflight, transaction ordering, reconciliation and management operations.
- `context_manifest.py` defines the single Kodi context-root contract used by validation and packaging.

Kodi UI waits reuse one `xbmc.Monitor` for the lifetime of an action. This keeps cancellation and shutdown checks responsive without repeatedly creating monitor instances.

## Configuration isolation

The Servarr API backend is the default. Valid path mappings may still help entity resolution, but stale malformed VFS mapping text is treated as an inactive-backend warning rather than blocking API actions. VFS mapping and protected-path validation remains strict when the VFS backend is selected.

Configured Kodi-side mapping roots are always added to the protected set for VFS operations. Product defaults protect only the filesystem root; installation-specific media roots must be configured by the user.

## Menus and entrypoints

Kodi registers one plain ASCII **Managarr** context item for library movies, TV shows and episodes. It opens a Kodi-native runtime menu rather than a static manifest submenu.

The central action registry records each stable action ID, localised label, group, default mode and order, supported media types, mutation/destructive classification, selected-item requirement and dispatcher mode. **Advanced** is the upgrade-safe default so existing features are not silently hidden. **Simple** reduces the visible set. Stored visibility and ordering values are filtered against current registry IDs, and restore-defaults removes stale custom state.

Menu visibility is presentation only. Direct `RunScript(...,mode=...)` entrypoints use the same registry, media checks and authorisation path and remain callable for keymaps even when an action is hidden from the menu.

## PIN protection

PIN protection applies only to actions classified as destructive media deletion, exclusion or replacement. Queue removal remains protected by its existing explicit confirmation but is not PIN-gated.

A PIN is 4–8 numeric digits. It is stored only as a random-salt PBKDF2-HMAC-SHA-256 derivative and compared in constant time. Enablement is derived from one complete credential pair: absent credentials disable protection, while incomplete or malformed state fails closed and exposes a repair path. PIN protection is intended to prevent accidental local use, not to defend against a user who can alter Kodi's local add-on data.

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
12. apply a Kodi synchronisation plan resolved before mutation and containing only affected rows.

Transaction stages are persisted in the add-on profile without media paths, URLs or credentials. Failures state whether a destructive commit occurred and list completed stages.

## Servarr command completion

A command is accepted only when the initial response contains a valid command ID. Polling succeeds only when `status` is completed and `result` is successful. Failed, aborted, cancelled, orphaned, unsuccessful, indeterminate, malformed and timed-out commands are errors.

Normal Servarr requests identify the installed add-on version in a validated `Kodi-Managarr/<version>` User-Agent. Header control characters and unreasonable values fall back to a safe generic identity.

Sonarr episode-monitoring updates may use its verified bulk endpoint with validated, deduplicated IDs. Imported-history failure remains sequential because no supported bulk history-failure endpoint is assumed.

## Path identity

Missing paths are never converted to `/`. Scheme and host identity are normalised, but POSIX, SFTP and SMB path components retain case. Every configured Kodi-side mapping root is automatically protected against deletion.

## Publication

The release package contains one `context.arr.manager/` root, `LICENSE.txt`, an opaque 512×512 icon, 1920×1080 fanart and runtime-only files. Packaging rejects symlinks, hidden files, bytecode and unexpected file types and is reproducible under `SOURCE_DATE_EPOCH`.

Stable releases are owner-controlled. The manual workflow validates and packages the selected branch, while the Android Kodi runbook provides practical device evidence. A release-candidate promotion process is optional rather than mandatory.

## Repository and updates

A separate GitHub Pages workflow accepts only an exact stable release, validates its published add-on ZIP and deterministically generates `repository.managarr`, canonical Kodi repository paths, `addons.xml`, Kodi's MD5 change token and SHA-256 checksum files. Repository ZIPs are built outside their source directory to prevent self-inclusion and contain licence metadata and `LICENSE.txt`.

The pipeline packages and checksums repository content; it does not perform or claim cryptographic signing. Authenticity depends on the trusted GitHub release and HTTPS Pages origin.
