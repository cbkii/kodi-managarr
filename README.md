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
2. Supports **Kodi VFS** using Kodi's own saved SMB or SFTP source credentials.
3. Uses Kodi's official optional **SFTP support** (`vfs.sftp`) binary add-on for SFTP paths instead of a Python SSH library.

No Android storage permission is needed to delete Pi-hosted SMB or SFTP files through Kodi's VFS.

## Install on Kodi

1. Download the latest `context.arr.manager-<version>.zip` release asset.
2. Copy it to a location available to Kodi.
3. In Kodi, enable **Settings → System → Add-ons → Unknown sources** if required.
4. Open **Add-ons → Install from zip file** and select the archive.
5. Open **Add-ons → My add-ons → Context menus → Arr Manager → Configure**.
6. Enter the Radarr and Sonarr base URLs and API keys.
7. Run both connection tests.
8. Leave `Dry run` enabled for the first tests.

The context menu appears on Kodi **library** movies, TV shows and episodes. Add SMB folders as video sources and scan them into Kodi's library first.

## Recommended Pi settings

For the supplied Pi baseline:

```text
Radarr URL: http://192.168.1.50:7878
Sonarr URL: http://192.168.1.50:8989
```

API keys are available in each application under **Settings → General → Security**.

Use whichever Pi address is reachable from the TV. Avoid `localhost`, because that refers to the Android TV itself.

## Network VFS setup and path mapping

Add the Pi shares to Kodi through **Settings → File manager → Add source** or **Videos → Files → Add videos**. For SFTP, install **SFTP support** from Kodi's repository, then use **Add network location → SSH/SFTP** and let Kodi save and verify the credentials before testing deletion.

The add-on maps paths reported by Radarr/Sonarr to paths Kodi can open. The setting format is:

```text
Pi path=>Kodi VFS path;Pi path=>Kodi VFS path
```

Example:

```text
/media/mediasmb/Movies=>smb://192.168.1.50/Movies;/media/mediasmb/Shows=>sftp://192.168.1.50:22/media/mediasmb/Shows
```

The SMB share names or SFTP paths must match the network location Kodi can access. Avoid embedding passwords in mapping text; use Kodi-managed credentials wherever possible. Kodi's selected library item path can also be used directly for a single movie or episode.

### Deletion backends

- **Servarr API:** recommended. Radarr/Sonarr perform deletion locally on the Pi and update their databases atomically.
- **Kodi VFS (SMB/SFTP):** Kodi deletes over the authenticated SMB source or official `vfs.sftp` SFTP source, then the add-on asks Radarr/Sonarr to rescan and waits for the file record to disappear. SFTP uses Kodi's trust-on-first-use host-key handling rather than add-on-controlled fingerprint pinning.

## Safety behaviour

- Destructive confirmation is on by default.
- Dry-run mode is available.
- Recursive deletion rejects root/share roots and configured protected paths.
- Ambiguous Radarr/Sonarr matches fail safely.
- API keys and credential-bearing network URLs are not written to diagnostics.
- Replace actions resolve import history before deleting.

Keep the default protected paths and add any other storage roots that must never be recursively removed.

## Current limitations

- Replace cannot guarantee blocklisting for manually copied/imported files that have no usable Servarr import history; strict mode stops safely.
- SFTP availability depends on Kodi's optional platform-matched `vfs.sftp` binary add-on. Servarr API should still be preferred.
- The initial release targets Kodi 19+ (Python 3), including current Android builds.

## Development

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
python3 scripts/package.py
```

The package command writes a Kodi-installable ZIP to `dist/`. The ZIP always contains the required `context.arr.manager/` top-level directory, regardless of the Git checkout directory name.

The code uses only Python's standard library outside Kodi. Kodi runtime modules are imported only at entry points, so matching and path logic can be tested on a normal workstation.

## Coding-agent development

Jules, Codex, GitHub Copilot coding agent, Copilot code review, and other autonomous agents must begin with:

- [`AGENTS.md`](AGENTS.md) — shared architecture, safety, implementation, test, review and release contract;
- [`docs/AGENT_SOURCES.md`](docs/AGENT_SOURCES.md) — authoritative Kodi, Android, Radarr, Sonarr, Prowlarr, API, Debian and battle-tested add-on references;
- [`.github/copilot-instructions.md`](.github/copilot-instructions.md) — Copilot repository-wide instructions;
- [`.github/instructions/`](.github/instructions/) — path-specific Kodi and Servarr instructions;
- [`docs/agents/JULES.md`](docs/agents/JULES.md) and [`docs/agents/CODEX.md`](docs/agents/CODEX.md) — agent-specific execution profiles.

The instructions require agents to verify external contracts against live OpenAPI or current upstream source, preserve fail-closed destructive behaviour, add regression tests, run validation/package checks, inspect complete review/CI evidence, and state any Android TV or live Servarr testing gaps.

## Publishing a release

The **Build and publish Kodi release** workflow is manual-only and its `workflow_dispatch` fields are authoritative.

Open **Actions → Build and publish Kodi release → Run workflow**, then set:

- **branch:** the branch to package and update, normally `main`;
- **version:** an exact numeric `x.y.z` version, or leave blank to increment the highest existing patch version automatically;
- **channel:** `stable`, `prerelease`, or `draft`;
- **release_notes:** optional release highlights; these are also written into `addon.xml` as the `<news>` entry;
- **mark_latest:** whether a stable release should become GitHub's Latest release.

Examples:

- Existing highest version `0.1.0`, blank version input → `0.1.1`.
- Existing highest version `99.99.9`, blank version input → `99.99.10`.
- Version input `2.0.0` → exactly `2.0.0`.

The workflow:

1. resolves the authoritative version from the dispatch form;
2. updates `addon.xml` version and news metadata;
3. validates XML and Python source;
4. runs unit tests;
5. builds and verifies the Kodi-installable ZIP;
6. commits the selected release metadata back to the chosen branch;
7. creates the tag and GitHub release at that commit;
8. uploads the ZIP and SHA-256 checksum as release assets and workflow artifacts;
9. combines supplied highlights, installation guidance, compatibility details, provenance, and GitHub-generated change notes.

It refuses duplicate tags/releases and invalid versions. Because the workflow writes back to the selected branch, that branch must permit GitHub Actions to push with `contents: write` permission.

Run with automatic patch increment:

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

Run with an explicit version:

```bash
gh workflow run release.yml \
  --repo cbkii/kodi-managarr \
  --ref main \
  -f branch=main \
  -f version=2.0.0 \
  -f channel=stable \
  -f mark_latest=true
```

## Repository layout

```text
AGENTS.md
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
  AGENT_SOURCES.md
  agents/
.github/
  copilot-instructions.md
  instructions/
  workflows/
```

## Licence

GPL-3.0-or-later.
