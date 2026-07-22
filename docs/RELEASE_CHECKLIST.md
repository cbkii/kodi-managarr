# Stable release checklist

Use this as the concise release gate. Detailed Android steps and the evidence template are in [`ANDROID_KODI_VALIDATION.md`](ANDROID_KODI_VALIDATION.md). A release candidate is optional; the owner may publish stable, prerelease or draft builds directly. Only stable releases enter the Kodi repository feed.

## Required before stable publication

### Package and CI

- [ ] The intended release commit is on the selected branch and all review threads are resolved.
- [ ] CI passes on Python 3.8 and 3.12.
- [ ] `python scripts/validate.py`, Ruff and the complete unit suite pass.
- [ ] `python scripts/package.py` produces `context.arr.manager-<version>.zip` reproducibly.
- [ ] Kodi add-on checker and archive inspection pass against the exact ZIP.
- [ ] The ZIP contains one `context.arr.manager/` root, `service.py`, all retention modules, `addon.xml`, `LICENSE.txt` and runtime assets.
- [ ] The release workflow publishes `managarr-addon_v<version>.zip` and its matching SHA-256 file.
- [ ] No generated asset, report, media path, private URL, credential or API key is committed or packaged.

### Kodi repository publication

- [ ] The Pages workflow resolves the exact stable tag and rejects drafts/prereleases.
- [ ] `addons.xml`, its change token/checksums and per-ZIP checksums match.
- [ ] `repository.managarr-X.Y.Z.zip` is valid, deterministic and installable.
- [ ] The stable update is offered through Kodi and preserves settings.

### Android Kodi quick validation

- [ ] Repository/add-on installation or upgrade succeeds and settings persist.
- [ ] The ASCII **Managarr** root renders for movie, TV-show and episode rows.
- [ ] Advanced/Simple menus and hide/reorder/restore behaviour work with the remote.
- [ ] Hidden direct modes remain callable and retain the same policy checks.
- [ ] PIN create/change/remove and direct destructive enforcement work.
- [ ] Radarr/Sonarr connection tests pass.
- [ ] Existing Delete actions pass dry-run checks and one disposable API mutation succeeds.
- [ ] Reports/logs contain no credentials or private URLs.

### Retention

- [ ] Retention is disabled by default; background dry-run is enabled by default.
- [ ] Settings accept `0` and `9999`, reject invalid values, and render all help text.
- [ ] Preview identifies the intended disposable movie/episode candidates and explains eligibility.
- [ ] Added age uses the latest applicable Kodi/Servarr timestamp.
- [ ] Watched age uses Kodi play count/last-played; a multi-episode file requires every linked row watched.
- [ ] Manual dry run makes no changes.
- [ ] Manual real cleanup requires the PIN when configured, revalidates the item and deletes through Servarr API only.
- [ ] Movie cleanup creates the Radarr import exclusion and removes the targeted Kodi row.
- [ ] Episode cleanup unmonitors every linked Sonarr episode, deletes one physical file and updates targeted Kodi rows.
- [ ] A pre-delete episode failure restores monitoring; a post-commit failure is reported as committed.
- [ ] Periodic dry run executes once when due, respects the interval/batch cap and opens no modal dialog.
- [ ] Enabling real periodic deletion requires PIN authorisation when configured.
- [ ] Changing/removing/corrupting the PIN disables or invalidates real periodic cleanup.
- [ ] Disabling periodic cleanup requires no PIN and stops the next candidate promptly.
- [ ] Concurrent manual/scheduled runs do not overlap and stale-lock recovery is safe.
- [ ] Last report includes run type, dry-run state, times, next due, counts, stable IDs, reasons and stages without paths/URLs/secrets.

Mark physical checks not performed as **NOT TESTED** rather than claiming a pass. Whole-series automatic deletion and unattended VFS retention are not part of this release.

## Optional backend checks

SMB/SFTP checks apply only to the existing manual VFS backend when claimed as device-tested. Retention itself must not use VFS/SMB/SFTP deletion.

## Release workflow

Run **Actions → Build and publish Kodi release**:

1. choose the branch;
2. enter the intended version or leave blank for the documented untagged/patch behaviour;
3. choose stable, prerelease or draft;
4. optionally override release highlights, or leave blank to use maintained `addon.xml` news;
5. run the workflow;
6. for stable, confirm the Pages repository publishes the same tag/version.

No mandatory RC promotion sequence is required.
