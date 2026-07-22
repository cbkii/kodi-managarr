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
    _action("status", 32003, "Status", "root", "status", 10, simple=True),
    _action("search_now", 32004, "Search & download now", "root", "search_now", 20, simple=True, mutating=True),
    _action("monitoring", 32005, "Monitoring", "root", "monitoring_menu", 30, simple=False, submenu=True),
    _action("monitor", 32006, "Monitor", "monitoring", "monitor", 31, simple=False, mutating=True),
    _action("unmonitor", 32007, "Unmonitor", "monitoring", "unmonitor", 32, simple=False, mutating=True),
    _action("change_quality_profile", 32008, "Change quality profile", "monitoring", "change_quality_profile", 33, simple=False, mutating=True),
    _action("queue", 32009, "Download queue", "root", "queue_menu", 40, simple=False, submenu=True),
    _action("queue_view", 32010, "View status", "queue", "queue_view", 41, simple=False),
    # Queue removal is mutating but does not delete imported media; its existing
    # confirmation remains sufficient and the media-deletion PIN is not required.
    _action("queue_remove", 32011, "Remove from queue", "queue", "queue_remove", 42, simple=False, mutating=True),
    _action("delete_exclude", 32001, "Delete & Exclude", "root", "delete_exclude", 50, simple=True, mutating=True, destructive=True),
    _action("delete_replace", 32002, "Delete & Replace", "root", "delete_replace", 60, simple=True, mutating=True, destructive=True),
    _action("retention", 33000, "Retention", "root", "retention_menu", 70, simple=False, requires_selection=False, submenu=True, media_types=()),
    _action("retention_preview", 33037, "Preview eligible media", "retention", "retention_preview", 71, simple=False, requires_selection=False, media_types=()),
    # These actions are conditionally destructive. The entrypoint invokes the
    # central PIN authoriser only when the selected run can perform real deletion.
    _action("retention_run", 33039, "Run cleanup now", "retention", "retention_run", 72, simple=False, mutating=True, requires_selection=False, media_types=()),
    _action("retention_enable", 33041, "Enable periodic cleanup", "retention", "retention_enable", 73, simple=False, mutating=True, requires_selection=False, media_types=()),
    _action("retention_disable", 33043, "Disable periodic cleanup", "retention", "retention_disable", 74, simple=False, mutating=True, requires_selection=False, media_types=()),
    _action("retention_report", 33045, "View last cleanup report", "retention", "retention_report", 75, simple=False, requires_selection=False, media_types=()),
    _action("tools", 32500, "Tools & settings", "root", "tools_menu", 80, simple=True, requires_selection=False, submenu=True, media_types=()),
]


def get_action_by_id(action_id):
    return next((action for action in ACTION_REGISTRY if action["id"] == action_id), None)


def get_action_by_mode(mode):
    return next((action for action in ACTION_REGISTRY if action["mode"] == mode), None)
