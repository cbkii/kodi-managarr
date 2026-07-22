# Stable release checklist

Use this as the concise release gate. Detailed device steps and the evidence template are in [`ANDROID_KODI_VALIDATION.md`](ANDROID_KODI_VALIDATION.md).

A release candidate is optional. The repository owner may publish stable, prerelease or draft builds directly through the manual release workflow. Only stable releases are published to the Kodi repository update feed.

## Required before a stable release

### Add-on package

- [ ] The intended release commit is on the selected release branch.
- [ ] CI passes on that commit on Python 3.8 and 3.12.
- [ ] `python scripts/validate.py` passes.
- [ ] `python -m unittest discover -s tests -v` passes with no placeholder-only tests.
- [ ] `python scripts/package.py` produces the expected internal `context.arr.manager-<version>.zip` reproducibly.
- [ ] The release workflow publishes `managarr-addon_v<version>.zip` with a matching `.sha256` file.
- [ ] Kodi add-on checker passes against the extracted ZIP.
- [ ] The release ZIP contains one `context.arr.manager/` root, `addon.xml`, `LICENSE.txt`, runtime files and publication assets.
- [ ] The generated SHA-256 matches the uploaded ZIP.

### Kodi repository publication

- [ ] The Pages workflow resolves the exact intended stable release tag and rejects drafts and prereleases.
- [ ] Exactly one `managarr-addon_v*.zip` release asset is selected and validated.
- [ ] `addons.xml` contains `repository.managarr` and the released `context.arr.manager` version.
- [ ] `addons.xml.md5`, `addons.xml.sha256` and per-ZIP `.sha256` files match their content.
- [ ] `repository.managarr-X.Y.Z.zip` is valid, deterministic, does not include itself, and contains `addon.xml`, `LICENSE.txt`, icon and fanart.
- [ ] Main add-on metadata assets are published at the paths referenced by its `addon.xml`.
- [ ] Repository URLs use HTTPS and the repository ZIP installs in Kodi.
- [ ] The next stable add-on release is detected as an update and preserves settings.

### Android Kodi quick validation

- [ ] The exact repository ZIP installs successfully on the target Android Kodi device.
- [ ] Kodi Managarr installs or upgrades through **Install from repository**.
- [ ] Settings labels/help render and saved values persist.
- [ ] The plain-text **Managarr** root item renders on movie, TV-show and episode library rows.
- [ ] Advanced mode preserves Status, Search, Monitoring, Download queue, both Delete actions and Tools & settings.
- [ ] Simple mode presents the documented reduced set.
- [ ] Hide, reorder and restore-default operations work with a TV remote and persist after reopening Kodi.
- [ ] Hidden actions remain callable through direct `RunScript(...,mode=...)` key mappings.
- [ ] A 4–8 digit PIN can be created, changed and removed; entry is masked.
- [ ] Incorrect PINs and malformed stored PIN state fail closed without deleting media.
- [ ] PIN protection applies to Delete & Exclude and Delete & Replace, including direct modes; queue removal remains confirmation-only.
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

- [ ] Test both a clean installation and an upgrade from the previous stable release.
- [ ] Test a season-zero special.
- [ ] Test a multi-episode file.
- [ ] Test one series-wide replacement with multiple files.
- [ ] Test network loss after a committed direct deletion and confirm the transaction report is accurate.
- [ ] Publish a prerelease first when wider community testing is useful.

## Release workflow

Run **Actions → Build and publish Kodi release**:

1. choose the branch;
2. enter the intended version or leave it blank to use the untagged manifest version or automatic patch increment;
3. choose stable, prerelease or draft;
4. optionally enter a one-off release-highlights override, or leave it blank to use the maintained `addon.xml` news;
5. run the workflow;
6. for a stable release, confirm the Pages repository workflow publishes the same exact tag and version.

No RC promotion sequence is required.
