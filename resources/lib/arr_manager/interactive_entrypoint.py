# SPDX-License-Identifier: GPL-3.0-or-later
from .clients import BazarrClient, ProwlarrClient
from .config import Settings
from .entrypoints import _bootstrap, _run_action, _show_error
from .interactive_messages import imessage

INTERACTIVE_MODES = {
    "request_search", "interactive_search", "dashboard", "find_subtitles",
    "configure_request_defaults", "configure_subtitle_languages",
    "test_prowlarr", "test_bazarr", "bazarr_languages", "request_defaults",
}


def run_mode(mode):
    addon, logger, ui = _bootstrap()
    try:
        settings = Settings(addon)
        logger.debug_enabled = settings.debug
        if mode == "test_prowlarr":
            cfg = settings.prowlarr
            cfg.validate("Prowlarr")
            status = ProwlarrClient(
                cfg.url, cfg.api_key, cfg.api_version, cfg.timeout, cfg.verify_tls, logger, cfg.user_agent,
            ).status()
            ui.ok("Prowlarr", imessage(addon, "optional_connection", service="Prowlarr", version=status.get("version", "?")))
            return
        if mode == "test_bazarr":
            cfg = settings.bazarr
            cfg.validate("Bazarr")
            status = BazarrClient(
                cfg.url, cfg.api_key, cfg.timeout, cfg.verify_tls, logger, cfg.user_agent,
            ).status()
            data = status.get("data") if isinstance(status.get("data"), dict) else status
            version = data.get("version") or data.get("bazarr_version") or "?"
            ui.ok("Bazarr", imessage(addon, "optional_connection", service="Bazarr", version=version))
            return
        aliases = {"bazarr_languages": "configure_subtitle_languages", "request_defaults": "configure_request_defaults"}
        _run_action(aliases.get(mode, mode), addon, settings, logger, ui)
    except Exception as exc:
        _show_error(addon, logger, ui, exc, "Unexpected interactive action failure")
