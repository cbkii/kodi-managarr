# Android Kodi validation runbook

This is the practical device check for a stable Managarr release. Use disposable Radarr/Sonarr entries and sacrificial media. Keep **Dry run** enabled until the dry-run checks pass.

## 1. Record the test environment

```text
Date/time:
Tester:
Android TV model:
Android version / OS family:
Kodi version:
Kodi skin:
Managarr version:
Repository ZIP filename and SHA-256:
Add-on version installed through repository:
Radarr version:
Sonarr version:
Deletion backend tested: API / SMB VFS / SFTP VFS
vfs.sftp version, if used:
Network connection: Wi-Fi / Ethernet
Clean install / upgrade from version:
```

Do not publish private URLs, API keys, SMB/SFTP credentials or unrelated Kodi logs.

## 2. Install the repository and add-on

1. Download the exact `repository.managarr-X.Y.Z.zip` from the project Pages site.
2. Confirm its SHA-256 against the adjacent `.sha256` file.
3. In Kodi, enable **Unknown sources** if required.
4. Open **Add-ons → Install from zip file** and install the repository ZIP.
5. Open **Install from repository → Kodi Managarr Repository → Context menus**.
6. Confirm **Kodi Managarr** is listed with the expected stable version and install it.
7. Open **My add-ons → Context menus → Kodi Managarr → Information** and confirm the installed version.
8. Confirm Kodi's normal add-on auto-update setting is enabled.

Evidence:

- repository ZIP filename and checksum;
- repository and add-on information/version screenshots;
- note whether this was a clean install or upgrade.

## 3. Verify upgrade and automatic-update behaviour

For an upgrade test, start with the previous stable release and do not clear add-on data.

1. Record the current menu mode, hidden/order customisation, PIN state, Radarr/Sonarr settings and dry-run state.
2. Publish or expose the next stable version in the repository feed.
3. In Kodi, run **Check for updates** or wait for the normal update check.
4. Confirm Kodi offers the intended newer stable version—not a draft or prerelease.
5. Install the update through the repository.
6. Confirm all recorded settings remain intact.
7. Confirm stale or unknown stored menu IDs do not appear and do not break the menu.

## 4. Verify the context root and Advanced mode

Use one Kodi-library movie, one TV show and one episode.

For each item:

1. Open Kodi's context menu.
2. Confirm the root item is exactly **Managarr**, with no missing-glyph box, emoji or decorative prefix.
3. Open it and confirm Advanced mode exposes:
   - Status
   - Search & download now
   - Monitoring
   - Download queue
   - Delete & Exclude
   - Delete & Replace
   - Tools & settings
4. Open **Monitoring** and confirm:
   - Monitor
   - Unmonitor
   - Change quality profile
5. Open **Download queue** and confirm:
   - View status
   - Remove
6. Select **Status** and confirm a Kodi-native dialog opens rather than a browser or silent failure.

## 5. Verify Simple mode and menu customisation

1. Change **Menu mode** to **Simple**.
2. Confirm the root menu contains:
   - Status
   - Search & download now
   - Delete & Exclude
   - Delete & Replace
   - Tools & settings
3. Return to Advanced mode.
4. Open **Configure menu** using only the TV remote.
5. Hide one non-destructive action, move another action up or down, then save.
6. Reopen the menu and confirm visibility and order persisted.
7. Invoke the hidden action through a direct `RunScript(...,mode=...)` key mapping and confirm it remains callable.
8. Choose **Restore defaults** and confirm all registered actions return in default order.
9. Restart Kodi and confirm the final state persists.

## 6. Verify PIN protection

Use only disposable media.

1. Open **Manage PIN** and create a 4-digit PIN.
2. Confirm PIN entry is masked.
3. Attempt a 3-digit, 9-digit and non-numeric PIN and confirm each is rejected.
4. With **Dry run** enabled, invoke **Delete & Exclude** from the menu:
   - cancel the PIN prompt and confirm the action does not proceed;
   - enter an incorrect PIN three times and confirm the action is cancelled;
   - enter the correct PIN and confirm the normal destructive confirmation/dry-run flow opens.
5. Repeat the direct-mode path using `RunScript(...,mode=delete_replace)` and confirm the PIN is still required.
6. Open **Download queue → Remove** and confirm it uses its normal explicit confirmation but does not request the media-deletion PIN.
7. Change the PIN and confirm the old PIN no longer works.
8. Remove the PIN and confirm destructive actions no longer show a PIN prompt, while normal confirmations remain.
9. Optional repair check: deliberately corrupt only disposable local PIN settings, then confirm destructive actions fail closed and **Manage PIN** offers a reset path.

PIN protection prevents accidental local use; it is not a security boundary against a user who can modify Kodi's local add-on data.

## 7. Verify configuration and read-only diagnostics

1. Run **Test Radarr** and **Test Sonarr**.
2. Confirm each reports the expected instance name and version.
3. Run **Write diagnostics**.
4. Confirm Kodi reports the path of `diagnostics.json`.
5. Check that it contains versions and configuration shape but no API keys, passwords or credential-bearing URLs.
6. Confirm a missing prior transaction-state file produces no warning.
7. Confirm malformed or unreadable transaction state reports only the exception type, not sensitive content.

API-backend users may leave malformed or old VFS-only values unused; they must not prevent API actions. Repair those values before selecting the VFS backend.

## 8. Dry-run destructive actions

Prepare one disposable movie and one disposable episode file. A multi-episode file is preferred.

1. Enable **Dry run**.
2. On the disposable movie, run **Delete & Exclude** and confirm the preview identifies the correct movie and makes no change.
3. Run **Delete & Replace** and confirm the preview identifies the correct movie and release/blocklist state without changing anything.
4. Repeat both actions on the disposable episode.
5. Confirm cancellation at each confirmation stage leaves all state unchanged.

## 9. Execute one API-backend end-to-end mutation

1. Select **Servarr API** as the deletion backend.
2. Disable **Dry run**.
3. Use a disposable item whose file can be reacquired.
4. Run either:
   - **Delete & Replace** to prove blocklist → delete → search → Kodi synchronisation; or
   - **Delete & Exclude** to prove delete → exclusion → Kodi synchronisation.
5. Confirm the final notification reports success.
6. In Radarr/Sonarr, confirm the intended record/file state.
7. In Kodi, confirm removed rows are not stale.
8. For an episode exclusion involving linked episodes, confirm Sonarr monitoring is changed or restored as one coherent operation if a pre-delete failure is induced.

## 10. Optional SMB/SFTP VFS validation

Complete this only when the release is intended to support your direct VFS configuration.

1. Configure one explicit Servarr-to-Kodi child mapping. Never map a target broader than the required media root.
2. Ensure the mapping root is protected; Managarr also protects configured mapping roots automatically.
3. For SFTP, install and enable Kodi's official `vfs.sftp` add-on and verify the network location in Kodi first.
4. Run **Test file backend** on the selected disposable item.
5. Keep **Dry run** enabled and verify the mapped target is the correct child path.
6. Disable dry run and perform one disposable child-file delete or replace.
7. Confirm the child was removed, the mapping root remained intact, Servarr reconciliation completed and Kodi state synchronised.

Mark an untested optional backend **NOT TESTED**, not PASS.

## 11. Quick failure checks

1. Cancel a destructive confirmation and confirm no mutation occurs.
2. Temporarily enter an invalid API URL or disable the relevant service, run **Status**, and confirm a clear Kodi error appears without hanging. Restore the setting afterwards.
3. Interrupt network access during a disposable operation and verify the last transaction report accurately identifies committed stages.
4. Confirm a progress-dialog close failure cannot replace the primary operation result and is logged without secrets.

## 12. Completion summary

```markdown
# Managarr Android Kodi validation

- Result: PASS / PASS WITH LIMITATIONS / FAIL
- Managarr: vX.Y.Z
- Repository ZIP/SHA-256: ...
- Device/Kodi/skin: ...
- Radarr/Sonarr: ...
- Backend: ...

| Check | Result | Notes/evidence |
|---|---|---|
| Repository ZIP install | PASS/FAIL | |
| Install/update through repository | PASS/FAIL | |
| Settings preserved on upgrade | PASS/FAIL | |
| Movie/TV/episode context root | PASS/FAIL | |
| Advanced menu complete | PASS/FAIL | |
| Simple menu | PASS/FAIL | |
| Hide/reorder/restore persistence | PASS/FAIL | |
| Hidden direct mode remains callable | PASS/FAIL | |
| PIN create/change/remove | PASS/FAIL | |
| PIN menu and direct-mode enforcement | PASS/FAIL | |
| Queue removal confirmation-only | PASS/FAIL | |
| Radarr/Sonarr tests | PASS/FAIL | |
| Dry-run movie/episode actions | PASS/FAIL | |
| API end-to-end mutation | PASS/FAIL | |
| SMB VFS | PASS/FAIL/NOT TESTED | |
| SFTP VFS | PASS/FAIL/NOT TESTED | |
| Diagnostics contain no secrets | PASS/FAIL | |

Known limitations:
- ...

Evidence locations:
- ...
```

## Release decision

A stable release is reasonably evidenced when CI is green, repository installation and update succeeds, upgrade state is preserved, menu and PIN paths work with a TV remote, connection tests and dry runs pass, one disposable API mutation passes, and no unresolved failure risks normal use or destructive safety.
