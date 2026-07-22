# SPDX-License-Identifier: GPL-3.0-or-later

ROOT_CONTEXT_LABEL = "Managarr"

EXPECTED_CONTEXT_ACTIONS = frozenset(
    {
        "status",
        "search_now",
        "monitor",
        "unmonitor",
        "change_quality_profile",
        "queue_view",
        "queue_remove",
        "delete_exclude",
        "delete_replace",
    }
)

EXPECTED_DIRECT_CONTEXT_ACTIONS = frozenset(
    {
        "status",
        "search_now",
        "delete_exclude",
        "delete_replace",
    }
)

EXPECTED_CONTEXT_SUBMENUS = {
    "32005": frozenset({"monitor", "unmonitor", "change_quality_profile"}),
    "32009": frozenset({"queue_view", "queue_remove"}),
}
