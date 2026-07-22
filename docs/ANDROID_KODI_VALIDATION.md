# Android Kodi validation runbook

Use disposable Radarr/Sonarr entries and sacrificial media. Keep both the global **Dry run** and retention **Background dry run** enabled until their checks pass. Do not publish URLs, API keys, SMB/SFTP credentials or unrelated Kodi logs.

## 1. Record the environment

```text
Date/time:
Tester:
Android TV model / OS family / Android version:
Kodi version / skin:
Managarr version:
Repository ZIP filename and SHA-256:
Clean install or upgrade from:
Radarr version:
Sonarr version:
Normal deletion backend: API / SMB VFS / SFTP VFS
Network: Wi-Fi / Ethernet
```

## 2. Install or upgrade

1. Verify and install `repository.managarr-X.Y.Z.zip`.
2. Install or upgrade Kodi Managarr through the repository.
3. Confirm the expected version under **My add-ons → Context menus → Kodi Managarr**.
4. For upgrades, confirm Radarr/Sonarr, menu, PIN, dry-run and retention settings persist.
5. Confirm Kodi auto-update remains enabled.

## 3. Menu and PIN smoke test

1. On one movie, TV show and episode, confirm the context root is exactly **Managarr**.
2. In Advanced mode confirm Status, Search, Monitoring, Download queue, both Delete actions, Retention and Tools are present.
3. Confirm Retention contains Preview, Run, Enable, Disable and Report.
4. Confirm Simple mode omits Retention by default.
5. Hide/reorder one action, restart Kodi and verify persistence; restore defaults.
6. Confirm a hidden direct `RunScript(...,mode=...)` action remains callable.
7. Create a 4–8 digit PIN; verify cancellation and three wrong attempts stop a destructive action.
8. Confirm queue removal retains normal confirmation but is not PIN-gated.

## 4. Connection and existing actions

1. Run **Test Radarr** and **Test Sonarr**.
2. With global Dry run enabled, verify Delete & Exclude and Delete & Replace identify the correct disposable movie and episode without mutation.
3. Perform one disposable API-backend mutation and verify Servarr and Kodi state.
4. Confirm diagnostics/logs expose no credentials.

## 5. Configure retention safely

1. Enable Retention.
2. Include movies and episodes.
3. Keep **Watched only**, both age criteria and **All criteria** enabled.
4. Choose thresholds so exactly one watched disposable movie is eligible.
5. Keep global Dry run and Background dry run enabled.
6. Set a small batch cap such as 1–2.
7. Confirm `0` means immediate after a valid timestamp exists and that `9999` is accepted.

## 6. Preview eligibility

1. Run **Preview eligible media**.
2. Confirm only the intended movie appears and the displayed added/watched age is correct.
3. Confirm an unwatched item is skipped.
4. Confirm an item below either threshold is skipped in **All** mode.
5. Change to **Any** mode and confirm an item passing one enabled age criterion becomes eligible.
6. View the last report and confirm candidate/count/reason data contains no paths, URLs or credentials.

## 7. Manual dry run

1. Run **Run cleanup now** with global Dry run enabled.
2. Confirm no PIN prompt is shown because no deletion can occur.
3. Confirm the aggregate prompt and progress dialog identify the correct bounded batch.
4. Cancel before a candidate and confirm no change.
5. Complete the dry run and confirm Radarr, Sonarr, files and Kodi rows are unchanged.

## 8. Manual real movie cleanup

1. Select the Servarr API backend and disable global Dry run.
2. Run cleanup with exactly one disposable eligible movie.
3. Cancel the PIN prompt and confirm no mutation.
4. Re-run with the correct PIN and approve the aggregate confirmation.
5. Confirm the movie is removed through Radarr with files and import exclusion.
6. Confirm the targeted Kodi movie row is removed/updated.
7. Confirm the report says committed/deleted and records no path or credential.

## 9. Episode and multi-episode cleanup

1. Prepare one disposable watched episode file; a file containing two episodes is preferred.
2. Confirm Preview shows one physical-file candidate, not duplicate rows.
3. For a multi-episode file, mark only one linked Kodi episode watched and confirm it is ineligible; mark all watched and confirm eligibility.
4. Run one real cleanup.
5. Confirm every Sonarr episode linked to the physical file is unmonitored and exactly one episode file is deleted.
6. Confirm the affected Kodi episode rows are removed/updated while the TV-show row remains.
7. Where safe, induce a failure before file deletion and verify monitoring is restored.

## 10. Periodic dry run

1. Re-enable Background dry run.
2. Set a short safe test interval and enable periodic cleanup.
3. Confirm enabling a dry-run schedule does not request the destructive PIN.
4. Restart Kodi and wait for one due pass.
5. Confirm no modal dialog opens, one report is written and no media changes occur.
6. Confirm the batch cap and next-due time are recorded.
7. Enable twice/concurrently where practical and confirm only one run owns the lock.

## 11. Periodic real authorisation

1. With disposable media only, disable Background dry run.
2. Enable periodic cleanup and confirm the configured PIN is required.
3. Before it runs, change the PIN; confirm periodic real cleanup is disabled/invalidated and no deletion occurs.
4. Re-enable with the new PIN and allow one due candidate to complete.
5. Confirm the same fresh revalidation/API-only deletion semantics as manual cleanup.
6. Disable periodic cleanup without a PIN and confirm no next candidate executes.
7. Restore Background dry run before normal use unless real automation is intentionally desired.

## 12. Shutdown, failure and privacy checks

1. Restart/stop Kodi during the service wait and confirm it exits promptly without a busy loop.
2. Interrupt network access before mutation and confirm no deletion.
3. Interrupt after a disposable committed deletion and confirm the report states the commit occurred rather than claiming rollback.
4. Inspect `retention-state.json`, `retention-last-report.json` and `kodi.log`; confirm no paths, URLs, API keys, passwords or credentials appear.
5. Confirm scheduled retention never performs VFS/SMB/SFTP deletion or whole-series deletion.

## Completion summary

```markdown
# Managarr Android Kodi validation

- Result: PASS / PASS WITH LIMITATIONS / FAIL
- Managarr: vX.Y.Z
- Device/Kodi/skin: ...
- Radarr/Sonarr: ...
- Install type: clean / upgrade from ...

| Check | Result | Notes/evidence |
|---|---|---|
| Repository install/update | PASS/FAIL | |
| Settings/menu/PIN preserved | PASS/FAIL | |
| Context root and runtime menus | PASS/FAIL | |
| Existing dry-run and API mutation | PASS/FAIL | |
| Retention preview/reasons | PASS/FAIL | |
| Manual dry run | PASS/FAIL | |
| Manual real movie cleanup | PASS/FAIL | |
| Episode/multi-episode cleanup | PASS/FAIL/NOT TESTED | |
| Monitoring rollback | PASS/FAIL/NOT TESTED | |
| Scheduled dry run | PASS/FAIL | |
| Real schedule PIN invalidation | PASS/FAIL/NOT TESTED | |
| Lock/shutdown behaviour | PASS/FAIL | |
| Reports/logs contain no secrets | PASS/FAIL | |

Known limitations:
- Whole-series automatic deletion is not implemented.
- Retention uses Servarr API only; unattended VFS deletion is not implemented.

Evidence locations:
- ...
```

A stable release is reasonably evidenced when CI is green, installation/upgrade succeeds, existing actions remain stable, the retention dry-run path passes, at least one disposable real API cleanup passes, scheduled dry-run/PIN invalidation works, and no unresolved issue risks destructive safety.
