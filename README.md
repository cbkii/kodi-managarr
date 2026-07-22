# Kodi Managarr

Kodi Managarr is a Kodi 19+ Python 3 context-menu add-on for managing Radarr movies and Sonarr series or episodes directly from Kodi's video library. It is designed for Android TV and uses Kodi-native dialogs and menus; it does not open a browser.

## Kodi-native actions

- **Status** — service, monitoring, quality-profile and file status for the selected item.
- **Search & download now** — queues and verifies the appropriate Radarr movie, Sonarr series or Sonarr episode search.
- **Monitoring** — monitor, unmonitor, or change quality profile. An episode quality-profile change is series-wide because Sonarr profiles are assigned to series.
- **Download queue** — view matching queue entries or remove one from Servarr and its download client without blocklisting it.
- **Delete & Exclude** — removes the selected movie/series, or deletes and unmonitors the selected episode file.
- **Delete & Replace** — proves and blocklists the imported release, deletes the file, reconciles Servarr, searches for a replacement and synchronises Kodi.

## Safety model

- Servarr API deletion is the default and recommended backend.
- Direct SMB/SFTP deletion uses Kodi VFS and Kodi-managed credentials.
- Direct deletion always requires confirmation, even if confirmation is disabled for API-only operations.
- Empty, malformed, root, share-root, mapping-root, protected, traversal and ambiguous paths fail closed.
- Every multi-file direct operation validates every target before blocklisting or deleting anything.
- Confirmed VFS folder plans are re-enumerated before deletion and removals are verified against parent listings.
- Servarr commands succeed only with terminal `Completed` status and `Successful` result.
- Partial commits are persisted without secrets and reported with completed transaction stages.
- API keys and credential-bearing URLs are never written to diagnostics or logs.

## Install and automatic updates

1. Download `repository.managarr-X.Y.Z.zip` from the [project repository page](https://cbkii.github.io/kodi-managarr/).
2. Enable **Unknown sources** in Kodi settings if required.
3. Open **Add-ons → Install from zip file** and select the repository ZIP.
4. Open **Install from repository → Kodi Managarr Repository → Context menus** and install **Kodi Managarr**.
5. Leave Kodi's normal add-on auto-update setting enabled. Stable releases are then offered through the repository.
6. Configure **My add-ons → Context menus → Kodi Managarr**.
7. Enter the Radarr and Sonarr URLs and API keys.
8. Run both connection tests.
9. Keep **Dry run** enabled for the first end-to-end validation.

The repository publishes canonical Kodi filenames, `addons.xml`, Kodi's `addons.xml.md5` change token and SHA-256 checksum files. It validates the exact stable release ZIP before publication and does not claim cryptographic signing.

## Menu configuration

The plain-text **Managarr** root item appears for Kodi library movies, TV shows and episodes. It intentionally avoids emoji and decorative Unicode glyphs so it remains readable across Android Kodi skins and font packages.

**Advanced** is the upgrade-safe default and preserves every existing action. **Simple** keeps the common actions visible while reducing menu depth. **Configure menu** can hide or reorder registered actions and restore defaults using Kodi-native TV-remote dialogs. Hiding an action affects menu presentation only; direct `RunScript(...,mode=...)` key mappings remain callable.

## PIN protection

**Manage PIN** can create, change, remove or repair a local 4–8 digit numeric PIN. The PIN is salted and derived with PBKDF2-HMAC; plaintext is not stored. It protects media deletion, exclusion and replacement actions, including direct-mode invocations. Queue removal retains its existing explicit confirmation and is not PIN-protected. This protects against accidental local use; it is not a boundary against a user who can modify Kodi's local add-on data.

## Path mappings

Direct Kodi VFS deletion requires explicit mappings:

```text
/media/mediasmb/Movies=>smb://server/Movies;/media/mediasmb/Shows=>sftp://server:22/media/mediasmb/Shows
```

Every configured Kodi mapping root is protected automatically. The add-on may delete a validated child but never the mapping root itself or one of its ancestors. VFS-only configuration errors do not block normal API-backend operation, but they must be repaired before switching to the VFS backend.

## Keymap Editor

Keymap Editor exposes **Launch Kodi Managarr** under its Add-ons actions. The launcher presents the configured native menu for the currently highlighted library item.

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

Validation checks the exact ASCII `Managarr` label, single runtime context root, registry dispatch, localisation, PIN policy, repository-generation safety and generated ZIP structure. CI runs these gates on Python 3.8 and 3.12 alongside actionlint, Ruff, deterministic packaging, archive integrity and Kodi add-on checker.

## Android Kodi validation and release

Host-side tests do not replace a real Android Kodi run. Use the [`Android Kodi validation runbook`](docs/ANDROID_KODI_VALIDATION.md) with disposable media and attach its completed evidence summary to the release or PR.

A release candidate is optional. The manual release workflow may publish a stable, prerelease or draft build whenever the owner chooses; the practical release gate is a green CI run plus the applicable checks in [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md).

## Licence

GPL-3.0-or-later. See `LICENSE.txt`.
