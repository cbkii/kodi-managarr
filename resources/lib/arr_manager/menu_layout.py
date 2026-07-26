# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure menu-rank, migration, ordering and flattening model."""

from collections import defaultdict

from .registry import (
    ACTION_REGISTRY,
    FLATTENABLE_GROUPS,
    MENU_GROUPS,
    get_action_by_id,
    get_group_actions,
)
from .util import as_bool

LAYOUT_VERSION = 1
MAX_RANK = 999
RANK_PREFIX = "menu_rank_"
FLATTEN_PREFIX = "menu_flatten_"
LAYOUT_VERSION_SETTING = "menu_layout_version"
MENU_ACTIONS = tuple(action for action in ACTION_REGISTRY if action["group"] in MENU_GROUPS)


def rank_setting_id(action_id):
    return RANK_PREFIX + action_id


def flatten_setting_id(group):
    return FLATTEN_PREFIX + group


def _safe_int(value, default):
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default, False
    if parsed < 0 or parsed > MAX_RANK:
        return default, False
    return parsed, True


def _legacy_state(settings):
    hidden = getattr(settings, "hidden_actions", [])
    order = getattr(settings, "action_order", [])
    return (
        list(hidden) if isinstance(hidden, (list, tuple)) else [],
        list(order) if isinstance(order, (list, tuple)) else [],
    )


def derive_legacy_ranks(hidden_actions, action_order):
    """Translate the old global list into the effective order of each menu group."""
    hidden = set(hidden_actions or [])
    order = list(action_order or [])
    positions = {action_id: index for index, action_id in enumerate(order)}
    ranks = {}
    for group in MENU_GROUPS:
        actions = sorted(
            get_group_actions(group),
            key=lambda action: (
                positions.get(action["id"], 100000 + int(action["default_rank"])),
                int(action["default_rank"]),
                action["id"],
            ),
        )
        next_rank = 10
        for action in actions:
            if action["id"] in hidden:
                ranks[action["id"]] = 0
            else:
                ranks[action["id"]] = next_rank
                next_rank += 10
    return ranks


def _read_canonical_ranks(get):
    ranks = {}
    warnings = []
    changed_from_defaults = False
    for action in MENU_ACTIONS:
        default = int(action["default_rank"])
        raw = get(rank_setting_id(action["id"]))
        rank, valid = _safe_int(raw, default)
        if not valid and str(raw or "").strip():
            warnings.append(("invalid_position", action["id"], default))
        ranks[action["id"]] = rank
        if rank != default:
            changed_from_defaults = True
    return ranks, warnings, changed_from_defaults


def _shadow_order(ranks):
    result = []
    for group in MENU_GROUPS:
        actions = sorted(
            get_group_actions(group),
            key=lambda action: (
                1 if int(ranks.get(action["id"], action["default_rank"])) == 0 else 0,
                int(ranks.get(action["id"], action["default_rank"])) or MAX_RANK + 1,
                int(action["default_rank"]),
                action["id"],
            ),
        )
        result.extend(action["id"] for action in actions)
    return result


def _persist_shadow(addon, settings):
    setter = getattr(addon, "setSetting", None)
    if not callable(setter):
        return
    ranks = getattr(settings, "menu_ranks", {})
    hidden = [action["id"] for action in MENU_ACTIONS if int(ranks.get(action["id"], 0)) == 0]
    order = _shadow_order(ranks)
    setter("hidden_actions", ",".join(hidden))
    setter("action_order", ",".join(order))
    settings.hidden_actions = hidden
    settings.action_order = order


def attach_menu_layout(settings, addon):
    """Load canonical ranks or migrate a customised legacy layout exactly once."""
    get = addon.getSetting
    version, valid_version = _safe_int(get(LAYOUT_VERSION_SETTING), 0)
    if not valid_version:
        version = 0

    canonical_ranks, warnings, canonical_changed = _read_canonical_ranks(get)
    flatten_groups = {
        group for group in FLATTENABLE_GROUPS
        if as_bool(get(flatten_setting_id(group)), False)
    }
    hidden, order = _legacy_state(settings)
    legacy_customised = bool(hidden or order)

    # A direct edit in Kodi's numbered settings must win even before the first
    # post-upgrade script launch. Otherwise migrate a real legacy customisation;
    # fresh/default installs simply adopt the canonical settings defaults.
    if version < LAYOUT_VERSION and legacy_customised and not canonical_changed and not flatten_groups:
        ranks = derive_legacy_ranks(hidden, order)
        warnings = []
    else:
        ranks = canonical_ranks

    settings.menu_ranks = ranks
    settings.flatten_groups = flatten_groups
    settings.menu_layout_version = LAYOUT_VERSION
    settings.menu_layout_warnings = warnings

    setter = getattr(addon, "setSetting", None)
    if version < LAYOUT_VERSION and callable(setter):
        for action in MENU_ACTIONS:
            setter(rank_setting_id(action["id"]), str(ranks[action["id"]]))
        for group in FLATTENABLE_GROUPS:
            setter(flatten_setting_id(group), "true" if group in settings.flatten_groups else "false")
        setter(LAYOUT_VERSION_SETTING, str(LAYOUT_VERSION))
        _persist_shadow(addon, settings)
    return settings


def ensure_menu_layout(settings, addon):
    if not isinstance(getattr(settings, "menu_ranks", None), dict):
        return attach_menu_layout(settings, addon)
    if not isinstance(getattr(settings, "flatten_groups", None), set):
        settings.flatten_groups = set()
    return settings


def rank_for(settings, action):
    ranks = getattr(settings, "menu_ranks", None)
    if isinstance(ranks, dict):
        rank = ranks.get(action["id"], action["default_rank"])
        parsed, _ = _safe_int(rank, int(action["default_rank"]))
        return parsed

    hidden, order = _legacy_state(settings)
    if action["id"] in hidden:
        return 0
    try:
        return (order.index(action["id"]) + 1) * 10
    except ValueError:
        return int(action["default_rank"])


def is_flattened(settings, group):
    flattened = getattr(settings, "flatten_groups", None)
    return isinstance(flattened, set) and group in flattened


def _mode_visible(settings, action):
    mode_key = "simple_mode" if getattr(settings, "menu_mode", "1") == "0" else "advanced_mode"
    return bool(action.get(mode_key, False))


def sorted_group_actions(settings, group, include_disabled=False, include_mode_hidden=False):
    actions = get_group_actions(group)
    if not include_mode_hidden:
        actions = [action for action in actions if _mode_visible(settings, action)]
    if not include_disabled:
        actions = [action for action in actions if rank_for(settings, action) > 0]
    return sorted(
        actions,
        key=lambda action: (
            1 if rank_for(settings, action) == 0 else 0,
            rank_for(settings, action) or MAX_RANK + 1,
            int(action["default_rank"]),
            action["id"],
        ),
    )


def resolve_actions(settings, group):
    actions = sorted_group_actions(settings, group)
    if group != "root":
        return actions

    resolved = []
    for action in actions:
        if action.get("is_submenu") and action["id"] in FLATTENABLE_GROUPS and is_flattened(settings, action["id"]):
            for child in sorted_group_actions(settings, action["id"]):
                flattened = dict(child)
                flattened["flattened_from"] = action["id"]
                flattened["parent_rank"] = rank_for(settings, action)
                resolved.append(flattened)
        else:
            resolved.append(action)
    return resolved


def set_rank(addon, settings, action_id, rank):
    action = get_action_by_id(action_id)
    if not action or action["group"] not in MENU_GROUPS:
        return False
    parsed, valid = _safe_int(rank, int(action["default_rank"]))
    if not valid:
        return False
    ensure_menu_layout(settings, addon)
    settings.menu_ranks[action_id] = parsed
    setter = getattr(addon, "setSetting", None)
    if callable(setter):
        setter(rank_setting_id(action_id), str(parsed))
        setter(LAYOUT_VERSION_SETTING, str(LAYOUT_VERSION))
    _persist_shadow(addon, settings)
    return True


def set_flattened(addon, settings, group, enabled):
    if group not in FLATTENABLE_GROUPS:
        return False
    ensure_menu_layout(settings, addon)
    if enabled:
        settings.flatten_groups.add(group)
    else:
        settings.flatten_groups.discard(group)
    setter = getattr(addon, "setSetting", None)
    if callable(setter):
        setter(flatten_setting_id(group), "true" if enabled else "false")
        setter(LAYOUT_VERSION_SETTING, str(LAYOUT_VERSION))
    return True


def normalise_group(addon, settings, group, ordered_ids=None):
    """Normalise every enabled action in a group, independent of simple/advanced mode."""
    ensure_menu_layout(settings, addon)
    actions = sorted_group_actions(settings, group, include_mode_hidden=True)
    if ordered_ids is not None:
        known = {action["id"]: action for action in actions}
        actions = [known[action_id] for action_id in ordered_ids if action_id in known]
        actions.extend(action for action in actions if action["id"] not in ordered_ids)
    for index, action in enumerate(actions, 1):
        set_rank(addon, settings, action["id"], index * 10)
    return [action["id"] for action in actions]


def normalise_all(addon, settings):
    for group in MENU_GROUPS:
        normalise_group(addon, settings, group)


def restore_defaults(addon, settings):
    ensure_menu_layout(settings, addon)
    for action in MENU_ACTIONS:
        set_rank(addon, settings, action["id"], int(action["default_rank"]))
    for group in FLATTENABLE_GROUPS:
        set_flattened(addon, settings, group, False)
    settings.menu_layout_warnings = []


def duplicate_ranks(settings):
    duplicates = []
    for group in MENU_GROUPS:
        by_rank = defaultdict(list)
        for action in get_group_actions(group):
            rank = rank_for(settings, action)
            if rank > 0:
                by_rank[rank].append(action)
        for rank, actions in sorted(by_rank.items()):
            if len(actions) > 1:
                duplicates.append((group, rank, actions))
    return duplicates
