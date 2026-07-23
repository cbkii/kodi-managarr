# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import sys
import time
from urllib.parse import parse_qsl

from .actions import ArrManager
from .bazarr_client import BazarrClient
from .clients import ProwlarrClient, RadarrClient, SonarrClient
from .config import Settings
from .errors import (
    ApiError, ArrManagerError, BlocklistError, ConfigurationError, ResolutionError, SafetyError,
)
from .fileops import make_direct_backend
from .interactive_messages import imessage
from .kodi import KodiLogger, KodiUI, selected_item_from_context
from .kodi_selected import enrich_selected_series_identity
from .messages import message
from .pin import authorize_action, hash_pin, validate_pin, verify_pin
from .registry import ACTION_REGISTRY, get_action_by_id, get_action_by_mode
from .resolver import resolve_episode_context, resolve_movie, resolve_series

SUPPORTED_MEDIA_TYPES = ("movie", "tvshow", "episode")
ACTION_ALIASES = {
    "bazarr_languages": "configure_subtitle_languages",
    "request_defaults": "configure_request_defaults",
}
REGISTERED_ACTION_MODES = {action["mode"] for action in ACTION_REGISTRY}
DIRECT_ACTIONS = REGISTERED_ACTION_MODES | {"menu", "configure_menu", "manage_pin"}


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


def _selected(addon=None, ui=None):
    selected = selected_item_from_context()
    if not selected or selected.media_type not in SUPPORTED_MEDIA_TYPES:
        raise ArrManagerError(_m(addon, "no_selection"))
    if ui is not None and selected.media_type == "episode":
        enrich_selected_series_identity(selected, ui.jsonrpc)
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
    mode = ACTION_ALIASES.get(params.get("mode"), params.get("mode"))
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
            ui.ok(_s(addon, 32712, "File backend"), _test_backend(settings, logger, ui)); return
        if mode == "test_prowlarr":
            ui.ok("Prowlarr", _test_prowlarr(settings, logger)); return
        if mode == "test_bazarr":
            ui.ok("Bazarr", _test_bazarr(settings, logger)); return
        if mode == "diagnostics":
            ui.ok(_s(addon, 32600, "Diagnostics"), _write_diagnostics(addon, settings, logger)); return
        _run_action("menu", addon, settings, logger, ui)
    except Exception as exc:
        _show_error(addon, logger, ui, exc, "Unexpected script failure")


def _get_visible_actions(settings, group):
    actions = [action for action in ACTION_REGISTRY if action["group"] == group]
    mode_key = "simple_mode" if settings.menu_mode == "0" else "advanced_mode"
    actions = [action for action in actions if action.get(mode_key, False)]
    actions = [action for action in actions if action["id"] not in settings.hidden_actions]

    def _sort_key(action):
        try:
            return settings.action_order.index(action["id"])
        except ValueError:
            return action.get("default_order", 999)

    return sorted(actions, key=_sort_key)


def _run_menu_group(group, addon, settings, logger, ui):
    actions = _get_visible_actions(settings, group)
    if not actions:
        return None
    options = [_s(addon, action["label_id"], action["default_label"]) for action in actions]
    heading = addon.getAddonInfo("name")
    if group != "root":
        parent = get_action_by_id(group)
        if parent:
            heading = _s(addon, parent["label_id"], parent["default_label"])
    choice = ui.select(heading, options)
    if choice >= 0:
        return _run_action(actions[choice]["mode"], addon, settings, logger, ui)
    return None


def _run_action(action_mode, addon, settings, logger, ui):
    group_modes = {
        "menu": "root",
        "monitoring_menu": "monitoring",
        "queue_menu": "queue",
    }
    if action_mode in group_modes:
        return _run_menu_group(group_modes[action_mode], addon, settings, logger, ui)
    if action_mode == "tools_menu":
        return _run_tools_menu(addon, settings, logger, ui)
    if action_mode == "configure_menu":
        return _run_configure_menu(addon, settings, logger, ui)
    if action_mode == "manage_pin":
        return _run_manage_pin(addon, settings, logger, ui)

    action = get_action_by_mode(action_mode)
    if action is None:
        raise ResolutionError(f"Unknown action: {action_mode}")
    selected = _selected(addon, ui) if action.get("requires_selection") else None
    if selected and action.get("media_types") and selected.media_type not in action["media_types"]:
        raise ResolutionError(f"Action {action_mode} does not support {selected.media_type}")
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
        _s(addon, 32505, "Write diagnostics"), _s(addon, 32906, "Configure menu"),
        _s(addon, 32910, "Manage PIN"),
    ]
    choice = ui.select(addon.getAddonInfo("name"), options)
    if choice == 0:
        return ui.open_settings()
    if choice == 1:
        return ui.ok(_s(addon, 32710, "Radarr connection"), _test_radarr(settings, logger))
    if choice == 2:
        return ui.ok(_s(addon, 32711, "Sonarr connection"), _test_sonarr(settings, logger))
    if choice == 3:
        return ui.ok(_s(addon, 32712, "File backend"), _test_backend(settings, logger, ui))
    if choice == 4:
        return ui.ok(_s(addon, 32600, "Diagnostics"), _write_diagnostics(addon, settings, logger))
    if choice == 5:
        return _run_configure_menu(addon, settings, logger, ui)
    if choice == 6:
        return _run_manage_pin(addon, settings, logger, ui)
    return None


def _run_configure_menu(addon, settings, logger, ui):
    del logger
    while True:
        order = [action_id for action_id in settings.action_order if get_action_by_id(action_id)]
        for action in ACTION_REGISTRY:
            if action["id"] not in order:
                order.append(action["id"])
        options = []
        visible_ids = []
        for action_id in order:
            action = get_action_by_id(action_id)
            if not action:
                continue
            marker = " " if action_id in settings.hidden_actions else "*"
            options.append(f"[{marker}] {_s(addon, action['label_id'], action['default_label'])}")
            visible_ids.append(action_id)
        options.extend([_m(addon, "menu_save_exit"), _m(addon, "menu_restore_defaults")])
        choice = ui.select(_s(addon, 32906, "Configure menu"), options)
        if choice < 0 or choice == len(options) - 2:
            addon.setSetting("hidden_actions", ",".join(settings.hidden_actions))
            addon.setSetting("action_order", ",".join(settings.action_order))
            return
        if choice == len(options) - 1:
            settings.hidden_actions = []
            settings.action_order = []
            addon.setSetting("hidden_actions", "")
            addon.setSetting("action_order", "")
            ui.notification(_m(addon, "menu_defaults_restored"))
            continue

        action_id = visible_ids[choice]
        item_options = [
            _m(addon, "menu_toggle_visibility"),
            _m(addon, "menu_move_up"),
            _m(addon, "menu_move_down"),
        ]
        action_choice = ui.select(_s(addon, 32906, "Configure menu"), item_options)
        order_index = order.index(action_id)
        if action_choice == 0:
            if action_id in settings.hidden_actions:
                settings.hidden_actions.remove(action_id)
            else:
                settings.hidden_actions.append(action_id)
        elif action_choice == 1 and order_index > 0:
            order[order_index - 1], order[order_index] = order[order_index], order[order_index - 1]
            settings.action_order = order
        elif action_choice == 2 and order_index < len(order) - 1:
            order[order_index + 1], order[order_index] = order[order_index], order[order_index + 1]
            settings.action_order = order
        addon.setSetting("hidden_actions", ",".join(settings.hidden_actions))
        addon.setSetting("action_order", ",".join(settings.action_order))


def _clear_pin(addon, settings):
    addon.setSetting("pin_hash", "")
    addon.setSetting("pin_salt", "")
    settings.pin_hash = b""
    settings.pin_salt = b""
    settings.pin_invalid = False
    settings.pin_enabled = False


def _run_manage_pin(addon, settings, logger, ui):
    del logger
    if settings.pin_invalid:
        ui.notification(_m(addon, "pin_reset_invalid"), error=True)
        _clear_pin(addon, settings)

    if settings.pin_enabled:
        old_pin = ui.numeric_input(_m(addon, "pin_prompt"))
        if not old_pin or not verify_pin(old_pin, settings.pin_hash, settings.pin_salt):
            ui.notification(_m(addon, "pin_incorrect"), error=True)
            return
        choice = ui.select(
            _s(addon, 32910, "Manage PIN"),
            [_m(addon, "pin_change"), _m(addon, "pin_remove")],
        )
        if choice == 1:
            if ui.confirm(_s(addon, 32910, "Manage PIN"), _m(addon, "pin_remove_confirm")):
                _clear_pin(addon, settings)
                ui.notification(_m(addon, "pin_removed"))
            return
        if choice < 0:
            return

    new_pin = ui.numeric_input(_m(addon, "pin_enter_new"))
    if not new_pin:
        return
    try:
        validate_pin(new_pin)
    except ValueError:
        ui.notification(_m(addon, "pin_invalid_format"), error=True)
        return
    confirm_pin = ui.numeric_input(_m(addon, "pin_confirm_new"))
    if new_pin != confirm_pin:
        ui.notification(_m(addon, "pin_mismatch"), error=True)
        return

    pin_hash, pin_salt = hash_pin(new_pin)
    addon.setSetting("pin_hash", pin_hash.hex())
    addon.setSetting("pin_salt", pin_salt.hex())
    settings.pin_hash = pin_hash
    settings.pin_salt = pin_salt
    settings.pin_invalid = False
    settings.pin_enabled = True
    ui.notification(_m(addon, "pin_set"))


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


def _test_prowlarr(settings, logger):
    cfg = settings.prowlarr
    cfg.validate("Prowlarr")
    status = ProwlarrClient(
        cfg.url, cfg.api_key, cfg.api_version, cfg.timeout, cfg.verify_tls, logger, cfg.user_agent,
    ).status()
    return imessage(settings.addon, "optional_connection", service="Prowlarr", version=status.get("version", "?"))


def _test_bazarr(settings, logger):
    cfg = settings.bazarr
    cfg.validate("Bazarr")
    status = BazarrClient(
        cfg.url, cfg.api_key, cfg.timeout, cfg.verify_tls, logger, cfg.user_agent,
    ).status()
    data = status.get("data") if isinstance(status.get("data"), dict) else status
    version = data.get("version") or data.get("bazarr_version") or "?"
    return imessage(settings.addon, "optional_connection", service="Bazarr", version=version)


def _test_backend(settings, logger, ui=None):
    if settings.backend == "api":
        return _m(settings.addon, "backend_api")
    selected = _selected(settings.addon, ui)
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
        logger.warning("Could not read non-secret transaction state: %s", type(exc).__name__)
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
        query = str(arg or "").lstrip("?")
        for key, value in parse_qsl(query, keep_blank_values=True):
            output[key] = value
    return output
