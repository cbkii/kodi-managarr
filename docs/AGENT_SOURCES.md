# Authoritative engineering sources for agents

This file is a curated knowledgebase for Jules, Codex, GitHub Copilot, reviewers, and maintainers working on Kodi Managarr. Use it together with `AGENTS.md`.

Links are grouped by authority and purpose. Before changing an external contract, open the relevant current source rather than relying on memory or a copied payload.

## How to use this knowledgebase

For each change involving Kodi or a Servarr API:

1. identify the exact Kodi generation and Radarr/Sonarr/Prowlarr version being targeted;
2. inspect the deployed application's OpenAPI/Swagger output where available;
3. verify the matching upstream controller/resource/command source;
4. consult the official user/developer documentation for intended semantics;
5. use mature add-ons only for implementation patterns, not as API authority;
6. add tests that lock in the verified behaviour and failure cases.

Do not generalise API versions across Servarr products:

- Radarr public API: v3
- Sonarr public API: v3
- Prowlarr public API: v1

A reverse proxy may prepend a URL base. Build all endpoints from the configured base URL and product-specific API prefix.

---

# Kodi official references

## Add-on architecture and metadata

- Add-on development index: https://kodi.wiki/view/Add-on_development
  - Entry point for add-on types, tutorials, Python libraries, publishing and debugging.
- Add-on structure: https://kodi.wiki/view/Add-on_structure
  - Expected layout and purpose of `addon.xml`, `resources/`, language files and Python code.
- `addon.xml` reference: https://kodi.wiki/view/Addon.xml
  - Extension points, dependencies, metadata, assets and platform declarations.
- Add-on rules: https://kodi.wiki/view/Add-on_rules
  - Repository-quality and packaging rules; use as a quality baseline even for GitHub-only releases.
- Submitting add-ons: https://kodi.wiki/view/Submitting_Add-ons
  - Official repository expectations and review workflow.
- Official add-on checker: https://github.com/xbmc/addon-check
  - Run or inspect this before pursuing Kodi repository submission. Do not assume this repository's lightweight validator covers all official rules.

Critical implications:

- The installable ZIP must contain one top-level directory named exactly after the add-on ID: `context.arr.manager/`.
- Runtime files belong beneath that directory; development-only directories such as `.git`, `.github`, `tests`, `docs`, `scripts`, and `dist` must not leak into the ZIP.
- Keep add-on ID stable after release. Kodi uses it as the installed add-on identity and profile-data namespace.
- Keep all user-visible text in language resources.

## Context-menu integration

- Context Item Add-ons: https://kodi.wiki/view/Context_Item_Add-ons
- List of boolean conditions: https://kodi.wiki/view/List_of_boolean_conditions
- Info labels: https://kodi.wiki/view/InfoLabels
- Kodi Python `ListItem` API: https://xbmc.github.io/docs.kodi.tv/master/kodi-base/d8/d29/group__python__xbmcgui__listitem.html

Critical implications:

- Register context actions through `kodi.context.item`.
- Kodi 19+ supports a shared script plus unique `args`; values arrive in `sys.argv`.
- `sys.listitem` is a copy of the selected item and is the primary context source.
- Use visibility expressions to expose actions only for supported Kodi library types.
- Prefer modern `InfoTagVideo` methods, but retain tested fallbacks because Android builds, skins and list origins can expose incomplete labels/tags.
- Context-menu scripts should return promptly and must not leave the Kodi UI blocked indefinitely.

## Settings and secrets

- Add-on settings: https://kodi.wiki/view/Add-on_settings
- Kodi 19+ settings conversion/new schema: https://kodi.wiki/view/Add-on_settings_conversion
- `xbmcaddon` Python API: https://xbmc.github.io/docs.kodi.tv/master/kodi-base/d4/d17/group__python__xbmcaddon.html

Critical implications:

- Settings UI definitions live at `resources/settings.xml`.
- Settings are retrieved as strings unless using typed helpers; validate and convert explicitly.
- A setting marked `hidden` is visually masked only. Kodi stores the value unencrypted in the add-on profile. Never log or export API keys, passwords, private keys or credential-bearing SMB URLs.
- Preserve stable setting IDs so upgrades retain configuration.
- Any migration of setting IDs or representation needs compatibility handling and tests.

## Kodi filesystem and Android

- Android platform guide: https://kodi.wiki/view/Android
- Kodi data folder: https://kodi.wiki/view/Kodi_data_folder
- Special protocol: https://kodi.wiki/view/Special_protocol
- SMB guide: https://kodi.wiki/view/SMB
- `xbmcvfs` Python API: https://xbmc.github.io/docs.kodi.tv/master/kodi-base/d7/d0c/group__python__xbmcvfs.html
- File access examples: https://kodi.wiki/view/Archive:Python_Development#File_and_directory_access

Critical implications:

- Android Kodi is sandboxed and does not behave like a Debian shell environment.
- Use `xbmcvfs` for `smb://`, `special://`, ZIP and other Kodi VFS paths.
- Never send an SMB/VFS URL to `os`, `pathlib`, `shutil`, `subprocess`, or a shell.
- Use `special://profile`, `special://home`, and `special://temp` rather than assuming desktop paths such as `/tmp`.
- Let Kodi own SMB authentication through configured sources where possible. Do not persist duplicate plaintext SMB credentials in this add-on.
- Android Kodi cannot be assumed to provide `ssh`, `systemd`, GNU utilities, a desktop keyring, or arbitrary Python wheels.

## Kodi runtime, UI, logging and JSON-RPC

- Kodi Python modules: https://kodi.wiki/view/Category:Python
- Kodi Python API docs: https://xbmc.github.io/docs.kodi.tv/master/kodi-base/modules.html
- `xbmc` API: https://xbmc.github.io/docs.kodi.tv/master/kodi-base/d6/db2/group__python__xbmc.html
- `xbmcgui` API: https://xbmc.github.io/docs.kodi.tv/master/kodi-base/dd/dae/group__python__xbmcgui.html
- JSON-RPC API: https://kodi.wiki/view/JSON-RPC_API
- JSON-RPC schema/introspection: https://kodi.wiki/view/JSON-RPC_API/Examples
- Log file: https://kodi.wiki/view/Log_file
- Python debugging: https://kodi.wiki/view/Python_debugging

Critical implications:

- Keep Kodi imports at adapter/entry-point boundaries so pure logic can run under normal Python.
- Use Kodi dialogs/notifications for user feedback and Kodi logging for diagnostics.
- Redact secrets before logging.
- Use JSON-RPC or supported built-ins for Kodi library refreshes; do not mutate Kodi's database directly.
- Treat UI cancellation as a normal outcome, not an error.

---

# Radarr authoritative references

## Product and deployment

- Official site: https://radarr.video/
- Servarr wiki: https://wiki.servarr.com/radarr
- Linux/Debian installation: https://wiki.servarr.com/radarr/installation/linux
- System and troubleshooting: https://wiki.servarr.com/radarr/system
- Application data directory: https://wiki.servarr.com/radarr/appdata-directory
- Source repository: https://github.com/Radarr/Radarr

Important Debian guidance:

- Official manual guidance commonly installs binaries under `/opt/Radarr` and app data under `/var/lib/radarr`.
- It uses a dedicated `radarr` user and recommends a shared media group with read/write access to media and download paths.
- These are deployment conventions, not paths that Kodi Managarr should hard-code or modify.

## API and source

- Public v3 API docs: https://radarr.video/docs/api/
- API source root: https://github.com/Radarr/Radarr/tree/develop/src/Radarr.Api.V3
- Movie controller: https://github.com/Radarr/Radarr/blob/develop/src/Radarr.Api.V3/Movies/MovieController.cs
- Movie-file controller: https://github.com/Radarr/Radarr/blob/develop/src/Radarr.Api.V3/MovieFiles/MovieFileController.cs
- History controller: https://github.com/Radarr/Radarr/blob/develop/src/Radarr.Api.V3/History/HistoryController.cs
- Command controller/resources: https://github.com/Radarr/Radarr/tree/develop/src/Radarr.Api.V3/Commands
- Movie search command: https://github.com/Radarr/Radarr/blob/develop/src/NzbDrone.Core/Movies/Commands/MoviesSearchCommand.cs
- History event enum: https://github.com/Radarr/Radarr/blob/develop/src/NzbDrone.Core/History/HistoryEventType.cs
- Failed download handling: https://github.com/Radarr/Radarr/blob/develop/src/NzbDrone.Core/Download/FailedDownloadService.cs

Verified contracts central to this project:

- Delete movie: `DELETE /api/v3/movie/{id}` with `deleteFiles` and `addImportExclusion` query parameters.
- Delete movie file: `DELETE /api/v3/movieFile/{id}`.
- Search movie: `POST /api/v3/command` with `name: MoviesSearch` and `movieIds`.
- Rescan movie: command `RescanMovie` with `movieId`.
- Imported history is represented by `DownloadFolderImported` (`eventType=3`) in the supported generation.
- Marking the matching imported history item failed through `POST /api/v3/history/failed/{id}` invokes Radarr's failed-download pipeline and normal blocklist behaviour.

Re-verify these contracts before changing them. Upstream development branches can move ahead of stable deployed releases.

---

# Sonarr authoritative references

## Product and deployment

- Official site: https://sonarr.tv/
- Servarr wiki: https://wiki.servarr.com/sonarr
- Linux/Debian installation: https://wiki.servarr.com/sonarr/installation/linux
- System and troubleshooting: https://wiki.servarr.com/sonarr/system
- Application data directory: https://wiki.servarr.com/sonarr/appdata-directory
- Source repository: https://github.com/Sonarr/Sonarr

For Debian, expect a dedicated service user, systemd operation and a writable application-data directory. Confirm the actual service/unit and paths from the target system rather than assuming a historical package layout.

## API and source

- Public API docs: https://sonarr.tv/docs/api/
- API source root: https://github.com/Sonarr/Sonarr/tree/develop/src/Sonarr.Api.V3
- Series controller: https://github.com/Sonarr/Sonarr/blob/develop/src/Sonarr.Api.V3/Series/SeriesController.cs
- Episode controller: https://github.com/Sonarr/Sonarr/blob/develop/src/Sonarr.Api.V3/Episodes/EpisodeController.cs
- Episode-file controller: https://github.com/Sonarr/Sonarr/blob/develop/src/Sonarr.Api.V3/EpisodeFiles/EpisodeFileController.cs
- History controller: https://github.com/Sonarr/Sonarr/blob/develop/src/Sonarr.Api.V3/History/HistoryController.cs
- Command controller/resources: https://github.com/Sonarr/Sonarr/tree/develop/src/Sonarr.Api.V3/Commands
- Episode search command: https://github.com/Sonarr/Sonarr/blob/develop/src/NzbDrone.Core/Tv/Commands/EpisodeSearchCommand.cs
- Series search command: https://github.com/Sonarr/Sonarr/blob/develop/src/NzbDrone.Core/Tv/Commands/SeriesSearchCommand.cs
- History event enum: https://github.com/Sonarr/Sonarr/blob/develop/src/NzbDrone.Core/History/HistoryEventType.cs
- Failed download handling: https://github.com/Sonarr/Sonarr/blob/develop/src/NzbDrone.Core/Download/FailedDownloadService.cs

Verified contracts central to this project:

- Delete series: `DELETE /api/v3/series/{id}` with `deleteFiles` and `addImportListExclusion` query parameters.
- Delete episode file: `DELETE /api/v3/episodeFile/{id}`.
- Bulk delete episode files: verify the current `/api/v3/episodeFile/bulk` request resource before modifying payloads.
- Update monitoring: `PUT /api/v3/episode/{id}` with a complete compatible episode resource.
- Search episodes: command `EpisodeSearch` with `episodeIds`.
- Search series: command `SeriesSearch` with `seriesId`.
- Rescan series: command `RescanSeries` with `seriesId`.
- Imported history uses `DownloadFolderImported` (`eventType=3`) in the supported generation.
- `POST /api/v3/history/failed/{id}` invokes normal failed-download/blocklist handling.

Sonarr's import-list exclusion is series-level. There is no equivalent episode-level import-list exclusion in the current API model. Kodi Managarr's episode `Delete & Exclude` behaviour therefore unmonitors every episode linked to the deleted physical episode file.

---

# Prowlarr authoritative references

## Product and deployment

- Official site: https://prowlarr.com/
- Servarr wiki: https://wiki.servarr.com/prowlarr
- Linux/Debian installation: https://wiki.servarr.com/prowlarr/installation/linux
- System and troubleshooting: https://wiki.servarr.com/prowlarr/system
- Application data directory: https://wiki.servarr.com/prowlarr/appdata-directory
- Source repository: https://github.com/Prowlarr/Prowlarr

Official manual Debian guidance commonly uses `/opt/Prowlarr`, `/var/lib/prowlarr`, a dedicated `prowlarr` user and a systemd service. Do not hard-code or mutate those paths from the Kodi add-on.

## API and source

- Public v1 API docs: https://prowlarr.com/docs/api/
- API source root: https://github.com/Prowlarr/Prowlarr/tree/develop/src/Prowlarr.Api.V1
- Indexer controller: https://github.com/Prowlarr/Prowlarr/blob/develop/src/Prowlarr.Api.V1/Indexers/IndexerController.cs
- Application controller: https://github.com/Prowlarr/Prowlarr/tree/develop/src/Prowlarr.Api.V1/Applications
- Search API: https://github.com/Prowlarr/Prowlarr/tree/develop/src/Prowlarr.Api.V1/Search
- History API: https://github.com/Prowlarr/Prowlarr/tree/develop/src/Prowlarr.Api.V1/History
- Command API: https://github.com/Prowlarr/Prowlarr/tree/develop/src/Prowlarr.Api.V1/Commands

Critical boundary:

- Prowlarr manages indexers, searches, applications and indexer synchronisation.
- It does not own Radarr movies, Sonarr series/episodes, imported media files or their blocklist history.
- Any future Prowlarr integration needs a separate v1 client and settings section. Do not inherit Radarr/Sonarr v3 paths by convention.
- Prefer Prowlarr application/indexer APIs to editing definitions or application data directly.

---

# Live instance API discovery

When integration tests can access a configured instance, inspect its own Swagger/OpenAPI UI or schema. Common installations expose Swagger from the application web root, but exact paths and availability vary by version and URL base.

Use the live schema to confirm:

- API prefix and version;
- endpoint path and HTTP method;
- query-parameter spelling and defaults;
- required request body/resource shape;
- response and command resource shape;
- supported enum values;
- authentication header;
- bulk-operation semantics.

Do not include real API keys or instance URLs in committed tests, logs, issue comments, snapshots or fixtures.

---

# Battle-tested Kodi add-on repositories

These repositories are implementation references, not authorities over Kodi's formal API.

## Context-menu pattern

- Trakt context menu: https://github.com/razzeee/context.trakt.contextmenu
  - Small, focused example of `kodi.context.item`, visibility expressions, Python entry points and language resources.
  - Useful for context-menu packaging and registration; verify age/Kodi generation before copying syntax.

## Mature networked add-ons

- YouTube for Kodi: https://github.com/anxdpanic/plugin.video.youtube
  - Mature add-on with settings, networking, authentication, localisation, logging, compatibility handling and extensive real-world use.
  - Use as a pattern source for separation of concerns and defensive remote-service handling, not as a reason to add unnecessary framework complexity.

- TheMovieDb Helper: https://github.com/jurialmunkey/plugin.video.themoviedb.helper
  - Mature Python/Kodi integration with metadata, library interaction, routing, caching and version compatibility.
  - Particularly useful when evaluating Kodi metadata and `ListItem` handling patterns.

## Official repositories and quality corpus

- Official script add-ons: https://github.com/xbmc/repo-scripts
- Official plugin add-ons: https://github.com/xbmc/repo-plugins
- Add-on checker: https://github.com/xbmc/addon-check

Use official repositories to inspect currently accepted manifests, settings schemas, language layouts and Python compatibility. Select examples that target the same Kodi generation; repository history contains code for multiple generations.

---

# Additional operational guidance

## Servarr path and permission model

- Servarr system troubleshooting repeatedly emphasises consistent paths, separate download and library roots, correct remote-path mapping, and read/write permissions for the service user/group.
- Kodi Managarr should surface path mismatches clearly but must not silently repair Linux permissions or rewrite Servarr root folders.
- Direct file deletion over SMB/SFTP creates out-of-band filesystem changes. Always ask Servarr to rescan and verify its file record is reconciled before continuing.

## Commands are asynchronous

A successful `POST /command` means the command was accepted, not necessarily completed. When correctness depends on completion:

1. retain the returned command ID;
2. poll the product/version-specific command endpoint;
3. stop on completed success, completed failure, cancellation, or timeout;
4. propagate the remote failure message safely;
5. never use unbounded polling or a fixed sleep as proof of completion.

## API authentication and transport

- Servarr commonly uses the `X-Api-Key` header.
- Keep TLS verification enabled by default.
- Support reverse-proxy URL bases without dropping or duplicating path components.
- Apply bounded timeouts.
- Do not automatically retry destructive operations unless duplicate safety is proven.
- Redact secrets in exceptions and diagnostics.

## Release and package references

- Workflow: `.github/workflows/release.yml`
- Local validator: `scripts/validate.py`
- Packager: `scripts/package.py`
- Shared engineering contract: `AGENTS.md`

The workflow-dispatch form is authoritative for release branch, version, channel, notes and Latest status. Blank version means numeric patch increment, including `99.99.9 -> 99.99.10`.

---

# Agent-platform instruction references

- Jules getting started and `AGENTS.md`: https://jules.google/docs/
- Jules environment setup: https://jules.google/docs/environment/
- GitHub Copilot repository instructions: https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions
- OpenAI Codex and `AGENTS.md`: https://openai.com/index/introducing-codex/
- Codex documentation: https://platform.openai.com/docs/codex/overview

The root `AGENTS.md` is intentionally the shared source of truth because Jules and Codex consume it directly and Copilot supports it as agent instructions. `.github/copilot-instructions.md` and path-specific instruction files supplement it for Copilot surfaces.
