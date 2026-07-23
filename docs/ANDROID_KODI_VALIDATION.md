# Android Kodi validation runbook

Use disposable Radarr/Sonarr entries and sacrificial media. Fresh installs should start with **Dry run** enabled. Keep it enabled until the relevant checks pass; disable it only for one explicitly disposable API-backend mutation, then re-enable it immediately. Record **NOT TESTED** for optional integrations outside the release claim.

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
2. Install it through **Add-ons -> Install from zip file**.
3. Install/upgrade **Kodi Managarr** through its repository.
4. Confirm the expected version and normal auto-update setting.
5. On a clean profile confirm **Dry run** starts enabled.
6. On upgrade, confirm menu mode/order, PIN, Arr/optional-service settings and an explicitly saved dry-run state remain intact.

## 3. Menus, direct modes and compatibility

Using a Kodi-library movie, show and episode:

1. Confirm the context root is exactly **Managarr** with no emoji or missing glyph.
2. In Advanced mode confirm all documented actions; in Simple mode confirm the reduced set.
3. Confirm Monitoring and Download queue child menus work.
4. Hide/reorder one action, restart Kodi, confirm persistence, then restore defaults.
5. Invoke one hidden action with `RunScript(...,mode=...)` and confirm it still dispatches.
6. Invoke a query-style encoded mode and confirm it URL-decodes correctly.
7. Confirm every destructive direct mode still requests the configured PIN.
8. Test an accented-Latin title and, where available, a CJK or Cyrillic title; confirm exact Arr matching does not collapse the title to empty text.

## 4. Episode parent-series identity

Use an episode with distinct episode and series TVDb IDs, ideally including a season-zero special.

1. Use the API deletion backend with no path mapping required for identity.
2. Run Status or Request & Search on the episode.
3. Confirm Sonarr resolves the parent series, not an unrelated entity matching the episode TVDb ID.
4. Confirm the selected season/episode is resolved exactly.
5. Repeat with a skin/view that exposes incomplete list-item metadata; Kodi JSON-RPC should supply parent TV-show title, year and stable IDs.
6. Confirm ambiguous title/year fallback stops for explicit resolution instead of choosing the first match.

## 5. PIN and existing safety

1. Create, change and remove a 4-8 digit PIN; reject malformed PINs.
2. Confirm Delete & Exclude and Delete & Replace require it from menu and direct modes.
3. Confirm cancellation/three wrong attempts make no change.
4. Confirm queue removal retains its normal confirmation but is not PIN-gated.
5. Complete movie/episode destructive checks with **Dry run** enabled.
6. Disable **Dry run**, perform only one explicitly disposable API-backend mutation, verify the result, then immediately re-enable **Dry run**.
7. Verify targeted Kodi cleanup and accurate transaction state.

## 6. Request & Search

Use disposable items.

1. Configure one root/profile for each enabled Arr service.
2. On a managed movie, confirm no duplicate is created, monitoring is enabled if needed and search completes.
3. On an unmanaged movie with a TMDb ID, confirm it is added once and searched.
4. On an unmanaged series, confirm it is added once and searched using the configured monitoring policy.
5. On an unmanaged episode, confirm the parent series is added if required but only the selected episode is monitored/searched.
6. Confirm ambiguous lookup asks for the exact title/year/ID.
7. Induce a search-command failure after a disposable add and confirm partial success is reported without deleting the new Arr entity.

## 7. Interactive release search and Dashboard

1. Open Interactive search for a managed disposable movie and episode.
2. Confirm results include useful quality/indexer/rejection detail.
3. Cancel once and confirm no download is queued.
4. Select and confirm one accepted disposable result; verify submission remains through Radarr/Sonarr.
5. Confirm TV-show rows explain unsupported full-series interactive selection.
6. Optional: with Prowlarr enabled and no Arr results, confirm it is informational only.
7. Open Dashboard with one deliberately unavailable optional service; healthy services must still render without secret URLs.
8. Confirm refresh is manual and Kodi remains responsive.

## 8. Bazarr subtitle integration

1. Enable Bazarr and run its connection test.
2. Configure one base language, then three ordered unique languages.
3. For a base language such as `en`, confirm normal, forced and hearing-impaired variants can appear in configured order.
4. Configure a qualified language such as `en:forced` and confirm normal/HI variants are excluded.
5. Start playback of a Kodi-library movie, open Kodi's built-in subtitle search and select Kodi Managarr/Bazarr.
6. Select one result and confirm Kodi receives and loads that exact provider result.
7. Attempt to select the same stale result token again; it must fail safely without a second provider request.
8. Repeat for a Kodi-library episode and confirm parent-series identity resolves correctly.
9. Confirm a server-only path is never passed directly to Android Kodi; configure a path mapping where required.
10. Confirm disabled Bazarr, no languages, no results and malformed responses close the subtitle directory with a reported failure rather than caching a broken result.
11. Inspect the add-on profile: short-lived result files contain no media path, API key, service URL or credentials and expire/are consumed.

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
| Fresh-install Dry run default | PASS/FAIL | |
| Movie/show/episode Managarr root and menus | PASS/FAIL | |
| Menu hide/order/direct-mode and PIN boundary | PASS/FAIL | |
| Episode parent-series identity / season zero | PASS/FAIL | |
| International-title matching | PASS/FAIL | |
| Request & Search: managed/unmanaged movie | PASS/FAIL | |
| Request & Search: series/selected episode | PASS/FAIL | |
| Interactive release search/grab | PASS/FAIL | |
| Dashboard partial-service failure | PASS/FAIL | |
| Bazarr movie/episode subtitle load | PASS/FAIL/NOT TESTED | |
| Base/forced/HI language filtering and token replay | PASS/FAIL/NOT TESTED | |
| API deletion end-to-end | PASS/FAIL | |
| SMB / SFTP VFS | PASS/FAIL/NOT TESTED | |
| Logs/diagnostics/cache contain no secrets | PASS/FAIL | |

Known limitations:
- ...

Evidence locations:
- ...
```

A stable release is reasonably evidenced when CI is green, repository install/update succeeds, upgrade state is preserved, menus/PIN work with a TV remote, parent-series identity and core Arr actions pass, one disposable API mutation passes, and each newly claimed optional feature is verified or explicitly marked **NOT TESTED**.
