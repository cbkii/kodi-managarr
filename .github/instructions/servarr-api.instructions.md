---
applyTo: "resources/lib/arr_manager/actions.py,resources/lib/arr_manager/clients.py,resources/lib/arr_manager/http.py,resources/lib/arr_manager/resolver.py,resources/lib/arr_manager/history.py,resources/lib/arr_manager/config.py,tests/**"
---

# Servarr API and destructive-workflow instructions

Apply `AGENTS.md` and consult the matching Radarr, Sonarr, or Prowlarr source/API links in `docs/AGENT_SOURCES.md` before changing a request or workflow.

- Radarr and Sonarr normally use API v3. Prowlarr currently uses API v1. Never assume endpoint parity.
- Keep Prowlarr in a separate client/version boundary and do not use it for media-file deletion or blocklisting.
- Prefer Servarr API deletion over direct filesystem deletion.
- Never edit Servarr databases, app-data files, history, blocklists, queue state, root folders or configuration directly.
- Resolve entities by stable external IDs first and reject ambiguous matches.
- Validate response shapes before using fields in destructive decisions.
- `Delete & Replace` must preflight imported-history evidence before deletion and must not search after failed deletion, reconciliation or blocklisting.
- Preserve `DownloadFolderImported`/event-type matching only after verifying the target version and upstream enum.
- Preserve multi-episode-file relationships and restore monitoring state after a failed episode exclusion.
- Direct VFS/SFTP deletion requires rescan plus bounded API polling until the file record disappears.
- Treat commands as asynchronous. Poll returned command IDs when subsequent correctness depends on completion.
- Keep API-key authentication, reverse-proxy base paths, query encoding, TLS defaults and explicit timeouts correct.
- Do not retry non-idempotent destructive requests without proving duplicate safety.
- Redact API keys, passwords, credential-bearing URLs and private paths from logs/errors where disclosure is unnecessary.
- Tests must cover exact method/path/query/body contracts, 401/403/404/409/422/429/5xx handling, timeouts, malformed JSON, partial failure, dry run, cancellation, ambiguity, strict blocklist mode and path safety as applicable.
