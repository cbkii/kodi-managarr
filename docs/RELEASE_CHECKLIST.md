# Android TV and release acceptance checklist

Use disposable Radarr/Sonarr entries and sacrificial files. Record the Kodi version, add-on ZIP checksum, Radarr/Sonarr versions and deletion backend.

## Installation and upgrade

- [ ] Clean ZIP installation succeeds.
- [ ] Upgrade from v0.1.1 preserves every setting.
- [ ] Modern settings render and save using only the TV remote.
- [ ] Context submenu appears only for movie, TV show and episode library rows.
- [ ] Keymap Editor launches the complete Managarr menu.

## Non-destructive actions

- [ ] Status works for movie, series, missing episode and downloaded episode.
- [ ] Search completes for movie, series and episode.
- [ ] Monitor and unmonitor work for movie, series and episode.
- [ ] Series monitoring updates season scope as displayed.
- [ ] Quality profile changes work; episode changes are visibly series-wide.
- [ ] Queue view shows only matching items.
- [ ] Queue removal removes the chosen download without blocklisting it.

## Destructive API backend

- [ ] Dry-run results are accurate for every media type and action.
- [ ] Delete & Exclude works for movie, series and multi-episode file.
- [ ] Delete & Replace works for movie, series and multi-episode file.
- [ ] Specials (season zero) work.
- [ ] Cancellation performs no mutation.
- [ ] Strict history ambiguity performs no mutation.
- [ ] Search is never started after deletion or blocklist failure.

## Direct Kodi VFS backend

- [ ] Read-only backend test proves the selected item is accessible.
- [ ] SMB and SFTP child-file deletion work with Kodi-managed credentials.
- [ ] Mapping-root, share-root, ancestor, traversal and case-mismatch attempts fail closed.
- [ ] Direct deletion always confirms even when general confirmation is disabled.
- [ ] All files preflight before a multi-file mutation.
- [ ] Network loss during rescan reports the committed deletion stage.

## Command and Kodi synchronisation

- [ ] Completed/successful command is accepted.
- [ ] Completed/unsuccessful, failed, cancelled and orphaned commands surface as failure.
- [ ] Series replacement removes only Kodi episodes linked to deleted Sonarr file IDs.
- [ ] Missing and Kodi-only episode rows remain present.
- [ ] Kodi JSON-RPC failure after deletion is reported as post-commit failure.

## Publication

- [ ] CI passes on the exact release commit.
- [ ] ZIP is reproducible and checksum matches the release asset.
- [ ] `kodi-addon-checker --branch matrix` passes on the extracted ZIP.
- [ ] Release workflow environment approval is configured.
- [ ] Direct VFS deletion exception has been discussed with Kodi repository maintainers before official-repository submission.
