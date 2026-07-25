# SPDX-License-Identifier: GPL-3.0-or-later

ALL_MEDIA = ("movie", "tvshow", "episode")
MENU_GROUPS = ("root", "monitoring", "queue", "retention", "tools")
FLATTENABLE_GROUPS = ("monitoring", "queue", "retention", "tools")
GROUP_LABELS = {
    "root": (32940, "Main menu"),
    "monitoring": (32005, "Monitoring"),
    "queue": (32009, "Download queue"),
    "retention": (33510, "Retention"),
    "tools": (32500, "Tools & settings"),
}


def _action(action_id, label_id, label, help_text, group, mode, rank, *, simple, mutating=False,
            destructive=False, requires_selection=True, submenu=False, media_types=ALL_MEDIA):
    return {
        "id": action_id,
        "label_id": label_id,
        "default_label": label,
        "default_help": help_text,
        "group": group,
        "mode": mode,
        "default_mode": "simple" if simple else "advanced",
        "default_order": rank,
        "default_rank": rank,
        "media_types": tuple(media_types),
        "mutating": bool(mutating),
        "destructive": bool(destructive),
        "requires_selection": bool(requires_selection),
        "simple_mode": bool(simple),
        "advanced_mode": True,
        "is_submenu": bool(submenu),
        "dispatcher_mode": mode,
    }


ACTION_REGISTRY = [
    _action("request_search", 33001, "Request & Search",
            "Add unmanaged media when needed, then ask Radarr or Sonarr to search for the selected item.",
            "root", "request_search", 10, simple=True, mutating=True),
    _action("status", 32003, "Status",
            "Show monitoring, availability, quality-profile and file information for the selected item.",
            "root", "status", 20, simple=True),
    _action("search_now", 32004, "Search & download now",
            "Ask Radarr or Sonarr to search immediately for the selected movie, series or episode.",
            "root", "search_now", 30, simple=True, mutating=True),
    _action("interactive_search", 33002, "Interactive search",
            "Choose a specific release returned by Radarr or Sonarr instead of accepting an automatic match.",
            "root", "interactive_search", 40, simple=False, mutating=True,
            media_types=("movie", "episode")),
    _action("monitoring", 32005, "Monitoring",
            "Open monitoring and quality-profile controls for the selected item.",
            "root", "monitoring_menu", 50, simple=False, submenu=True),
    _action("queue", 32009, "Download queue",
            "View or remove active downloads that match the selected item.",
            "root", "queue_menu", 60, simple=False, submenu=True),
    _action("dashboard", 33003, "Dashboard",
            "Show a bounded overview of configured Arr services and their current state.",
            "root", "dashboard", 70, simple=True, requires_selection=False, media_types=()),
    _action("find_subtitles", 33005, "Find subtitles",
            "Open Kodi-native Bazarr subtitle search for the item that is currently playing.",
            "root", "find_subtitles", 80, simple=True, requires_selection=False, media_types=()),
    _action("retention", 33510, "Retention",
            "Preview, run or review watched-media cleanup using the configured retention policy.",
            "root", "retention_menu", 90, simple=False, requires_selection=False, submenu=True, media_types=()),
    _action("delete_exclude", 32001, "Delete & Exclude",
            "Delete the selected media and prevent its normal import-list readdition where the Arr API supports it.",
            "root", "delete_exclude", 100, simple=True, mutating=True, destructive=True),
    _action("delete_replace", 32002, "Delete & Replace",
            "Delete the current file, blocklist its imported release when proven, and search for a replacement.",
            "root", "delete_replace", 110, simple=True, mutating=True, destructive=True),
    _action("tools", 32500, "Tools & settings",
            "Open setup, connection tests, diagnostics, menu controls and PIN management.",
            "root", "tools_menu", 120, simple=True, requires_selection=False, submenu=True, media_types=()),

    _action("monitor", 32006, "Monitor",
            "Enable Radarr or Sonarr monitoring for the selected movie, series or episode.",
            "monitoring", "monitor", 10, simple=False, mutating=True),
    _action("unmonitor", 32007, "Unmonitor",
            "Disable Radarr or Sonarr monitoring for the selected movie, series or episode.",
            "monitoring", "unmonitor", 20, simple=False, mutating=True),
    _action("change_quality_profile", 32008, "Change quality profile",
            "Choose the Radarr movie or Sonarr series quality profile used for future downloads.",
            "monitoring", "change_quality_profile", 30, simple=False, mutating=True),

    _action("queue_view", 32010, "View status",
            "Show matching active download progress, state and remaining-time information.",
            "queue", "queue_view", 10, simple=False),
    _action("queue_remove", 32011, "Remove from queue",
            "Remove a matching active download from the Arr queue and download client without blocklisting it.",
            "queue", "queue_remove", 20, simple=False, mutating=True),

    _action("retention_preview", 33500, "Retention preview",
            "List media that currently passes the watched, age, rating and exclusion policy without deleting it.",
            "retention", "retention_preview", 10, simple=False, requires_selection=False, media_types=()),
    _action("retention_cleanup", 33501, "Run retention cleanup",
            "Run the bounded manual retention pass using the configured dry-run and deletion limits.",
            "retention", "retention_cleanup", 20, simple=False, mutating=True, destructive=True,
            requires_selection=False, media_types=()),
    _action("retention_report", 33502, "Last retention report",
            "Show the most recent bounded retention result and its deleted, planned, failed and skipped counts.",
            "retention", "retention_report", 30, simple=False, requires_selection=False, media_types=()),

    _action("open_settings", 32501, "Open settings",
            "Open the standard Kodi settings page for all Managarr services and safety options.",
            "tools", "settings", 10, simple=True, requires_selection=False, media_types=()),
    _action("configure_request_defaults", 33007, "Configure Request & Search defaults",
            "Choose the default Arr root folders, quality profiles and Sonarr monitoring behaviour.",
            "tools", "configure_request_defaults", 20, simple=True, requires_selection=False, media_types=()),
    _action("configure_subtitle_languages", 33006, "Configure subtitle languages",
            "Choose up to three ordered Bazarr language variants used by Kodi subtitle search.",
            "tools", "configure_subtitle_languages", 30, simple=True, requires_selection=False, media_types=()),
    _action("test_radarr", 32206, "Test Radarr connection",
            "Perform a read-only Radarr connection and API-version check.",
            "tools", "test_radarr", 40, simple=True, requires_selection=False, media_types=()),
    _action("test_sonarr", 32306, "Test Sonarr connection",
            "Perform a read-only Sonarr connection and API-version check.",
            "tools", "test_sonarr", 50, simple=True, requires_selection=False, media_types=()),
    _action("test_backend", 32404, "Test file backend",
            "Perform a read-only accessibility check using the selected deletion backend and mappings.",
            "tools", "test_backend", 60, simple=True, requires_selection=False, media_types=()),
    _action("test_prowlarr", 33106, "Test Prowlarr connection",
            "Perform a read-only Prowlarr connection and API-version check.",
            "tools", "test_prowlarr", 70, simple=True, requires_selection=False, media_types=()),
    _action("test_bazarr", 33205, "Test Bazarr connection",
            "Perform a read-only Bazarr status and language-capability check.",
            "tools", "test_bazarr", 80, simple=True, requires_selection=False, media_types=()),
    _action("diagnostics", 32505, "Write diagnostics",
            "Write a bounded non-secret support report containing configuration shape and recent operation stages.",
            "tools", "diagnostics", 90, simple=True, requires_selection=False, media_types=()),
    _action("configure_menu", 32906, "Configure menu",
            "Open the TV-remote-friendly batch visibility, destination move and numeric-rank editor.",
            "tools", "configure_menu", 100, simple=True, requires_selection=False, media_types=()),
    _action("manage_pin", 32910, "Manage PIN",
            "Set, change, remove or repair the local numeric PIN used for protected actions.",
            "tools", "manage_pin", 110, simple=True, requires_selection=False, media_types=()),

    _action("retention_enable_periodic", 33503, "Enable periodic retention",
            "Authorise and enable periodic retention using the current policy and PIN state.",
            "retention_settings", "retention_enable_periodic", 10, simple=False, mutating=True,
            destructive=True, requires_selection=False, media_types=()),
    _action("retention_disable_periodic", 33504, "Disable periodic retention",
            "Disable future periodic retention passes immediately.",
            "retention_settings", "retention_disable_periodic", 20, simple=False, mutating=True,
            requires_selection=False, media_types=()),
]


def get_action_by_id(action_id):
    return next((action for action in ACTION_REGISTRY if action["id"] == action_id), None)


def get_action_by_mode(mode):
    return next((action for action in ACTION_REGISTRY if action["mode"] == mode), None)


def get_group_actions(group):
    return [action for action in ACTION_REGISTRY if action["group"] == group]
