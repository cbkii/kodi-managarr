---
applyTo: "addon.xml,context.py,default.py,resources/settings.xml,resources/language/**,resources/lib/arr_manager/kodi.py,resources/lib/arr_manager/entrypoints.py,resources/lib/arr_manager/fileops.py"
---

# Kodi and Android runtime instructions

Apply `AGENTS.md` and verify Kodi contracts through the official links in `docs/AGENT_SOURCES.md`.

- Target Kodi 19+ Python 3 on Android TV unless the task explicitly changes support.
- Preserve the `context.arr.manager` add-on ID and Kodi-valid ZIP root.
- Keep `kodi.context.item`, unique `library`/`args` combinations, supported-item visibility, and `sys.listitem` handling correct.
- Prefer modern `InfoTagVideo` access with tested fallbacks for incomplete Android/skin metadata.
- Keep Kodi imports at adapter and entry-point boundaries so pure modules and unit tests run outside Kodi.
- Use `xbmcvfs` for all `smb://` and `special://` operations. Never use desktop filesystem APIs on VFS URLs.
- Use `special://profile` or `special://temp`; do not assume `/tmp` or arbitrary Android paths.
- Do not assume a system SSH binary or install native wheels into Kodi. Optional SFTP must fail clearly when its Python dependency is unavailable.
- Bound all network and polling operations; return control to Kodi on failure or cancellation.
- Treat hidden settings as plaintext secrets at rest. Redact keys, passwords, credentials and sensitive URLs from logs and diagnostics.
- Preserve setting IDs where possible; migrations require explicit compatibility logic and tests.
- Add every visible string to the language catalogue.
- Use Kodi dialogs and notifications for user interaction; do not bury destructive results only in logs.
- Test remote-control-friendly confirmation, cancellation, progress and error messages.
