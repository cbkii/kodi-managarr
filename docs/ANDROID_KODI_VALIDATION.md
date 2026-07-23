# Android Kodi validation runbook

Use disposable Radarr/Sonarr entries and sacrificial media. Keep **Dry run** enabled until the relevant dry-run checks pass. Record **NOT TESTED** for optional integrations that are not part of the release claim.

## 1. Record the environment

```text
Date/time:
Tester:
Android TV model / Android OS:
Kodi version / skin:
Managarr version:
Repository ZIP filename and SHA-256:
Clean install / upgrade from:
Radarr / Sonarr versions:
Prowlarr / Bazarr versions, if tested:
Deletion backend: API / SMB VFS / SFTP VFS
Network: Wi-Fi / Ethernet
```

Never publish API keys, private URLs, credentials or unrelated Kodi logs.

## 2. Install or upgrade

1. Verify the exact `repository.managarr-X.Y.Z.zip` checksum.
2. Install it through **Add-ons → Install from zip file**.
3. Install/upgrade **Kodi Managarr** through its repository.
4. Confirm the expected version and normal auto-update setting.
5. On upgrade, confirm menu mode/order, PIN, Arr/optional-service settings and dry-run state remain intact.

## 3. Menus and direct modes

Using a Kodi-library movie, show and episode:

1. Confirm the context root is exactly **Managarr** with no emoji or missing glyph.
2. In Advanced mode confirm the documented actions appear, including Request & Search, Interactive search, Dashboard, subtitles, existing management/delete actions and Tools.
3. Confirm Monitoring and Download queue child menus work.
4. In Simple mode confirm the reduced common set.
5. Hide/reorder one action, restart Kodi, confirm persistence, then restore defaults.
6. Invoke one hidden action with `RunScript(...,mode=...)` and confirm it still dispatches.

## 4. PIN and existing safety

1. Create, change and remove a 4–8 digit PIN; reject malformed PINs.
2. Confirm Delete & Exclude and Delete & Replace require it from menu and direct modes.
3. Confirm cancellation/three wrong attempts make no change.
4. Confirm queue removal retains its normal confirmation but is not PIN-gated.
5. Complete existing movie/episode destructive dry runs and one disposable API-backend mutation.
6. Verify targeted Kodi cleanup and accurate transaction state.

## 5. Request & Search

Use disposable items.

1. Run **Configure Request & Search defaults** and select one root/profile for each enabled Arr service.
2. On a managed movie, run Request & Search and confirm no duplicate is created, monitoring is enabled if needed, and the Radarr search completes.
3. On an unmanaged movie with a TMDb ID, confirm it is added once to the stored defaults and searched.
4. On an unmanaged series, confirm it is added once and searched using the configured monitoring policy.
5. On an unmanaged episode, confirm the parent series is added if required but only the selected episode is monitored/searched.
6. Where lookup is ambiguous, confirm Kodi asks for the exact title/year/ID rather than selecting the first result.
7. Induce a search-command failure after a disposable add and confirm Managarr reports partial success without deleting the new Arr entity.

## 6. Interactive release search

1. Select a managed disposable movie and open **Interactive search**.
2. Confirm results show title, quality, size, indexer, protocol/peers where available, accepted/rejected state and rejection reasons.
3. Open details, cancel, and confirm no download is queued.
4. Repeat, select an accepted result, confirm, and verify it is submitted through Radarr/Sonarr and appears in the Arr/download-client flow.
5. For a selected episode, repeat the test through Sonarr.
6. Confirm a TV-show row explains that full-series interactive selection is unsupported rather than failing silently.
7. Optional: when Arr returns no results and Prowlarr is enabled, confirm Prowlarr is shown as informational only and no direct Prowlarr download occurs.

## 7. Dashboard MVP

1. Open Dashboard with Radarr/Sonarr healthy and confirm versions, health counts, bounded queue/problem counts and missing totals.
2. Enable Prowlarr/Bazarr and confirm their status appears.
3. Temporarily make one optional service unavailable; confirm the other services still render and no secret/URL is shown.
4. Confirm refresh is manual and Kodi remains responsive.

## 8. Bazarr subtitle integration

1. Enable Bazarr and run its connection test.
2. Use **Configure subtitle languages** to choose one language; repeat with three ordered unique languages.
3. Start playback of a Kodi-library movie, open Kodi's built-in subtitle search, and select Kodi Managarr/Bazarr.
4. Confirm only configured language/forced/HI combinations appear.
5. Select one result and confirm Kodi receives and loads a real accessible subtitle file.
6. Repeat for a Kodi-library episode.
7. Confirm a Debian/server-only path is never passed directly to Android Kodi; configure a path mapping where required.
8. Confirm disabled Bazarr, no configured languages, no results and unsupported/malformed responses produce concise Kodi errors and always close the subtitle directory cleanly.
9. Inspect the add-on profile: cached subtitle-result files should contain no API key, URL or media-server credentials and should expire.

## 9. Diagnostics and optional VFS

1. Run all configured service connection tests.
2. Write diagnostics and confirm no credentials/private URLs.
3. Test SMB/SFTP only when claimed. Confirm mapped roots remain protected and mark untested backends **NOT TESTED**.

## 10. Evidence summary

```markdown
# Managarr Android Kodi validation

- Result: PASS / PASS WITH LIMITATIONS / FAIL
- Managarr / Kodi / device / skin: ...
- Repository ZIP/SHA-256: ...
- Radarr/Sonarr/Prowlarr/Bazarr: ...

| Check | Result | Notes/evidence |
|---|---|---|
| Repository install/update and settings preservation | PASS/FAIL | |
| Movie/show/episode Managarr root and menus | PASS/FAIL | |
| Menu hide/order/direct-mode behavior | PASS/FAIL | |
| PIN and existing destructive safety | PASS/FAIL | |
| Request & Search: managed/unmanaged movie | PASS/FAIL | |
| Request & Search: series/selected episode | PASS/FAIL | |
| Interactive release search/grab | PASS/FAIL | |
| Dashboard partial-service failure | PASS/FAIL | |
| Bazarr movie/episode subtitle load | PASS/FAIL/NOT TESTED | |
| One/three language filtering | PASS/FAIL/NOT TESTED | |
| API deletion end-to-end | PASS/FAIL | |
| SMB / SFTP VFS | PASS/FAIL/NOT TESTED | |
| Logs/diagnostics/cache contain no secrets | PASS/FAIL | |

Known limitations:
- ...

Evidence locations:
- ...
```

A stable release is reasonably evidenced when CI is green, repository install/update succeeds, upgrade state is preserved, menus/PIN work with a TV remote, core Arr actions and dry runs pass, one disposable API mutation passes, and each newly claimed interactive/optional feature above is either verified or explicitly marked not tested.
