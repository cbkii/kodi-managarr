import json
import os
import sys
import time

from .actions import ArrManager
from .clients import RadarrClient, SonarrClient
from .config import Settings
from .errors import ArrManagerError
from .fileops import make_direct_backend
from .kodi import KodiLogger, KodiUI, selected_item_from_context


ACTION_DELETE_EXCLUDE = "delete_exclude"
ACTION_DELETE_REPLACE = "delete_replace"
SELECTED_ACTIONS = (ACTION_DELETE_EXCLUDE, ACTION_DELETE_REPLACE)


def _runtime():
    import xbmcaddon
    addon = xbmcaddon.Addon()
    settings = Settings(addon)
    logger = KodiLogger(settings.debug)
    ui = KodiUI(addon)
    return addon, settings, logger, ui


def _localize(addon, string_id, fallback):
    try:
        value = addon.getLocalizedString(int(string_id))
    except Exception:
        value = ""
    return value or fallback


def _execute_selected_action(action, settings, logger, ui):
    selected = selected_item_from_context()
    logger.info("Action %s requested for %s", action, selected.display_name)
    result = ArrManager(settings, ui, logger).execute(action, selected)
    ui.notification(result)


def _show_error(addon, logger, ui, exc, unexpected_message):
    if isinstance(exc, ArrManagerError):
        logger.warning("%s", exc)
        ui.ok(addon.getAddonInfo("name"), str(exc))
        return
    logger.exception(unexpected_message)
    ui.ok(addon.getAddonInfo("name"), f"Unexpected error: {exc}\n\nCheck kodi.log for details.")


def run_context(action):
    addon, settings, logger, ui = _runtime()
    try:
        _execute_selected_action(action, settings, logger, ui)
    except Exception as exc:
        _show_error(addon, logger, ui, exc, "Unexpected failure")


def run_script(args):
    addon, settings, logger, ui = _runtime()
    params = _parse_args(args)
    mode = params.get("mode")
    try:
        if mode in SELECTED_ACTIONS:
            _execute_selected_action(mode, settings, logger, ui)
            return
        if mode == "test_radarr":
            result = _test_radarr(settings, logger)
            ui.ok("Radarr connection", result)
            return
        if mode == "test_sonarr":
            result = _test_sonarr(settings, logger)
            ui.ok("Sonarr connection", result)
            return
        if mode == "test_backend":
            result = _test_backend(settings, logger)
            ui.ok("File backend", result)
            return
        if mode == "diagnostics":
            result = _write_diagnostics(addon, settings, logger)
            ui.ok("Diagnostics", result)
            return

        options = [
            _localize(addon, 32001, "Delete & Exclude"),
            _localize(addon, 32002, "Delete & Replace"),
            _localize(addon, 32500, "Tools & settings"),
        ]
        choice = ui.select(addon.getAddonInfo("name"), options)
        if choice == 0:
            _execute_selected_action(ACTION_DELETE_EXCLUDE, settings, logger, ui)
        elif choice == 1:
            _execute_selected_action(ACTION_DELETE_REPLACE, settings, logger, ui)
        elif choice == 2:
            _run_tools_menu(addon, settings, logger, ui)
    except Exception as exc:
        _show_error(addon, logger, ui, exc, "Unexpected script failure")


def _run_tools_menu(addon, settings, logger, ui):
    options = [
        _localize(addon, 32501, "Open settings"),
        _localize(addon, 32502, "Test Radarr"),
        _localize(addon, 32503, "Test Sonarr"),
        _localize(addon, 32504, "Test file backend"),
        _localize(addon, 32505, "Write diagnostics"),
    ]
    choice = ui.select(addon.getAddonInfo("name"), options)
    if choice == 0:
        ui.open_settings()
    elif choice == 1:
        ui.ok("Radarr connection", _test_radarr(settings, logger))
    elif choice == 2:
        ui.ok("Sonarr connection", _test_sonarr(settings, logger))
    elif choice == 3:
        ui.ok("File backend", _test_backend(settings, logger))
    elif choice == 4:
        ui.ok("Diagnostics", _write_diagnostics(addon, settings, logger))


def _test_radarr(settings, logger):
    cfg = settings.radarr
    cfg.validate("Radarr")
    status = RadarrClient(cfg.url, cfg.api_key, cfg.api_version, cfg.timeout, cfg.verify_tls, logger).status()
    return f"Connected to Radarr {status.get('version', 'unknown')} as {status.get('instanceName', 'Radarr')}."


def _test_sonarr(settings, logger):
    cfg = settings.sonarr
    cfg.validate("Sonarr")
    status = SonarrClient(cfg.url, cfg.api_key, cfg.api_version, cfg.timeout, cfg.verify_tls, logger).status()
    return f"Connected to Sonarr {status.get('version', 'unknown')} as {status.get('instanceName', 'Sonarr')}."


def _test_backend(settings, logger):
    if settings.backend == "api":
        return "Servarr API deletion is selected. Test Radarr and Sonarr separately."
    backend = make_direct_backend(settings, logger)
    try:
        return f"Connected using {backend.name}. No files were changed."
    finally:
        backend.close()


def _write_diagnostics(addon, settings, logger):
    import xbmcvfs
    profile = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
    os.makedirs(profile, exist_ok=True)
    path = os.path.join(profile, "diagnostics.json")
    payload = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "addonVersion": addon.getAddonInfo("version"),
        "backend": settings.backend,
        "dryRun": settings.dry_run,
        "requireBlocklist": settings.require_blocklist,
        "radarrConfigured": bool(settings.radarr.url and settings.radarr.api_key),
        "sonarrConfigured": bool(settings.sonarr.url and settings.sonarr.api_key),
        "pathMappingCount": len(settings.path_mapper.mappings),
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    return f"Wrote diagnostics to:\n{path}"


def _parse_args(args):
    output = {}
    for arg in args:
        for part in str(arg).split("&"):
            if "=" in part:
                key, value = part.split("=", 1)
                output[key.lstrip("?")] = value
    return output
