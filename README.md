# Kodi Managarr

Kodi Managarr is a Kodi 19+ Python 3 context-menu add-on for managing Radarr movies and Sonarr series or episodes directly from Kodi's video library. It is designed for Android TV, uses Kodi-native dialogs and menus, and never opens a browser.

## Kodi-native actions

- **Status** — service, monitoring, quality-profile and file status for the selected item.
- **Search & download now** — queues and verifies the appropriate Radarr movie, Sonarr series or Sonarr episode search.
- **Monitoring** — monitor, unmonitor, or change quality profile.
- **Download queue** — view matching queue entries or remove one without blocklisting.
- **Delete & Exclude** — removes the selected movie/series, or deletes and unmonitors the selected episode file.
- **Delete & Replace** — proves and blocklists the imported release, deletes the file, reconciles Servarr, searches for a replacement and synchronises Kodi.
- **Retention** — previews or conditionally deletes watched movies and episode files using added/watched age rules, manually or on an optional schedule.

## Safety model

- Servarr API deletion is the default and recommended backend.
- Direct SMB/SFTP deletion uses Kodi VFS and Kodi-managed credentials.
- Empty, malformed, root, share-root, mapping-root, protected, traversal and ambiguous paths fail closed.
- Every multi-file direct operation validates every target before blocklisting or deleting anything.
- Confirmed VFS folder plans are re-enumerated before deletion and removals are verified against parent listings.
- Servarr commands succeed only with terminal `Completed` status and `Successful` result.
- Partial commits are persisted without secrets and reported with completed transaction stages.
- API keys and credential-bearing URLs are never written to reports, diagnostics or logs.

## Install and automatic updates

1. Download `repository.managarr-X.Y.Z.zip` from the [project repository page](https://cbkii.github.io/kodi-managarr/).
2. Enable **Unknown sources** in Kodi settings if required.
3. Open **Add-ons → Install from zip file** and select the repository ZIP.
4. Open **Install from repository → Kodi Managarr Repository → Context menus** and install **Kodi Managarr**.
5. Leave Kodi's normal add-on auto-update setting enabled.
6. Configure **My add-ons → Context menus → Kodi Managarr**.
7. Enter the Radarr and Sonarr URLs and API keys and run both connection tests.
8. Keep **Dry run** enabled for the first end-to-end validation.

The repository publishes canonical Kodi filenames, `addons.xml`, Kodi's `addons.xml.md5` change token and SHA-256 checksum files. It validates the exact stable release ZIP before publication and does not claim cryptographic signing.

## Menu configuration and PIN protection

The plain-text **Managarr** root item appears for Kodi library movies, TV shows and episodes. **Advanced** is the upgrade-safe default and includes Retention; **Simple** keeps the common actions visible. **Configure menu** can hide or reorder registered actions and restore defaults. Hidden actions remain callable through direct `RunScript(...,mode=...)` key mappings.

**Manage PIN** can create, change or remove a local 4–8 digit numeric PIN. The PIN is salted and derived with PBKDF2-HMAC; plaintext is not stored. It protects real media-deletion actions, including manual real retention cleanup and enabling real periodic retention. Changing or removing the PIN disables previously authorised real periodic cleanup. This is convenience protection against accidental local use, not a boundary against a user who can edit Kodi's local add-on data.

## Retention cleanup

Retention is disabled by default and appears in Advanced mode. It supports:

- movies and physical episode files; whole-series automatic deletion is deliberately excluded;
- watched-only or any watched state;
- `0–9999` complete days since added;
- `0–9999` complete days since watched;
- **all** or **any** enabled age criteria;
- a preview, manual run, periodic enable/disable and last-report viewer;
- a configurable interval, maximum deletions per run and background notification policy;
- background dry-run enabled by default.

Added age uses the latest valid applicable timestamp so deletion cannot occur earlier than Kodi or Servarr indicates. For movies this considers Radarr movie `added`, Radarr movie-file `dateAdded` and Kodi `dateadded`; for episodes it considers Sonarr episode-file `dateAdded` and all linked Kodi episode `dateadded` values. Multi-episode files are considered watched only when every linked Kodi episode row is watched, and watched age uses the most recent linked `lastplayed` timestamp.

Every real candidate is freshly re-read from Kodi and Servarr before mutation. Identity, watched state and age changes fail closed. Retention always deletes through Radarr/Sonarr APIs, never unattended Kodi VFS/SMB/SFTP recursion. Movie retention uses Radarr deletion with import exclusion. Episode retention unmonitors every Sonarr episode linked to the physical file, deletes that one file, restores monitoring if pre-commit deletion fails, and performs targeted Kodi synchronisation. Retention never runs Delete & Replace or searches for replacement media.

The Kodi startup service uses `xbmc.Monitor.waitForAbort`, does no busy polling, avoids overlapping runs, limits each batch and stores only sanitised bounded state/reports under the add-on profile. Manual cleanup follows the global **Dry run** setting; scheduled cleanup follows **Background dry run**.

## Path mappings

Direct Kodi VFS deletion requires explicit mappings such as:

```text
/media/mediasmb/Movies=>smb://server/Movies;/media/mediasmb/Shows=>sftp://server:22/media/mediasmb/Shows
```

Every configured Kodi mapping root is protected automatically. Retention itself does not use VFS deletion.

## Keymap Editor

Keymap Editor exposes **Launch Kodi Managarr** under Add-ons actions. Advanced keymaps may call modes directly, including:

```xml
<key>RunScript(special://home/addons/context.arr.manager/default.py,mode=status)</key>
<key>RunScript(special://home/addons/context.arr.manager/default.py,mode=retention_preview)</key>
<key>RunScript(special://home/addons/context.arr.manager/default.py,mode=retention_run)</key>
```

Direct retention modes use the same conditional PIN and safety policy as menu/settings invocation.

## Development validation

```bash
python -m pip install -r requirements-dev.txt
python scripts/validate.py
ruff check .
python -m unittest discover -s tests -v
SOURCE_DATE_EPOCH=1700000000 python scripts/package.py
rm -rf dist/addon-check && mkdir -p dist/addon-check
python - <<'PY'
import zipfile
from pathlib import Path
archive = next(Path('dist').glob('context.arr.manager-*.zip'))
with zipfile.ZipFile(archive) as handle:
    handle.extractall('dist/addon-check')
PY
kodi-addon-checker --branch matrix dist/addon-check/context.arr.manager
```

CI runs validation on Python 3.8 and 3.12, Ruff, actionlint, deterministic packaging, archive inspection and Kodi add-on checker. Host-side tests do not replace a real Android Kodi run; use [`docs/ANDROID_KODI_VALIDATION.md`](docs/ANDROID_KODI_VALIDATION.md) with disposable media.

## Licence

GPL-3.0-or-later. See `LICENSE.txt`.
