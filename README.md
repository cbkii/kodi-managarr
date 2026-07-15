# Arr Manager for Kodi

Arr Manager is a Python 3 context-menu add-on for managing Radarr movies and Sonarr series or episodes directly from Kodi's video library.

## Actions

### Delete & Exclude

- **Movie:** removes the movie from Radarr, deletes its file or folder, and adds a Radarr import-list exclusion.
- **Series:** removes the series from Sonarr, deletes its files or folder, and adds a Sonarr import-list exclusion.
- **Episode:** deletes the episode file and unmonitors every Sonarr episode linked to that file. Sonarr has no episode-level import-list exclusion, so unmonitoring is the conservative episode-level action and may later be changed by series or season monitoring.

### Delete & Replace

- **Movie:** proves the imported release, marks it failed so Radarr blocklists it, deletes the current file, verifies reconciliation, then runs and verifies a movie search.
- **Episode:** supports multi-episode files, blocklists the matched imported release before deletion, deletes and reconciles the file, then searches for all linked episodes.
- **Series:** preflights every episode file, blocklists every unique matched release before the first deletion, deletes and reconciles all files, then runs and verifies a full series search.

`Require release-history match before Replace` is enabled by default. When the add-on cannot prove which imported release created every required file, it stops before deletion. Non-strict mode may replace unmatched files but clearly reports that no release was blocklisted and the same release may be reacquired.

## Android TV design

Kodi on Android cannot safely assume a system SSH executable or desktop Python wheels. Arr Manager therefore:

1. uses the **Servarr API** as the recommended deletion backend;
2. uses **Kodi VFS** and Kodi-saved credentials for direct SMB or SFTP access;
3. uses Kodi's optional official **SFTP support** (`vfs.sftp`) binary add-on instead of Paramiko or another Python SSH implementation;
4. uses Python's standard-library HTTP client and no native Python dependencies.

No Android storage permission is required for Pi-hosted SMB or SFTP files accessed through Kodi VFS.

## Install on Kodi

1. Download `context.arr.manager-<version>.zip` from the release assets.
2. In Kodi, enable **Settings → System → Add-ons → Unknown sources** when required.
3. Open **Add-ons → Install from zip file** and select the archive.
4. Open **Add-ons → My add-ons → Context menus → Arr Manager → Configure**.
5. Enter the Radarr and Sonarr base URLs and API keys.
6. Run both connection tests.
7. Enable **Dry run** for the first validation pass.

The context menu is available for Kodi library movies, TV shows and episodes. Media must first be scanned into Kodi's video library.

## Radarr and Sonarr configuration

Example LAN endpoints are:

```text
Radarr URL: http://192.168.1.50:7878
Sonarr URL: http://192.168.1.50:8989
```

Use the actual address reachable from the TV; `localhost` refers to the Android TV itself. API keys are available under **Settings → General → Security** in each Servarr application. Runtime defaults intentionally contain no environment-specific IP address.

## Kodi VFS and path mappings

Add SMB or SFTP locations through Kodi's file manager or video-source setup. For SFTP, install and enable **SFTP support** from Kodi's repository, then create and verify an SSH/SFTP network location in Kodi before enabling direct deletion.

Mappings translate paths reported by Radarr or Sonarr into paths Kodi can access:

```text
Servarr path=>Kodi VFS path;Servarr path=>Kodi VFS path
```

Example:

```text
/media/mediasmb/Movies=>smb://192.168.1.50/Movies;/media/mediasmb/Shows=>sftp://192.168.1.50:22/media/mediasmb/Shows
```

Every destructive direct-backend path must resolve through exactly one configured mapping. Unmapped direct network URLs and arbitrary selected-item paths are rejected. Mapping syntax, authorities, overlaps, traversal, encoded separators and root boundaries are validated fail-closed. Avoid credentials in mapping text and use Kodi-managed credentials.

### Deletion backends

- **Servarr API:** recommended. Radarr or Sonarr deletes locally and updates its database.
- **Kodi VFS (SMB/SFTP):** Kodi deletes through an allowlisted mapped root. Arr Manager preflights the target, verifies accessibility, performs bounded deletion, polls the corresponding Servarr rescan command, and verifies that file records disappear.

Recursive VFS deletion fully plans the tree before the first removal, applies depth and entry limits, rejects unsafe entries and roots, removes bottom-up, and verifies each operation. Unknown or inaccessible VFS state blocks deletion rather than being treated as absence.

## Safety behaviour

- destructive confirmation is enabled by default;
- dry-run mode is available;
- replacement blocklisting completes before the first file deletion;
- multi-file operations preflight all required history and mappings before commit;
- root, share-root, mapping-root, traversal and protected-path deletion is rejected;
- malformed, overlapping or ambiguous mappings fail visibly;
- title-only or contradictory media matches fail closed;
- season and episode zero remain valid Kodi metadata;
- runtime polling uses monotonic deadlines and Kodi shutdown-aware waits rather than `time.sleep()`;
- only safe GET polling retries classified transient failures; mutating requests are never automatically retried;
- Servarr rescan and replacement-search commands are polled to completion or failure;
- Kodi library cleanup uses validated, targeted JSON-RPC calls rather than a blind global scan;
- movie and TV-show rows are identity-checked before removal;
- multi-episode and series-replacement cleanup resolves and removes affected episode rows while retaining the TV-show row;
- failures after deletion report that the destructive commit already occurred rather than implying rollback;
- API keys, credentials and sensitive URL components are excluded from diagnostics and user-facing errors.

Keep protected paths configured for every storage root that must never be recursively removed.

## Validation status and limitations

Host-side CI validates Python 3.8 and 3.12 compatibility, XML and Python compilation, the complete unit-test suite, package construction, Kodi `addon-check` against the extracted release ZIP, archive contents, permissions and integrity.

Physical Android TV testing and live Radarr/Sonarr testing have not been performed by CI and are not claimed. Before release promotion, validate on a real Kodi Android device with the actual media server and network environment.

SFTP availability depends on a platform- and Kodi-version-compatible `vfs.sftp` add-on. Prefer Servarr API deletion whenever it satisfies the deployment requirements.

## Android validation checklist

Before promoting a release, verify:

- ZIP installation and settings rendering;
- context-menu visibility for movies, TV shows and episodes;
- Radarr and Sonarr connection tests;
- SMB root access;
- SFTP access with `vfs.sftp` installed and enabled;
- dry-run output;
- Delete & Exclude for all three media types;
- Delete & Replace for all three media types;
- season-zero specials;
- multi-episode files;
- cancellation before deletion;
- network loss during command or file-state polling;
- Kodi shutdown or restart during a bounded wait;
- Kodi library-row cleanup after each successful action.

## Development

```bash
set -euo pipefail
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
python3 scripts/package.py
rm -rf dist/addon-check
python3 - <<'PY'
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
root = ET.parse('addon.xml').getroot()
addon_id = root.attrib['id']
version = root.attrib['version']
archive = Path('dist') / f'{addon_id}-{version}.zip'
with zipfile.ZipFile(archive) as z:
    z.extractall('dist/addon-check')
PY
kodi-addon-checker --branch matrix dist/addon-check/context.arr.manager
```

The package always has one `context.arr.manager/` root and deterministic non-executable file permissions. Tests, CI files, documentation, build scripts, caches and compiled Python are excluded.

The runtime uses only Python's standard library outside Kodi. Kodi modules are imported at runtime boundaries so matching, path, HTTP, transaction and JSON-RPC behaviour can be tested with host-side fakes.

## Coding-agent instructions

Coding agents must begin with:

- [`AGENTS.md`](AGENTS.md);
- [`docs/AGENT_SOURCES.md`](docs/AGENT_SOURCES.md);
- [`docs/REFERENCES.md`](docs/REFERENCES.md);
- [`.github/copilot-instructions.md`](.github/copilot-instructions.md);
- [`.github/instructions/`](.github/instructions/);
- [`docs/agents/JULES.md`](docs/agents/JULES.md);
- [`docs/agents/CODEX.md`](docs/agents/CODEX.md).

These instructions require authoritative Kodi and Servarr contract verification, fail-closed destructive behaviour, regression tests, package validation and truthful statements about device or live-service testing.

## Publishing a release

The **Build and publish Kodi release** workflow is manual-only. Its `workflow_dispatch` inputs control the branch, version, release channel, release notes and Latest-release status. The workflow validates, tests, packages, commits selected release metadata, creates the tag and release, and uploads the ZIP and checksum.

For an automatic patch increment on `main`:

```bash
gh workflow run release.yml \
  --repo cbkii/kodi-managarr \
  --ref main \
  -f branch=main \
  -f version= \
  -f channel=stable \
  -f mark_latest=true \
  -f release_notes='Describe the user-visible changes here.'

gh run watch --repo cbkii/kodi-managarr --exit-status
```

The selected branch must permit the release workflow to push its metadata commit with `contents: write` permission.

## Licence

GPL-3.0-or-later.
