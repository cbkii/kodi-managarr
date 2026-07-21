# Kodi Managarr

Kodi Managarr is a Kodi 19+ Python 3 context-menu add-on for managing Radarr movies and Sonarr series or episodes directly from Kodi's video library. It is designed for Android TV and uses Kodi-native dialogs and menus; it does not open a browser.

## Kodi-native actions

- **Status** — service, monitoring, quality-profile and file status for the selected item.
- **Search & download now** — queues and verifies the appropriate Radarr movie, Sonarr series or Sonarr episode search.
- **Monitoring** — monitor, unmonitor, or change quality profile. An episode quality-profile change is explicitly series-wide because Sonarr profiles are assigned to series.
- **Download queue** — view matching queue entries or remove one from Servarr and its download client without blocklisting it.
- **Delete & Exclude** — removes the selected movie/series, or deletes and unmonitors the selected episode file.
- **Delete & Replace** — proves and blocklists the imported release, deletes the file, reconciles Servarr, searches for a replacement and synchronises Kodi.

## Safety model

- Servarr API deletion is the default and recommended backend.
- Direct SMB/SFTP deletion uses Kodi VFS and Kodi-managed credentials.
- Direct deletion always requires confirmation, even if confirmation is disabled for API-only operations.
- Empty, malformed, root, share-root, mapping-root, protected, traversal and ambiguous paths fail closed.
- SMB path components are compared case-sensitively; scheme and host identity are normalised.
- Every multi-file direct operation validates every target before blocklisting or deleting anything.
- Servarr commands are successful only when the command has terminal `Completed` status and `Successful` result.
- Partial commits are persisted without secrets and reported with completed transaction stages.
- API keys and credential-bearing URLs are never written to diagnostics or logs.

## Install

1. Download `context.arr.manager-<version>.zip` from a GitHub release.
2. In Kodi, open **Add-ons → Install from zip file**.
3. Configure **My add-ons → Context menus → Kodi Managarr**.
4. Enter the Radarr and Sonarr URLs and API keys.
5. Run both connection tests.
6. Keep **Dry run** enabled for the first end-to-end validation.

The **Managarr** submenu appears for Kodi library movies, TV shows and episodes. The label intentionally uses plain text so it remains readable with Kodi fonts that do not include colour-emoji glyphs.

## Path mappings

Direct Kodi VFS deletion requires explicit mappings:

```text
/media/mediasmb/Movies=>smb://server/Movies;/media/mediasmb/Shows=>sftp://server:22/media/mediasmb/Shows
```

Every configured Kodi mapping root is protected automatically. The add-on may delete a validated child but never the mapping root itself or one of its ancestors.

## Keymap Editor

Keymap Editor exposes **Launch Kodi Managarr** under its Add-ons actions. The launcher presents Status, Search, Monitoring, Download queue, Delete actions, and Tools & settings for the currently highlighted library item.

Advanced keymaps may call a mode directly:

```xml
<key>RunScript(special://home/addons/context.arr.manager/default.py,mode=status)</key>
<key>RunScript(special://home/addons/context.arr.manager/default.py,mode=search_now)</key>
<key>RunScript(special://home/addons/context.arr.manager/default.py,mode=delete_replace)</key>
```

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

CI validates Python 3.8 and 3.12, action workflow syntax, image and metadata rules, tests, deterministic packaging, archive integrity and Kodi add-on checker results.

## Release status

Host-side tests do not replace real Android TV and live Servarr validation. Complete [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) against disposable media before publishing a stable release.

## Licence

GPL-3.0-or-later. See `LICENSE.txt`.
