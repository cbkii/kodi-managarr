# Android Kodi validation runbook

This runbook is the practical device check for a stable Managarr release. It is designed to be completed in about 20–40 minutes with disposable Radarr/Sonarr entries and sacrificial media.

Do not test destructive actions against irreplaceable media. Keep **Dry run** enabled until the dry-run checks below pass.

## 1. Record the test environment

Copy this block into the release notes, PR, issue, or a new validation report:

```text
Date/time:
Tester:
Android TV model:
Android version / OS family:
Kodi version:
Kodi skin:
Managarr version:
ZIP filename:
ZIP SHA-256:
Radarr version:
Sonarr version:
Deletion backend tested: API / SMB VFS / SFTP VFS
vfs.sftp version, if used:
Network connection: Wi-Fi / Ethernet
```

The ZIP checksum can be copied from the release `.sha256` asset or calculated on another computer before transferring the file.

## 2. Install or upgrade

1. Install the exact release ZIP through **Kodi → Add-ons → Install from zip file**.
2. For an upgrade test, install it over the currently installed Managarr version without clearing add-on data.
3. Open **My add-ons → Context menus → Kodi Managarr → Information**.
4. Confirm the displayed version matches the ZIP.
5. Open settings with the TV remote and confirm every category, setting label and help line is readable.
6. Confirm the existing Radarr, Sonarr and path settings were preserved after an upgrade.

Evidence:

- screenshot or photo of the add-on information/version page;
- note whether this was a clean install or an upgrade and the previous version.

## 3. Verify the context menu

Use one Kodi-library movie, one TV show and one episode.

For each item:

1. Open Kodi's context menu.
2. Confirm the root item is shown exactly as **Managarr** with no missing-glyph box or emoji.
3. Open it and confirm these entries are visible:
   - Status
   - Search & download now
   - Monitoring
   - Download queue
   - Delete & Exclude
   - Delete & Replace
4. Open **Monitoring** and confirm:
   - Monitor
   - Unmonitor
   - Change quality profile
5. Open **Download queue** and confirm:
   - View status
   - Remove
6. Select **Status** and confirm a Kodi-native dialog opens rather than a browser or a silent failure.

Evidence:

- one screenshot/photo showing the complete root submenu;
- one showing each nested submenu;
- record movie, TV-show and episode as PASS or FAIL.

## 4. Verify configuration and read-only diagnostics

1. In Managarr settings, run **Test Radarr**.
2. Run **Test Sonarr**.
3. Confirm each reports the expected instance name and version.
4. Run **Write diagnostics**.
5. Confirm Kodi reports the path of `diagnostics.json`.
6. Check that the file contains versions and configuration shape but no API keys or passwords.

API-backend users may leave malformed or old VFS-only values unused; they must not prevent the Radarr/Sonarr connection tests or API actions from running. Repair those values before selecting the VFS backend.

## 5. Dry-run the destructive actions

Prepare one disposable movie and one disposable episode file. A multi-episode file is preferred for the episode check but is not mandatory for a quick validation.

1. Enable **Dry run**.
2. On the disposable movie, run **Delete & Exclude** and confirm the preview identifies the correct movie and no file or Radarr record changes.
3. Run **Delete & Replace** and confirm the preview identifies the correct movie and release/blocklist state without changing anything.
4. Repeat both actions on the disposable episode.
5. Confirm cancellation at the confirmation dialog leaves all state unchanged.

Evidence:

- record the selected titles and whether the predicted action was correct;
- confirm the files and Servarr records remained unchanged.

## 6. Execute one API-backend end-to-end mutation

This is the minimum destructive proof for the recommended backend.

1. Select **Servarr API** as the deletion backend.
2. Disable **Dry run**.
3. Use a disposable item whose file can be reacquired.
4. Run either:
   - **Delete & Replace** to prove blocklist → delete → search → Kodi synchronisation; or
   - **Delete & Exclude** to prove delete → exclusion → Kodi synchronisation.
5. Confirm the final notification reports success.
6. In Radarr/Sonarr, confirm the intended record/file state.
7. In Kodi, confirm the removed item or episode row is no longer stale.
8. For replacement, confirm a search command was accepted and the matched imported release was failed/blocklisted before deletion.

A second mutation on another media type is recommended for a major release but is not required to publish a small maintenance release when the automated suite covers that path.

## 7. Optional SMB/SFTP VFS validation

Complete this section only when the release is intended to support your direct VFS configuration.

1. Configure one explicit Servarr-to-Kodi child mapping. Never map a target broader than the required media root.
2. Ensure the mapping root is present in protected paths; Managarr also protects configured mapping roots automatically.
3. For SFTP, install/enable Kodi's official `vfs.sftp` add-on and verify the network location in Kodi first.
4. Run **Test file backend** on the selected disposable item.
5. Keep **Dry run** enabled and verify the mapped target shown is the correct child path.
6. Disable dry run and perform one disposable child-file delete/replace.
7. Confirm:
   - the child file was removed;
   - the mapping root remained intact;
   - Servarr rescan/reconciliation completed;
   - Kodi state was synchronised.

Record SMB and SFTP separately. Mark an untested optional backend as **NOT TESTED**, not PASS.

## 8. Quick failure checks

Perform at least these two safe negative checks:

1. Cancel a destructive confirmation and confirm no mutation occurs.
2. Temporarily enter an invalid API URL or disable the relevant service, run **Status**, and confirm a clear Kodi error appears without hanging. Restore the setting afterwards.

For a larger release, also interrupt network access during a disposable operation and verify the last transaction report accurately identifies any committed stage.

## 9. Collect evidence

Keep only sanitised evidence:

- completed summary below;
- submenu screenshots/photos;
- add-on version screenshot;
- ZIP SHA-256;
- Radarr/Sonarr versions;
- relevant `kodi.log` excerpt with API keys and credentials removed;
- `diagnostics.json`;
- optional Servarr history/command screenshots for the disposable mutation.

Do not publish full private URLs, API keys, SMB/SFTP credentials, or unrelated Kodi logs.

## 10. Completion summary

```markdown
# Managarr Android Kodi validation

- Result: PASS / PASS WITH LIMITATIONS / FAIL
- Managarr: vX.Y.Z
- ZIP SHA-256: ...
- Device/Kodi/skin: ...
- Radarr/Sonarr: ...
- Backend: ...

| Check | Result | Notes/evidence |
|---|---|---|
| Clean install or upgrade | PASS/FAIL | |
| Settings render and persist | PASS/FAIL | |
| Movie context menu | PASS/FAIL | |
| TV-show context menu | PASS/FAIL | |
| Episode context menu | PASS/FAIL | |
| Radarr connection test | PASS/FAIL | |
| Sonarr connection test | PASS/FAIL | |
| Dry-run movie actions | PASS/FAIL | |
| Dry-run episode actions | PASS/FAIL | |
| API end-to-end mutation | PASS/FAIL | |
| SMB VFS | PASS/FAIL/NOT TESTED | |
| SFTP VFS | PASS/FAIL/NOT TESTED | |
| Cancellation/no mutation | PASS/FAIL | |
| Diagnostics contain no secrets | PASS/FAIL | |

Known limitations:
- ...

Evidence locations:
- ...
```

## Release decision

A stable release is reasonably evidenced when:

- CI is green for the release commit;
- install/upgrade, menu dispatch, connection tests, dry runs and one disposable API mutation pass;
- any backend advertised as device-tested is explicitly tested above;
- no unresolved failure risks normal use or destructive safety.

A prerelease or release-candidate cycle is optional. Use it when the change is broad or when you want wider testing, not as a mandatory blocker for an owner-initiated stable release.

## 9. Retention Automation (Optional / Destructive)
1. Configure thresholds so exactly one watched movie is eligible.
2. Run `Preview eligible media` and confirm only that movie appears.
3. Run `Run cleanup now` with background dry-run enabled and confirm no changes.
4. Disable background dry-run and perform one real API-backend movie deletion through `Run cleanup now`.
5. Confirm Radarr exclusion and Kodi row cleanup.
6. Configure one disposable watched episode and verify multi-episode file warning if applicable.
7. Perform one episode cleanup manually.
8. Enable scheduled dry run with a short test interval.
9. Verify one background report appears in the add-on data folder.
10. Disable periodic cleanup.
11. Inspect logs and reports for secrets.
