# Security policy

Report vulnerabilities privately through GitHub's security-advisory feature rather than a public issue, especially anything involving path traversal, unintended deletion, API-key disclosure, cross-origin redirects or incorrect entity resolution.

Kodi stores hidden add-on settings unencrypted. Radarr and Sonarr API keys are therefore secrets at rest but are not encrypted by Kodi. Managarr excludes them from logs, exceptions and diagnostics.

Direct Kodi VFS deletion is optional, always confirms, and is restricted to explicitly mapped child paths. Servarr API deletion remains the recommended backend.
