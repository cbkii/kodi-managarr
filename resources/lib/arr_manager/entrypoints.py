# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import sys
import time

from .actions import ArrManager
from .clients import RadarrClient, SonarrClient
from .config import Settings
from .errors import (
    ApiError, ArrManagerError, BlocklistError, ConfigurationError, ResolutionError, SafetyError,
)
from .fileops import make_direct_backend
from .kodi import KodiLogger, KodiUI, selected_item_from_context
from .messages import message
from .resolver import resolve_episode_context, resolve_movie, resolve_series

SUPPORTED_MEDIA_TYPES = ("movie", "tvshow", "episode")
DIRECT_ACTIONS = {
    "delete_exclude", "delete_replace", "status", "search_now", "monitor", "unmonitor",
    "change_quality_profile", "queue_view", "queue_remove",
}


def _bootstrap():
    import xbmcaddon
    addon = xbmcaddon.Addon()
    logger = KodiLogger(False)
    ui = KodiUI(addon)
    return addon, logger, ui


def _runtime():
    addon, logger, ui = _bootstrap()
    settings = Settings(addon)
    logger.debug_enabled = settings.debug
    return addon, settings, logger, ui


def _s(addon, string_id, fallback):
    try:
        value = addon.getLocalizedString(int(string_id))
    except Exception:
        value = ""
    return value or fallback


def _m(source, key, **values):
    return message(source, key, **values)


def _selected(addon=None):
    selected = selected_item_from_context()
    if not selected or selected.media_type not in SUPPORTED_MEDIA_TYPES:
        raise ArrManagerError(_m(addon, "no_selection"))
    return selected


def _show_error(addon, logger, ui, exc, unexpected_message):
    if isinstance(exc, ArrManagerError):
        logger.warning("%s", type(exc).__name__)
        if isinstance(exc, ConfigurationError):
            summary = _m(addon, "summary_configuration")
        elif isinstance(exc, ResolutionError):
            summary = _m(addon, "summary_resolution")
        elif isinstance(exc, ApiError):
            summary = _m(addon, "summary_api")
        elif isinstance(exc, BlocklistError):
            summary = _m(addon, "summary_blocklist")
        elif isinstance(exc, SafetyError):
            summary = _m(addon, "summary_safety")
        else:
            summary = _m(addon, "summary_expected")
        ui.ok(addon.getAddonInfo("name"), _m(addon, "expected_error", summary=summary, detail=str(exc)))
        return
    logger.exception(unexpected_message)
    ui.ok(addon.getAddonInfo("name"), _m(addon, "unexpected_error", error_type=type(exc).__name__))


def run_context(action):
    addon, logger, ui = _bootstrap()
    try:
        settings = Settings(addon)
        logger.debug_enabled = settings.debug
        _run_action(action, addon, settings, logger, ui)
    except Exception as exc:
        _show_error(addon, logger, ui, exc, "Unexpected context action failure")


def run_script(args):
    addon, logger, ui = _bootstrap()
    params = _parse_args(args)
    mode = params.get("mode")
    try:
        settings = Settings(addon)
        logger.debug_enabled = settings.debug
    except ConfigurationError as exc:
        if mode in {"settings", ""} or mode is None:
            ui.ok(addon.getAddonInfo("name"), _m(addon, "configuration_repair", detail=str(exc)))
            ui.open_settings()
            return
        _show_error(addon, logger, ui, exc, "Configuration failure")
        return
    try:
        if mode in DIRECT_ACTIONS:
            _run_action(mode, addon, settings, logger, ui)
            return
        if mode == "settings":
            ui.open_settings()
            return
        if mode == "test_radarr":
            ui.ok(_s(addon, 32710, "Radarr connection"), _test_radarr(settings, logger)); return
        if mode == "test_sonarr":
            ui.ok(_s(addon, 32711, "Sonarr connection"), _test_sonarr(settings, logger)); return
        if mode == "test_backend":
            ui.ok(_s(addon, 32712, "File backend"), _test_backend(settings, logger)); return
        if mode == "diagnostics":
            ui.ok(_s(addon, 32600, "Diagnostics"), _write_diagnostics(addon, settings, logger)); return
        _run_main_menu(addon, settings, logger, ui)
    except Exception as exc:
        _show_error(addon, logger, ui, exc, "Unexpected script failure")


def _run_main_menu(addon, settings, logger, ui):
    options = [
        _s(addon, 32003, "Status"),
        _s(addon, 32004, "Search & download now"),
        _s(addon, 32005, "Monitoring"),
        _s(addon, 32009, "Download queue"),
        _s(addon, 32001, "Delete & Exclude"),
        _s(addon, 32002, "Delete & Replace"),
        _s(addon, 32500, "Tools & settings"),
    ]
    choice = ui.select(addon.getAddonInfo("name"), options)
    if choice == 0:
        _run_action("status", addon, settings, logger, ui)
    elif choice == 1:
        _run_action("search_now", addon, settings, logger, ui)
    elif choice == 2:
        _run_monitoring_menu(addon, settings, logger, ui)
    elif choice == 3:
        _run_queue_menu(addon, settings, logger, ui)
    elif choice == 4:
        _run_action("delete_exclude", addon, settings, logger, ui)
    elif choice == 5:
        _run_action("delete_replace", addon, settings, logger, ui)
    elif choice == 6:
        _run_tools_menu(addon, settings, logger, ui)


def _run_action(action, addon, settings, logger, ui):
    selected = _selected(addon)
    manager = ArrManager(settings, ui, logger)
    logger.info("Action %s requested for %s", action, selected.display_name)
    if action == "change_quality_profile":
        return _change_quality_profile(addon, manager, selected, ui)
    if action == "queue_view":
        return _view_queue(addon, manager, selected, ui)
    if action == "queue_remove":
        return _remove_queue(addon, manager, selected, ui)
    result = manager.execute(action, selected)
    if action == "status":
        ui.text(_s(addon, 32003, "Status"), result)
    elif action in {"delete_exclude", "delete_replace", "search_now", "monitor", "unmonitor"}:
        ui.notification(result)
    return result


def _run_monitoring_menu(addon, settings, logger, ui):
    options = [_s(addon, 32006, "Monitor"), _s(addon, 32007, "Unmonitor"), _s(addon, 32008, "Change quality profile")]
    choice = ui.select(_s(addon, 32005, "Monitoring"), options)
    if choice == 0:
        _run_action("monitor", addon, settings, logger, ui)
    elif choice == 1:
        _run_action("unmonitor", addon, settings, logger, ui)
    elif choice == 2:
        _run_action("change_quality_profile", addon, settings, logger, ui)


def _run_queue_menu(addon, settings, logger, ui):
    options = [_s(addon, 32010, "View status"), _s(addon, 32011, "Remove")]
    choice = ui.select(_s(addon, 32009, "Download queue"), options)
    if choice == 0:
        _run_action("queue_view", addon, settings, logger, ui)
    elif choice == 1:
        _run_action("queue_remove", addon, settings, logger, ui)


def _change_quality_profile(addon, manager, selected, ui):
    if selected.media_type == "episode":
        if not ui.confirm(
            _s(addon, 32008, "Change quality profile"),
            _m(addon, "quality_episode_scope_confirm", title=selected.tvshow_title or selected.title),
        ):
            return _m(addon, "cancelled")
    profiles = manager.quality_profiles(selected)
    choice = ui.select(_s(addon, 32008, "Change quality profile"), [profile["name"] for profile in profiles])
    if choice < 0:
        return _m(addon, "cancelled")
    result = manager.change_quality_profile(selected, profiles[choice]["id"])
    ui.notification(result)
    return result


def _view_queue(addon, manager, selected, ui):
    entries = manager.queue_entries(selected)
    if not entries:
        ui.ok(_s(addon, 32009, "Download queue"), _s(addon, 32720, "No matching downloads are in the queue."))
        return []
    choice = ui.select(_s(addon, 32010, "Queue status"), [f"{entry['title']}\n{entry['detail']}" for entry in entries])
    if choice >= 0:
        entry = entries[choice]
        ui.text(entry["title"], _m(addon, "service_line", service=entry["service"], detail=entry["detail"]))
    return entries


def _remove_queue(addon, manager, selected, ui):
    entries = manager.queue_entries(selected)
    if not entries:
        ui.ok(_s(addon, 32009, "Download queue"), _s(addon, 32720, "No matching downloads are in the queue."))
        return _s(addon, 32720, "No matching downloads are in the queue.")
    choice = ui.select(_s(addon, 32011, "Remove from queue"), [f"{entry['title']}\n{entry['detail']}" for entry in entries])
    if choice < 0:
        return _m(addon, "cancelled")
    result = manager.remove_queue_item(selected, entries[choice]["id"])
    if result != _m(addon, "cancelled"):
        ui.notification(result)
    return result


def _run_tools_menu(addon, settings, logger, ui):
    options = [
        _s(addon, 32501, "Open settings"), _s(addon, 32502, "Test Radarr"),
        _s(addon, 32503, "Test Sonarr"), _s(addon, 32504, "Test file backend"),
        _s(addon, 32505, "Write diagnostics"),
    ]
    choice = ui.select(addon.getAddonInfo("name"), options)
    if choice == 0:
        ui.open_settings()
    elif choice == 1:
        ui.ok(_s(addon, 32710, "Radarr connection"), _test_radarr(settings, logger))
    elif choice == 2:
        ui.ok(_s(addon, 32711, "Sonarr connection"), _test_sonarr(settings, logger))
    elif choice == 3:
        ui.ok(_s(addon, 32712, "File backend"), _test_backend(settings, logger))
    elif choice == 4:
        ui.ok(_s(addon, 32600, "Diagnostics"), _write_diagnostics(addon, settings, logger))


def _test_radarr(settings, logger):
    cfg = settings.radarr; cfg.validate("Radarr")
    status = RadarrClient(cfg.url, cfg.api_key, cfg.api_version, cfg.timeout, cfg.verify_tls, logger).status()
    return _m(settings.addon, "connection_radarr", version=status.get("version", "unknown"), name=status.get("instanceName", "Radarr"))


def _test_sonarr(settings, logger):
    cfg = settings.sonarr; cfg.validate("Sonarr")
    status = SonarrClient(cfg.url, cfg.api_key, cfg.api_version, cfg.timeout, cfg.verify_tls, logger).status()
    return _m(settings.addon, "connection_sonarr", version=status.get("version", "unknown"), name=status.get("instanceName", "Sonarr"))


def _test_backend(settings, logger):
    if settings.backend == "api":
        return _m(settings.addon, "backend_api")
    selected = _selected(settings.addon)
    manager = ArrManager(settings, object(), logger)
    backend = make_direct_backend(settings, logger)
    try:
        if selected.media_type == "movie":
            movie = resolve_movie(selected, manager.radarr, settings.path_mapper)
            target = settings.path_mapper.remote_to_kodi(movie.get("path") or "")
            if not target:
                raise ArrManagerError(_m(settings.addon, "backend_movie_unmapped"))
            listing = backend.probe_directory(target)
            return _m(settings.addon, "backend_movie", dirs=len(listing["dirs"]), files=len(listing["files"]))
        series = resolve_series(selected, manager.sonarr, settings.path_mapper)
        if selected.media_type == "tvshow":
            target = settings.path_mapper.remote_to_kodi(series.get("path") or "")
            if not target:
                raise ArrManagerError(_m(settings.addon, "backend_series_unmapped"))
            listing = backend.probe_directory(target)
            return _m(settings.addon, "backend_series", dirs=len(listing["dirs"]), files=len(listing["files"]))
        _, _, file_record = resolve_episode_context(selected, manager.sonarr, series)
        remote = manager._remote_file_path(series.get("path", ""), file_record)
        target = settings.path_mapper.remote_to_kodi(remote)
        if not target:
            raise ArrManagerError(_m(settings.addon, "backend_episode_unmapped"))
        backend.preflight_file(target)
        return _m(settings.addon, "backend_episode")
    finally:
        backend.close()


def _write_diagnostics(addon, settings, logger):
    import platform
    import xbmcvfs
    profile = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
    os.makedirs(profile, exist_ok=True)
    path = os.path.join(profile, "diagnostics.json")
    try:
        import xbmc
        kodi_version = xbmc.getInfoLabel("System.BuildVersion") or "unknown"
        sftp_available = bool(xbmc.getCondVisibility("System.HasAddon(vfs.sftp)"))
    except Exception:
        kodi_version = "unknown"; sftp_available = False
    last_transaction_status = None
    transaction_path = os.path.join(profile, "last-transaction.json")
    try:
        with open(transaction_path, encoding="utf-8") as handle:
            candidate = json.load(handle)
        if isinstance(candidate, dict):
            last_transaction_status = {
                "operation": str(candidate.get("operation", "")),
                "committed": bool(candidate.get("committed")),
                "status": str(candidate.get("status", "")),
                "errorType": str(candidate.get("errorType", "")),
            }
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        if logger:
            logger.warning("Could not read last transaction state: %s", type(exc).__name__)
    payload = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "addonVersion": addon.getAddonInfo("version"),
        "kodiVersion": kodi_version,
        "pythonVersion": platform.python_version(),
        "platform": platform.system(),
        "backend": settings.backend,
        "dryRun": settings.dry_run,
        "requireBlocklist": settings.require_blocklist,
        "radarrConfigured": bool(settings.radarr.url and settings.radarr.api_key),
        "radarrApiVersion": settings.radarr.api_version,
        "radarrVerifyTls": settings.radarr.verify_tls,
        "sonarrConfigured": bool(settings.sonarr.url and settings.sonarr.api_key),
        "sonarrApiVersion": settings.sonarr.api_version,
        "sonarrVerifyTls": settings.sonarr.verify_tls,
        "pathMappingCount": len(settings.path_mapper.mappings),
        "protectedPathCount": len(settings.protected_paths),
        "sftpAddonAvailable": sftp_available,
        "lastTransactionStatus": last_transaction_status,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    logger.debug("Wrote diagnostics file")
    return _m(addon, "diagnostics_written", path=path)


def _parse_args(args):
    output = {}
    for arg in args:
        for part in str(arg).split("&"):
            if "=" in part:
                key, value = part.split("=", 1)
                output[key.lstrip("?")] = value
    return output
