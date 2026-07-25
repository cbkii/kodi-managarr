# Stable release checklist

Use this concise gate with [`ANDROID_KODI_VALIDATION.md`](ANDROID_KODI_VALIDATION.md). A release candidate is optional. The owner may publish stable, prerelease or draft builds directly; only stable releases enter the Kodi repository feed.

## Add-on package and CI

- [ ] Intended release commit is on the selected branch and `addon.xml` version is newer than the latest stable tag.
- [ ] Python 3.8 and 3.12 host CI, Ruff, actionlint and complete unit tests pass with no placeholder/disabled tests.
- [ ] `scripts/validate.py` and Kodi add-on checker pass.
- [ ] Metadata remains nonempty and within project limits: summary 160, description 1000, news 1500 characters.
- [ ] Fresh-install defaults keep confirmation, general dry run and blocklist requirements enabled.
- [ ] Fresh-install retention is disabled, movies/episodes are excluded, periodic scheduling is disabled, and both retention dry-run settings are enabled.
- [ ] Registry modes, aliases and direct dispatch remain consistent; no obsolete parallel entrypoint is packaged.
- [ ] Deterministic packaging produces one valid `context.arr.manager/` root with safe non-executable permissions.
- [ ] ZIP excludes tests, docs, scripts, hidden/generated files, bytecode and obsolete runtime modules.
- [ ] ZIP contains `addon.xml`, `LICENSE.txt`, `default.py`, `context.py`, `service.py`, `subtitles.py`, resources/runtime files and artwork.
- [ ] `xbmc.service` and `xbmc.subtitle.module` point to their packaged entrypoints.
- [ ] Public assets use `managarr-addon_vX.Y.Z.zip` and a portable matching SHA-256 file.

## Kodi repository publication

- [ ] Pages resolves the exact intended stable release and rejects draft/prerelease assets.
- [ ] `addons.xml`, MD5 change token, SHA-256 files and per-package hashes match.
- [ ] `repository.managarr-X.Y.Z.zip` is deterministic, installable, licensed and does not contain itself.
- [ ] The next stable release is detected as an update and preserves settings.

## Core Android Kodi checks

- [ ] Clean install starts with Dry run enabled; upgrade preserves an explicitly saved setting.
- [ ] Plain ASCII Managarr root renders for movie/show/episode.
- [ ] Advanced/Simple menus, hide/order/restore and hidden direct modes work.
- [ ] Encoded query-style direct modes dispatch correctly.
- [ ] PIN create/change/remove and fail-closed direct/menu enforcement work.
- [ ] Episode actions resolve the parent series through Kodi TV-show metadata, including season zero and API-backend/no-mapping use.
- [ ] International titles remain matchable after normalisation.
- [ ] Radarr/Sonarr tests, dry runs, cancellation and one disposable API mutation pass.
- [ ] Diagnostics/logs contain no credentials or private URLs.

## Retention checks

Use disposable media only; do not test real deletion against irreplaceable library content.

- [ ] Retention remains unavailable until enabled and at least movies or episodes are explicitly included.
- [ ] Preview honours watched state, added-age and watched-age thresholds in both **all** and **any** modes.
- [ ] `movie:<id>`, `episode:<id>`, `series:<id>` and `season:<show-id>:<season>` exclusions protect their exact scope.
- [ ] Malformed exclusion syntax invalidates retention instead of being silently ignored.
- [ ] A movie at or above the configured rating threshold is protected; an unrated movie is protected while the threshold is enabled.
- [ ] Manual dry-run creates a bounded report without changing Kodi, Radarr or Sonarr.
- [ ] Real manual cleanup requires the central PIN when configured and respects the per-pass deletion cap.
- [ ] Movie cleanup revalidates identity, removes through Radarr with an import-list exclusion and targets only the corresponding Kodi row.
- [ ] Episode cleanup revalidates every linked Sonarr/Kodi episode, unmonitors them, deletes exactly one episode-file record and targets only those Kodi rows.
- [ ] A shared multi-episode file remains untouched when any linked episode is excluded, missing, unwatched or otherwise ineligible.
- [ ] Enabling periodic retention requires central PIN authorisation; disabling it never requires a PIN.
- [ ] Changing, repairing or removing PIN material disables real periodic cleanup until explicitly re-enabled.
- [ ] Periodic dry-run, deletion cap, atomic lock, report and notification modes behave as configured after a Kodi restart.

## Interactive feature checks

- [ ] Request defaults can be selected and persist.
- [ ] Managed/unmanaged movie Request & Search avoids duplicates and completes search.
- [ ] Series and selected-episode Request & Search use the intended monitoring/search scope and parent-series ID.
- [ ] Ambiguous lookup requires explicit selection; partial add/search failure is honest.
- [ ] Interactive movie/episode release details, cancellation, revalidation and Arr grab pass.
- [ ] Prowlarr remains informational/read-only and cannot bypass Arr authority.
- [ ] Dashboard isolates one failing service and uses bounded/manual refresh.
- [ ] Bazarr connection and one-to-three unique language configuration work.
- [ ] Base/forced/hearing-impaired language qualifier behaviour matches configuration.
- [ ] Kodi built-in subtitle search returns and loads the exact selected, Kodi-accessible movie and episode subtitle.
- [ ] Subtitle tokens are single-use; malformed/replayed state fails safely and plugin completion reports success/failure accurately.
- [ ] Subtitle cache/results contain no media path, secrets or service URLs, and server-only paths are never handed directly to Kodi.

## Compatibility claims

- Runtime: Kodi 19+ with Kodi's Python 3 runtime, including Android Kodi.
- Unsupported: Kodi 18 and Python 2.
- Host CI: CPython 3.8 and 3.12 for pure-code/tooling validation; this is separate from the Kodi runtime compatibility claim.
- Mark physical Android, SMB, SFTP, Prowlarr, Bazarr or real retention checks **NOT TESTED** rather than overstating evidence.

## Release workflow

Run **Actions -> Build and publish Kodi release**:

1. choose the branch;
2. enter a version or leave blank for the maintained manifest/automatic patch behaviour;
3. choose stable, prerelease or draft;
4. optionally override release highlights, or leave blank to use maintained `addon.xml` news;
5. run the workflow;
6. for stable, confirm Pages publishes the same tag/version.

No mandatory RC promotion sequence is required.
