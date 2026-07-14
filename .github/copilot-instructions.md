# GitHub Copilot instructions

Read and obey `AGENTS.md` before planning, coding, reviewing, or answering repository questions. Consult `docs/AGENT_SOURCES.md` before changing any Kodi, Radarr, Sonarr, Prowlarr, packaging, or release contract.

## Repository purpose

This is `context.arr.manager`, a Kodi 19+ Python 3 context-menu add-on for Android TV. It safely performs Radarr movie and Sonarr series/episode actions through Servarr APIs, Kodi SMB/VFS, or optional SFTP. Destructive actions must fail closed.

## Work autonomously

- Inspect the relevant implementation, tests, docs, complete PR discussion, and full CI logs.
- Verify external contracts against current official docs, live OpenAPI, or upstream source; do not rely on memory.
- Implement the complete scoped solution, add tests, run validation, fix failures, and inspect the final diff.
- Do not leave placeholders, TODO-only work, incomplete error handling, or an untested happy path.
- Do not broaden scope with unrelated refactors.

## Critical design rules

- Radarr and Sonarr API operations are authoritative; never edit their databases or config files.
- Radarr/Sonarr normally use API v3. Prowlarr uses API v1 and must have a separate client boundary.
- Prowlarr manages indexers/applications; it does not own Radarr/Sonarr media deletion or blocklists.
- Resolve media by stable IDs first: TMDb for movies, TVDb for series, then canonical paths, then exact normalised title/year. Reject ambiguous matches.
- `Delete & Replace` must identify imported history before deletion, use Servarr's failed-history/blocklist path, and search only after prerequisites succeed.
- Preserve multi-episode-file handling.
- For direct SMB/SFTP deletion, rescan and poll Servarr until reconciliation succeeds.
- Use `xbmcvfs` for `smb://` and `special://`; never pass Kodi VFS URLs to `os`, `pathlib`, `shutil`, shell commands, or subprocesses.
- Never assume Android Kodi has `/tmp`, `ssh`, systemd, desktop keyrings, unrestricted storage, or binary Python wheels.
- Protect root paths, SMB share roots, configured media roots, protected paths, and their ancestors from recursive deletion.
- Keep TLS verification enabled by default, bound network operations with timeouts, and redact all secrets.
- Hidden Kodi settings are stored unencrypted. Never log or export them.
- Keep pure logic importable without Kodi modules.
- Localise every user-visible runtime string.

## Repository navigation

- Orchestration/destructive ordering: `resources/lib/arr_manager/actions.py`
- API adapters: `resources/lib/arr_manager/clients.py`
- HTTP/auth/errors: `resources/lib/arr_manager/http.py`
- Entity resolution: `resources/lib/arr_manager/resolver.py`
- Imported-history matching: `resources/lib/arr_manager/history.py`
- VFS/SFTP: `resources/lib/arr_manager/fileops.py`
- Kodi adapter/UI: `resources/lib/arr_manager/kodi.py`
- Settings/path mapping: `resources/lib/arr_manager/config.py`
- Kodi manifest/settings/languages: `addon.xml`, `resources/settings.xml`, `resources/language/`
- Architecture: `docs/ARCHITECTURE.md`
- Source knowledgebase: `docs/AGENT_SOURCES.md`

## Required validation

Run from the repository root after every change, including documentation or workflow changes where applicable:

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
python3 scripts/package.py
```

Inspect the produced ZIP and confirm every entry is under `context.arr.manager/`, required runtime files exist, no development directories leaked, and `ZipFile.testzip()` returns `None`. Do not commit `dist/` output.

For changed behaviour, add tests covering success, ambiguity, dry run, cancellation, destructive safety, partial failure, API errors/timeouts, secret redaction, Unicode/spaces, reverse-proxy base paths, and multi-episode files as applicable.

## Review output

A review must prioritise correctness and safety over style. Report actionable findings with file/line evidence, explain why each matters, and distinguish valid, stale, duplicate, already-fixed, out-of-scope, and human-decision items. Resolve a thread only when the underlying issue is actually complete.

In the final response include the implementation summary, files changed, exact validation results, external sources consulted, device/integration testing status, and residual risks.
