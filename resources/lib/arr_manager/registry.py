# SPDX-License-Identifier: GPL-3.0-or-later

ALL_MEDIA = ("movie", "tvshow", "episode")


def _action(action_id, label_id, label, group, mode, order, *, simple, mutating=False,
            destructive=False, requires_selection=True, submenu=False, media_types=ALL_MEDIA):
    return {
        "id": action_id,
        "label_id": label_id,
        "default_label": label,
        "group": group,
        "mode": mode,
        "default_mode": "simple" if simple else "advanced",
        "default_order": order,
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
    _action("request_search", 33001, "Request & Search", "root", "request_search", 5, simple=True, mutating=True),
    _action("status", 32003, "Status", "root", "status", 10, simple=True),
    _action("search_now", 32004, "Search & download now", "root", "search_now", 20, simple=True, mutating=True),
    _action("interactive_search", 33002, "Interactive search", "root", "interactive_search", 25, simple=False, mutating=True,
            media_types=("movie", "episode")),
    _action("monitoring", 32005, "Monitoring", "root", "monitoring_menu", 30, simple=False, submenu=True),
    _action("monitor", 32006, "Monitor", "monitoring", "monitor", 31, simple=False, mutating=True),
    _action("unmonitor", 32007, "Unmonitor", "monitoring", "unmonitor", 32, simple=False, mutating=True),
    _action("change_quality_profile", 32008, "Change quality profile", "monitoring", "change_quality_profile", 33,
            simple=False, mutating=True),
    _action("queue", 32009, "Download queue", "root", "queue_menu", 40, simple=False, submenu=True),
    _action("queue_view", 32010, "View status", "queue", "queue_view", 41, simple=False),
    _action("queue_remove", 32011, "Remove from queue", "queue", "queue_remove", 42, simple=False, mutating=True),
    _action("dashboard", 33003, "Dashboard", "root", "dashboard", 45, simple=True, requires_selection=False,
            media_types=()),
    _action("find_subtitles", 33005, "Find subtitles", "root", "find_subtitles", 47, simple=True,
            requires_selection=False, media_types=()),
    _action("retention_preview", 33501, "Preview retention", "root", "retention_preview", 48,
            simple=True, requires_selection=False, media_types=()),
    _action("retention_run", 33502, "Run retention cleanup", "root", "retention_run", 49, simple=True,
            mutating=True, requires_selection=False, media_types=()),
    _action("delete_exclude", 32001, "Delete & Exclude", "root", "delete_exclude", 50, simple=True, mutating=True,
            destructive=True),
    _action("retention_exclude", 33503, "Exclude from automatic retention", "root", "retention_exclude", 51,
            simple=True, mutating=True),
    _action("delete_replace", 32002, "Delete & Replace", "root", "delete_replace", 60, simple=True, mutating=True,
            destructive=True),
    _action("retention_manage_exclusions", 33504, "Manage retention exclusions", "root",
            "retention_manage_exclusions", 61, simple=False, mutating=True, requires_selection=False, media_types=()),
    _action("retention_enable", 33505, "Enable periodic retention", "root", "retention_enable", 62,
            simple=False, mutating=True, requires_selection=False, media_types=()),
    _action("retention_disable", 33506, "Disable periodic retention", "root", "retention_disable", 63,
            simple=False, mutating=True, requires_selection=False, media_types=()),
    _action("retention_report", 33507, "View retention report", "root", "retention_report", 64,
            simple=False, requires_selection=False, media_types=()),
    _action("configure_request_defaults", 33007, "Configure Request & Search defaults", "root",
            "configure_request_defaults", 65, simple=False, requires_selection=False, media_types=()),
    _action("configure_subtitle_languages", 33006, "Configure subtitle languages", "root",
            "configure_subtitle_languages", 66, simple=False, requires_selection=False, media_types=()),
    _action("tools", 32500, "Tools & settings", "root", "tools_menu", 70, simple=True, requires_selection=False,
            submenu=True, media_types=()),
]


def get_action_by_id(action_id):
    return next((action for action in ACTION_REGISTRY if action["id"] == action_id), None)


def get_action_by_mode(mode):
    return next((action for action in ACTION_REGISTRY if action["mode"] == mode), None)
