# Kodi Managarr

Kodi Managarr is a Kodi 19+ Python 3 add-on for managing Radarr, Sonarr and optional companion services directly from Kodi's video library. It is designed for Android TV, uses Kodi-native dialogs and menus, and never opens a browser.

## Kodi-native actions

- **Request & Search** - searches an existing Arr item or adds an unmanaged Kodi movie/show using exact identity and one persistent root/profile default per service, then starts the appropriate search.
- **Search & download now** - queues and verifies the appropriate Radarr movie, Sonarr series or Sonarr episode search.
- **Interactive search** - presents Radarr/Sonarr release results, rejection reasons and metadata, then revalidates and grabs the selected release through Arr.
- **Status and Dashboard** - selected-item status plus a bounded, manually refreshed service/health/queue/wanted summary.
- **Monitoring** - monitor, unmonitor, or change quality profile. An episode quality-profile change is series-wide because Sonarr profiles are assigned to series.
- **Download queue** - view matching queue entries or remove one from Servarr and its download client without blocklisting it.
- **Subtitles** - use optional Bazarr integration from Kodi's built-in subtitle-search window with up to three ordered languages.
- **Delete & Exclude** - removes the selected movie/series, or deletes and unmonitors the selected episode file.
- **Delete & Replace** - proves and blocklists the imported release, deletes the file, reconciles Servarr, searches for a replacement and synchronises Kodi.

Prowlarr is optional and read-only from Managarr: it contributes indexer health and informational search context, but never bypasses Radarr/Sonarr download tracking or acts as a media/deletion authority.

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
3. Open **Add-ons -> Install from zip file** and select the repository ZIP.
4. Open **Install from repository -> Kodi Managarr Repository -> Context menus** and install **Kodi Managarr**.
5. Leave Kodi's normal add-on auto-update setting enabled.
6. Configure **My add-ons -> Context menus -> Kodi Managarr** and run the applicable connection tests.
7. Keep **Dry run** enabled for the first destructive end-to-end validation.

The repository publishes canonical Kodi filenames, `addons.xml`, Kodi's `addons.xml.md5` change token and SHA-256 checksum files. It validates the exact stable release ZIP before publication and does not claim cryptographic signing.

## Request & Search setup

Open **Configure Request & Search defaults** once. Managarr stores one Radarr and one Sonarr root folder and quality profile, plus one Sonarr monitoring mode. These are persistent defaults, not per-request routing: multi-instance, HD/4K and tag-routing policies remain outside this feature.

Existing items are never added twice. Stable TMDb/TVDb identity is preferred; exact title/year fallback is used only when necessary, and ambiguous lookup results require an explicit Kodi-native selection. An episode request adds the parent series when needed but searches only the selected episode.

## Optional Prowlarr and Bazarr

Prowlarr requires its URL/API key only when enabled. The Dashboard uses its status, health and indexer endpoints, and Interactive search may show an informational count when Arr returns no releases.

Bazarr requires its URL/API key and **Configure subtitle languages**. Choose one to three unique language codes in preference order. During movie or episode playback, open Kodi's normal subtitle-search dialog and choose Kodi Managarr/Bazarr. Selecting a result downloads that exact provider result through Bazarr, then Managarr returns only a Kodi-accessible mapped or sibling subtitle path.

## Menu configuration and PIN protection

The plain-text **Managarr** root item appears for Kodi library movies, TV shows and episodes. **Advanced** is the upgrade-safe default. **Simple** keeps common actions visible. **Configure menu** can hide or reorder registered actions and restore defaults using Kodi-native TV-remote dialogs. Hidden actions remain callable through direct `RunScript(...,mode=...)` key mappings.

**Manage PIN** can create, change, remove or repair a local 4-8 digit numeric PIN. The PIN is salted and derived with PBKDF2-HMAC; plaintext is not stored. It protects media deletion, exclusion and replacement actions, including direct-mode invocations. Queue removal remains confirmation-only. This protects against accidental local use; it is not a boundary against a user who can modify Kodi's local add-on data.

## Path mappings

Direct Kodi VFS deletion and server-side subtitle paths require explicit mappings where Kodi and the server use different paths:

```text
/media/Movies=>smb://server/Movies;/media/Shows=>sftp://server:22/media/Shows
```

Every configured Kodi mapping root is protected automatically. The add-on may use or delete a validated child where appropriate, but never deletes a mapping root or ancestor. VFS-only configuration errors do not block API-backend actions.

## Keymap Editor

Keymap Editor exposes **Launch Kodi Managarr** under Add-ons actions. Advanced keymaps may call a mode directly:

```xml
<key>RunScript(special://home/addons/context.arr.manager/default.py,mode=request_search)</key>
<key>RunScript(special://home/addons/context.arr.manager/default.py,mode=interactive_search)</key>
<key>RunScript(special://home/addons/context.arr.manager/default.py,mode=dashboard)</key>
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

Validation covers the ASCII context root, registry dispatch, localisation, PIN policy, optional-service isolation, subtitle entrypoint, release packaging and repository generation. CI runs the gates on Python 3.8 and 3.12 alongside actionlint, Ruff, archive integrity and Kodi add-on checker.

## Android Kodi validation and release

Host-side tests do not replace a real Android Kodi run. Use the [Android Kodi validation runbook](docs/ANDROID_KODI_VALIDATION.md) with disposable media. A release candidate remains optional; the practical release gate is green CI plus applicable checks in the [release checklist](docs/RELEASE_CHECKLIST.md).

## Licence

GPL-3.0-or-later. See `LICENSE.txt`.
