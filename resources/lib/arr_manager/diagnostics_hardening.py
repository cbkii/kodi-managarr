# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail-closed diagnostics normalisation and optional Bazarr evidence."""

import json
import os


def normalise_transaction_candidate(candidate):
    """Return independently normalised non-secret fields without dropping the record."""
    if not isinstance(candidate, dict):
        return candidate
    output = dict(candidate)
    stages = candidate.get("stages")
    output["stages"] = [value for value in stages if isinstance(value, str)][:20] if isinstance(stages, list) else []

    command_id = candidate.get("commandId")
    if isinstance(command_id, bool):
        output["commandId"] = 0
    elif isinstance(command_id, int):
        output["commandId"] = command_id if command_id > 0 else 0
    elif isinstance(command_id, str) and command_id.strip().isdigit():
        parsed = int(command_id.strip())
        output["commandId"] = parsed if parsed > 0 else 0
    else:
        output["commandId"] = 0
    return output


def bazarr_diagnostics(settings, logger, client_class):
    """Return bounded read-only Bazarr health evidence without endpoint or credential data."""
    cfg = settings.bazarr
    output = {
        "enabled": bool(cfg.enabled),
        "configured": bool(cfg.url and cfg.api_key),
        "languageCount": len(settings.bazarr_languages),
        "version": "",
        "lastOperation": "",
        "lastCategory": "not_run",
        "lastHttpStatus": None,
    }
    if not output["enabled"] or not output["configured"]:
        return output
    client = client_class(cfg.url, cfg.api_key, cfg.timeout, cfg.verify_tls, logger, cfg.user_agent)
    try:
        status = client.status()
        output["version"] = str(status.get("bazarr_version") or status.get("version") or "")[:80]
        output["availableLanguageCount"] = len(client.languages())
    except Exception as exc:
        output["lastOperation"] = str(getattr(exc, "operation", client.last_operation) or "request")[:80]
        output["lastCategory"] = str(getattr(exc, "category", client.last_category) or "api")[:40]
        status = getattr(exc, "status", client.last_status)
        output["lastHttpStatus"] = status if isinstance(status, int) else None
        return output
    output["lastOperation"] = str(client.last_operation or "languages")[:80]
    output["lastCategory"] = str(client.last_category or "success")[:40]
    output["lastHttpStatus"] = client.last_status if isinstance(client.last_status, int) else None
    return output


def _augment_bazarr_file(addon, settings, logger, client_class):
    try:
        import xbmcvfs
        profile = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
        path = os.path.join(profile, "diagnostics.json")
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            return
        payload["bazarr"] = bazarr_diagnostics(settings, logger, client_class)
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except (OSError, ValueError) as exc:
        if logger:
            logger.warning("Could not add non-secret Bazarr diagnostics: %s", type(exc).__name__)


def install(entrypoints_module):
    """Wrap diagnostics before ``run_script`` can dispatch it."""
    if getattr(entrypoints_module, "_transaction_normalisation_installed", False):
        return
    original = entrypoints_module._write_diagnostics

    def hardened_write_diagnostics(addon, settings, logger):
        original_load = entrypoints_module.json.load

        def safe_load(handle):
            return normalise_transaction_candidate(original_load(handle))

        entrypoints_module.json.load = safe_load
        try:
            result = original(addon, settings, logger)
        finally:
            entrypoints_module.json.load = original_load
        _augment_bazarr_file(addon, settings, logger, entrypoints_module.BazarrClient)
        return result

    entrypoints_module._write_diagnostics = hardened_write_diagnostics
    entrypoints_module._transaction_normalisation_installed = True
