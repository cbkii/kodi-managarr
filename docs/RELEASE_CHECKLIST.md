# Stable release checklist

Use this as a concise release gate. The detailed device steps and evidence template are in [`ANDROID_KODI_VALIDATION.md`](ANDROID_KODI_VALIDATION.md).

A release candidate is optional. The repository owner may publish stable, prerelease or draft builds directly through the manual release workflow.

## Required before a stable release

### Repository and package

- [ ] The intended release commit is on the selected release branch.
- [ ] CI passes on that commit.
- [ ] `python scripts/validate.py` passes.
- [ ] `python -m unittest discover -s tests -v` passes.
- [ ] `python scripts/package.py` produces the expected internal `context.arr.manager-<version>.zip` package.
- [ ] The release workflow publishes the user-facing asset as `managarr-addon_v<version>.zip` with a matching `.sha256` file.
- [ ] Kodi add-on checker passes against the extracted ZIP.
- [ ] The release ZIP contains one `context.arr.manager/` root, the expected version, all nine context actions and all runtime assets.
- [ ] The generated checksum matches the uploaded ZIP.

### Android Kodi quick validation

- [ ] The exact release ZIP installs or upgrades successfully on the target Android Kodi device.
- [ ] Settings labels/help render and saved values persist.
- [ ] The plain-text **Managarr** root item renders on movie, TV-show and episode library rows.
- [ ] All direct actions and both nested submenus are visible and triggerable.
- [ ] Radarr and Sonarr connection tests pass.
- [ ] Movie and episode Delete & Exclude/Delete & Replace dry runs identify the correct targets and make no changes.
- [ ] Cancellation makes no changes.
- [ ] At least one disposable API-backend end-to-end mutation succeeds and is verified in Servarr and Kodi.
- [ ] Diagnostics and shared logs contain no credentials or API keys.
- [ ] The completed evidence summary from the Android Kodi runbook is saved with the release or linked issue/PR.

## Required only when that backend is claimed as device-tested

### SMB VFS

- [ ] Read-only backend test succeeds for the selected disposable item.
- [ ] One child-file operation succeeds using Kodi-managed SMB access.
- [ ] The mapped root and its ancestors remain intact.
- [ ] Servarr reconciliation and Kodi synchronisation complete.

### SFTP VFS

- [ ] Kodi's official `vfs.sftp` add-on is installed and the network location works in Kodi.
- [ ] Read-only backend test succeeds for the selected disposable item.
- [ ] One child-file operation succeeds using Kodi-managed SFTP access.
- [ ] The mapped root and its ancestors remain intact.
- [ ] Servarr reconciliation and Kodi synchronisation complete.

Mark an optional backend **NOT TESTED** rather than blocking a release that does not claim device validation for it.

## Recommended for broad feature releases

These are useful but not mandatory for every owner-triggered maintenance release:

- [ ] Test both a clean installation and an upgrade from the previous stable release.
- [ ] Test a season-zero special.
- [ ] Test a multi-episode file.
- [ ] Test one series-wide replacement with multiple files.
- [ ] Test network loss after a committed direct deletion and confirm the transaction report is accurate.
- [ ] Publish a prerelease first when wider community testing is useful.

## Release workflow

Run **Actions → Build and publish Kodi release**:

1. choose the branch;
2. enter the intended version or leave it blank to use the untagged manifest version / automatic patch increment;
3. choose stable, prerelease or draft;
4. optionally enter a one-off release-highlights override, or leave it blank to use the maintained `addon.xml` news;
5. run the workflow.

The workflow validates, packages, renames the public asset to `managarr-addon_vX.Y.Z.zip`, checksums and publishes the release. No RC promotion sequence is required.

- [ ] Retention features verified against safe/dummy Servarr instances using physical device.