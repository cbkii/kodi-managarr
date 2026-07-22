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
from .registry import ACTION_REGISTRY, get_action_by_id, get_action_by_mode
from .pin import authorize_action, hash_pin, verify_pin

SUPPORTED_MEDIA_TYPES = ("movie", "tvshow", "episode")
DIRECT_ACTIONS = {
    "menu", "status", "search_now", "monitor", "unmonitor", "change_quality_profile",
    "queue_view", "queue_remove", "delete_exclude", "delete_replace",
    "monitoring_menu", "queue_menu", "tools_menu", "configure_menu", "manage_pin"
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
        _run_action("menu", addon, settings, logger, ui)
    except Exception as exc:
        _show_error(addon, logger, ui, exc, "Unexpected script failure")


def _get_visible_actions(settings, group):
    actions = [a for a in ACTION_REGISTRY if a["group"] == group]
    if str(settings.menu_mode) == "0": # Simple
        actions = [a for a in actions if a.get("simple_mode", False)]
    else: # Advanced
        actions = [a for a in actions if a.get("advanced_mode", False)]

    actions = [a for a in actions if a["id"] not in settings.hidden_actions]

    def _sort_key(action):
        try:
            return settings.action_order.index(action["id"])
        except ValueError:
            return action.get("default_order", 999)

    return sorted(actions, key=_sort_key)


def _run_menu_group(group, addon, settings, logger, ui):
    actions = _get_visible_actions(settings, group)
    if not actions:
        return

    options = [_s(addon, a["label_id"], a["default_label"]) for a in actions]
    heading = addon.getAddonInfo("name")
    if group != "root":
        # Find group label
        for a in ACTION_REGISTRY:
            if a["id"] == group:
                heading = _s(addon, a["label_id"], a["default_label"])
                break

    choice = ui.select(heading, options)
    if choice >= 0:
        _run_action(actions[choice]["mode"], addon, settings, logger, ui)


def _run_action(action_mode, addon, settings, logger, ui):
    if action_mode == "menu":
        return _run_menu_group("root", addon, settings, logger, ui)

    if action_mode == "monitoring_menu":
        return _run_menu_group("monitoring", addon, settings, logger, ui)

    if action_mode == "queue_menu":
        return _run_menu_group("queue", addon, settings, logger, ui)

    if action_mode == "tools_menu":
        return _run_tools_menu(addon, settings, logger, ui)

    if action_mode == "configure_menu":
        return _run_configure_menu(addon, settings, logger, ui)

    if action_mode == "manage_pin":
        return _run_manage_pin(addon, settings, logger, ui)

    action = get_action_by_mode(action_mode)
    if action and action.get("requires_selection"):
        selected = _selected(addon)
    else:
        selected = None

    if action and action.get("destructive"):
        if not authorize_action(action["id"], settings, ui):
            return _m(addon, "cancelled")

    manager = ArrManager(settings, ui, logger)
    if selected:
        logger.info("Action %s requested for %s", action_mode, selected.display_name)
    else:
        logger.info("Action %s requested", action_mode)

    if action_mode == "change_quality_profile":
        return _change_quality_profile(addon, manager, selected, ui)
    if action_mode == "queue_view":
        return _view_queue(addon, manager, selected, ui)
    if action_mode == "queue_remove":
        return _remove_queue(addon, manager, selected, ui)

    result = manager.execute(action_mode, selected)
    if action_mode == "status":
        ui.text(_s(addon, 32003, "Status"), result)
    elif action_mode in {"delete_exclude", "delete_replace", "search_now", "monitor", "unmonitor"}:
        ui.notification(result)
    return result


def _run_tools_menu(addon, settings, logger, ui):
    options = [
        _s(addon, 32501, "Open settings"), _s(addon, 32502, "Test Radarr"),
        _s(addon, 32503, "Test Sonarr"), _s(addon, 32504, "Test file backend"),
        _s(addon, 32505, "Write diagnostics"),
        _s(addon, 32906, "Configure menu"),
        _s(addon, 32910, "Manage PIN"),
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
    elif choice == 5:
        _run_configure_menu(addon, settings, logger, ui)
    elif choice == 6:
        _run_manage_pin(addon, settings, logger, ui)


def _run_configure_menu(addon, settings, logger, ui):
    # Very basic menu configuration loop
    while True:
        # Load order, merge any missing
        order = list(settings.action_order)
        for a in ACTION_REGISTRY:
            if a["id"] not in order:
                order.append(a["id"])

        # Display options
        options = []
        for action_id in order:
            a = get_action_by_id(action_id)
            if not a:
                continue
            visible = " " if action_id in settings.hidden_actions else "*"
            label = _s(addon, a["label_id"], a["default_label"])
            options.append(f"[{visible}] {label}")

        options.append("Save and Exit")
        options.append("Restore Defaults")

        choice = ui.select(_s(addon, 32906, "Configure menu"), options)
        if choice < 0 or choice == len(options) - 2:
            break
        elif choice == len(options) - 1:
            addon.setSetting("hidden_actions", "")
            addon.setSetting("action_order", "")
            settings.hidden_actions = []
            settings.action_order = []
            continue

        # Item selected
        action_id = order[choice]

        # Dialog to toggle visibility, move up, move down
        item_options = ["Toggle Visibility", "Move Up", "Move Down"]
        action_choice = ui.select(_s(addon, 32906, "Configure menu"), item_options)

        if action_choice == 0:
            if action_id in settings.hidden_actions:
                settings.hidden_actions.remove(action_id)
            else:
                settings.hidden_actions.append(action_id)
        elif action_choice == 1 and choice > 0:
            order[choice], order[choice-1] = order[choice-1], order[choice]
            settings.action_order = order
        elif action_choice == 2 and choice < len(order) - 1:
            order[choice], order[choice+1] = order[choice+1], order[choice]
            settings.action_order = order

        addon.setSetting("hidden_actions", ",".join(settings.hidden_actions))
        addon.setSetting("action_order", ",".join(settings.action_order))


def _run_manage_pin(addon, settings, logger, ui):
    if settings.pin_hash:
        # Require old PIN first
        old_pin = ui.keyboard_input(_m(addon, "pin_prompt", fallback="Enter current PIN"), hidden=True)
        if not old_pin or not verify_pin(old_pin, settings.pin_hash, settings.pin_salt):
            ui.notification(_m(addon, "pin_incorrect", fallback="Incorrect PIN"))
            return

        choice = ui.select(_s(addon, 32910, "Manage PIN"), ["Change PIN", "Remove PIN"])
        if choice == 1:
            addon.setSetting("pin_hash", "")
            addon.setSetting("pin_salt", "")
            addon.setSetting("pin_enabled", "false")
            ui.notification("PIN removed")
            return
        elif choice < 0:
            return

    new_pin = ui.keyboard_input("Enter new PIN", hidden=True)
    if not new_pin:
        return
    confirm_pin = ui.keyboard_input("Confirm new PIN", hidden=True)
    if new_pin != confirm_pin:
        ui.notification("PINs do not match")
        return

    pin_hash, pin_salt = hash_pin(new_pin)
    addon.setSetting("pin_hash", pin_hash.hex())
    addon.setSetting("pin_salt", pin_salt.hex())
    addon.setSetting("pin_enabled", "true")
    ui.notification("PIN set successfully")

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
    except (OSError, ValueError):
        pass
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
