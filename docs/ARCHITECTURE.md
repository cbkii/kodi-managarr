# Architecture

## Runtime boundaries

- `entrypoints.py` owns Kodi routing, registry-driven dispatch and native menus.
- `registry.py` is the central action-policy registry for menu presentation and direct invocation.
- `pin.py` owns local PIN validation, derivation, policy generation and authorisation.
- `kodi.py`, `kodi_ui.py` and `kodi_jsonrpc.py` own Kodi UI, selected-item extraction and targeted JSON-RPC synchronisation.
- `clients.py` and `http.py` own versioned Servarr transport and response validation.
- `resolver.py` resolves stable external IDs first, then mapped paths, then exact title/year evidence.
- `history.py` proves imported-release identity.
- `fileops.py` owns Kodi VFS inspection and deletion boundaries.
- `actions.py` and its mixins own preflight, transaction ordering, reconciliation and management operations.
- `retention/` owns retention configuration, eligibility, enumeration, execution, scheduling and sanitised reports.
- `context_manifest.py` defines the single Kodi context-root contract used by validation and packaging.

Kodi registers one plain ASCII **Managarr** context item. It opens a registry-driven Kodi-native runtime menu. Advanced is the upgrade-safe default; Simple reduces the visible set. Direct `RunScript(...,mode=...)` entrypoints use the same registry, media checks and authorisation path even when hidden.

## PIN policy

PIN protection applies to destructive media deletion, exclusion and replacement. Real manual retention cleanup and authorisation of real scheduled retention invoke the same central destructive authoriser conditionally; preview and dry-run paths do not prompt. A stable non-secret policy generation binds scheduled real authorisation to the current PIN state. Creating, changing, removing or corrupting the PIN invalidates that authorisation and disables real periodic cleanup.

A PIN is 4–8 numeric digits stored only as a random-salt PBKDF2-HMAC-SHA-256 derivative and compared in constant time. It is convenience protection, not a security boundary against local profile modification.

## Retention architecture

`RetentionSettings` is parsed without blocking unrelated features and is validated only when retention is invoked. The pure `RetentionPolicy` calculates complete-day age and supports watched-only, added/watched thresholds and all/any semantics. Missing, malformed or future timestamps fail closed; zero days remains an active immediate threshold.

`RetentionEnumerator` pages Kodi JSON-RPC movie/episode rows with only required fields. Stable movie and TV-show IDs are preferred. For episode rows, the parent TV-show identity is fetched separately so an episode-level TVDb ID is not mistaken for a Sonarr series ID. Series episode pages are bounded through a small LRU cache. A multi-episode physical file becomes one candidate containing all linked Kodi and Sonarr IDs.

The conservative added timestamp is the latest valid applicable Kodi/Servarr value. Multi-episode watched state requires every linked Kodi row to be watched and uses the latest linked last-played timestamp.

`RetentionExecutor` re-reads Kodi and Servarr state before each real deletion and requires the candidate identity and watched/age state to remain unchanged. It always uses Servarr APIs:

- movie: Radarr delete with files and import exclusion, then targeted Kodi synchronisation;
- episode file: validate the linked Sonarr episode set, unmonitor linked monitored episodes, delete the single file, restore monitoring when deletion fails before commit, then targeted Kodi synchronisation.

It never deletes a series, invokes replacement search or uses unattended VFS deletion. Transaction stages distinguish pre-commit and post-commit failures.

`RetentionService` provides preview, manual execution, scheduling and reports. Manual and scheduled execution share one lock. Scheduled passes use `xbmc.Monitor.waitForAbort`, rebuild settings/clients on every pass, enforce a batch cap, recheck enablement and PIN policy between candidates, and remember recent committed IDs to avoid replay after delayed Kodi cleanup. A token-owned atomic lock prevents a stale process from releasing a replacement lock.

State and reports are atomically written under the add-on profile, bounded and pruned. They may include display names and stable non-secret IDs but never paths, URLs, API keys or credentials. Background runs never open modal dialogs.

## Existing destructive and filesystem boundaries

The Servarr API backend remains the normal authority. Direct VFS operations retain complete preflight, mapping-root/protected-path rejection, confirmed-tree revalidation, parent-listing verification, Servarr reconciliation and targeted Kodi synchronisation. Retention is isolated from this direct VFS path.

## Publication

The release package contains one `context.arr.manager/` root, `service.py`, the retention runtime, `LICENSE.txt`, an opaque 512×512 icon, 1920×1080 fanart and runtime-only files. Packaging rejects symlinks, hidden files, bytecode and unexpected file types and is reproducible under `SOURCE_DATE_EPOCH`.

Stable releases are owner-controlled; RC promotion is optional. The GitHub Pages workflow validates an exact stable release and generates the private Kodi repository and checksums.
