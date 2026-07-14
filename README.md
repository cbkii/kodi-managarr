# Arr Manager for Kodi

A Kodi Python 3 context-menu add-on for managing Radarr movies and Sonarr series/episodes directly from Kodi's video library.

## Actions

### Delete & Exclude

- **Movie:** removes the movie from Radarr, deletes its file/folder, and adds a Radarr import-list exclusion.
- **Series:** removes the series from Sonarr, deletes its files/folder, and adds a Sonarr import-list exclusion.
- **Episode:** deletes the episode file and unmonitors every episode linked to that file. Sonarr does not provide an episode-level import-list exclusion, so unmonitoring is the safe episode-level equivalent.

### Delete & Replace

- **Movie:** identifies the imported release, deletes the current file, marks that release failed so Radarr blocklists it, then starts a movie search.
- **Episode:** handles multi-episode files, blocklists the matched imported release, deletes the file, then searches for every linked episode.
- **Series:** preflights every current episode file, deletes them, blocklists the matched releases, then starts a full series search.

`Require release-history match before Replace` is enabled by default. If the add-on cannot prove which release created a file, it stops before deleting anything. This is important for the requirement that the same release must not be downloaded again.

## Android TV design

Kodi on Android normally has no usable system `ssh` executable and cannot safely assume desktop Python wheels are available. This add-on therefore:

1. Uses the **Servarr APIs** as the recommended deletion backend.
2. Supports **Kodi SMB/VFS** using Kodi's own saved SMB source credentials.
3. Supports optional **SSH/SFTP** only when a Kodi-compatible `paramiko` module is already installed. It uses SFTP operations, not shell commands.

No Android storage permission is needed to delete Pi-hosted SMB files through Kodi's VFS.

## Install on Kodi

1. Copy `context.arr.manager-0.1.0.zip` to a location available to Kodi.
2. In Kodi, enable **Settings → System → Add-ons → Unknown sources** if required.
3. Open **Add-ons → Install from zip file** and select the archive.
4. Open **Add-ons → My add-ons → Context menus → Arr Manager → Configure**.
5. Enter the Radarr and Sonarr base URLs and API keys.
6. Run both connection tests.
7. Leave `Dry run` enabled for the first tests.

The context menu appears on Kodi **library** movies, TV shows and episodes. Add SMB folders as video sources and scan them into Kodi's library first.

## Recommended Pi settings

For the supplied Pi baseline:

```text
Radarr URL: http://192.168.1.50:7878
Sonarr URL: http://192.168.1.50:8989
```

API keys are available in each application under **Settings → General → Security**.

Use whichever Pi address is reachable from the TV. Avoid `localhost`, because that refers to the Android TV itself.

## SMB setup and path mapping

Add the Pi shares to Kodi through **Settings → File manager → Add source** or **Videos → Files → Add videos**. Let Kodi save the SMB credentials.

The add-on maps paths reported by Radarr/Sonarr to paths Kodi can open. The setting format is:

```text
Pi path=>Kodi path;Pi path=>Kodi path
```

Example:

```text
/media/mediasmb/Movies=>smb://192.168.1.50/Movies;/media/mediasmb/Shows=>smb://192.168.1.50/Shows
```

The share names must match the actual Samba shares. Kodi's selected library item path can also be used directly for a single movie or episode.

### Deletion backends

- **Servarr API:** recommended. Radarr/Sonarr perform deletion locally on the Pi and update their databases atomically.
- **Kodi SMB/VFS:** Kodi deletes over the authenticated SMB source, then the add-on asks Radarr/Sonarr to rescan and waits for the file record to disappear.
- **SSH/SFTP:** the Android Kodi Python runtime must already provide `paramiko`. Configure a pinned `SHA256:...` host-key fingerprint rather than allowing unknown keys.

## Safety behaviour

- Destructive confirmation is on by default.
- Dry-run mode is available.
- Recursive deletion rejects root/share roots and configured protected paths.
- Ambiguous Radarr/Sonarr matches fail safely.
- API keys, SMB credentials and SSH passwords are not written to diagnostics.
- Replace actions resolve import history before deleting.

Keep the default protected paths and add any other storage roots that must never be recursively removed.

## Current limitations

- Replace cannot guarantee blocklisting for manually copied/imported files that have no usable Servarr import history; strict mode stops safely.
- SSH/SFTP availability depends on the Kodi Android Python environment. SMB/VFS or Servarr API should be preferred.
- The initial release targets Kodi 19+ (Python 3), including current Android builds.

## Development

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
python3 scripts/package.py
```

The package command writes a Kodi-installable ZIP to `dist/`. The ZIP always contains the required `context.arr.manager/` top-level directory, regardless of the Git checkout directory name.

The code uses only Python's standard library outside Kodi. Kodi runtime modules are imported only at entry points, so matching and path logic can be tested on a normal workstation.

## Publishing a release

The **Build and publish Kodi release** GitHub Actions workflow is manually triggered with `workflow_dispatch`.

1. Update the `version` and `<news>` entry in `addon.xml`.
2. Commit and push the release-ready code.
3. Open **Actions → Build and publish Kodi release → Run workflow**.
4. Select the source ref and release channel. Leave the version blank to use `addon.xml`.
5. Optionally enter concise release highlights; GitHub-generated change notes are appended automatically.

The workflow:

- validates XML and Python source;
- runs the unit tests;
- builds and verifies the Kodi-installable ZIP;
- attaches the ZIP and its SHA-256 checksum to the GitHub release;
- retains the same files as a workflow artifact for 30 days;
- produces installation instructions, compatibility details, supplied highlights, and generated change notes.

It refuses to publish when the requested version differs from `addon.xml`, or when the release tag already exists.

The workflow can also be started with GitHub CLI:

```bash
gh workflow run release.yml \
  --repo cbkii/kodi-managarr \
  --ref main \
  -f ref=main \
  -f channel=stable \
  -f mark_latest=true

gh run watch --repo cbkii/kodi-managarr --exit-status
```

## Repository layout

```text
addon.xml
context.py
default.py
resources/
  settings.xml
  language/
  lib/arr_manager/
tests/
scripts/
docs/
```

## Licence

GPL-3.0-or-later.
