# SPDX-License-Identifier: GPL-3.0-or-later
"""Canonical numeric menu ranks and TV-remote-friendly layout editing."""

from collections import defaultdict

from .registry import (
    ACTION_REGISTRY, FLATTENABLE_GROUPS, GROUP_LABELS, MENU_GROUPS,
    get_action_by_id, get_group_actions,
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
            warnings.append("Invalid position for %s; using %d." % (action["default_label"], default))
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
    ensure_menu_layout(settings, addon)
    actions = sorted_group_actions(settings, group)
    if ordered_ids is not None:
        known = {action["id"]: action for action in actions}
        actions = [known[action_id] for action_id in ordered_ids if action_id in known]
        actions.extend(action for action in sorted_group_actions(settings, group) if action["id"] not in ordered_ids)
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


def _localised(entrypoints, addon, action):
    return entrypoints._s(addon, action["label_id"], action["default_label"])


def _group_label(entrypoints, addon, group):
    string_id, fallback = GROUP_LABELS[group]
    return entrypoints._s(addon, string_id, fallback)


def _runtime_label(entrypoints, addon, action):
    label = _localised(entrypoints, addon, action)
    parent_id = action.get("flattened_from")
    if parent_id:
        parent = get_action_by_id(parent_id)
        if parent:
            return "%s › %s" % (_localised(entrypoints, addon, parent), label)
    return label


def render_preview(entrypoints, addon, settings):
    ensure_menu_layout(settings, addon)
    lines = ["MAIN MENU", ""]
    for action in resolve_actions(settings, "root"):
        if action.get("flattened_from"):
            rank_text = "%03d/%03d" % (int(action["parent_rank"]), rank_for(settings, action))
        else:
            rank_text = "%03d" % rank_for(settings, action)
        suffix = " ›" if action.get("is_submenu") else ""
        lines.append("%s  %s%s" % (rank_text, _runtime_label(entrypoints, addon, action), suffix))

    for group in FLATTENABLE_GROUPS:
        parent = get_action_by_id(group)
        if not parent or rank_for(settings, parent) == 0 or is_flattened(settings, group):
            continue
        lines.extend(["", _group_label(entrypoints, addon, group).upper(), ""])
        for action in sorted_group_actions(settings, group):
            lines.append("%03d  %s" % (rank_for(settings, action), _localised(entrypoints, addon, action)))

    disabled = [action for action in MENU_ACTIONS if rank_for(settings, action) == 0]
    if disabled:
        lines.extend(["", "DISABLED", ""])
        for action in sorted(disabled, key=lambda item: (MENU_GROUPS.index(item["group"]), item["default_rank"])):
            lines.append("000  %s › %s" % (
                _group_label(entrypoints, addon, action["group"]),
                _localised(entrypoints, addon, action),
            ))

    warnings = list(getattr(settings, "menu_layout_warnings", []) or [])
    for group, rank, actions in duplicate_ranks(settings):
        warnings.append("Duplicate %s position %d: %s. Registry default and action ID break the tie." % (
            _group_label(entrypoints, addon, group), rank,
            ", ".join(_localised(entrypoints, addon, action) for action in actions),
        ))
    if warnings:
        lines.extend(["", "WARNINGS", ""])
        lines.extend("- " + warning for warning in warnings)
    return "\n".join(lines)


def _multiselect(ui, heading, options, preselect):
    method = getattr(ui, "multiselect", None)
    if callable(method):
        return method(heading, options, preselect)
    xbmcgui = getattr(ui, "xbmcgui", None)
    if xbmcgui is None:
        return None
    return xbmcgui.Dialog().multiselect(heading, options, preselect=preselect)


def _choose_group(entrypoints, addon, ui, heading):
    groups = list(MENU_GROUPS)
    choice = ui.select(heading, [_group_label(entrypoints, addon, group) for group in groups])
    return groups[choice] if 0 <= choice < len(groups) else None


def _edit_visibility(entrypoints, addon, settings, ui):
    group = _choose_group(entrypoints, addon, ui, "Choose a menu group")
    if not group:
        return
    actions = sorted_group_actions(settings, group, include_disabled=True, include_mode_hidden=True)
    options = [_localised(entrypoints, addon, action) for action in actions]
    selected = _multiselect(
        ui, "Visible %s items" % _group_label(entrypoints, addon, group), options,
        [index for index, action in enumerate(actions) if rank_for(settings, action) > 0],
    )
    if selected is None:
        return
    selected_indexes = set(selected)
    enabled = []
    for index, action in enumerate(actions):
        if index in selected_indexes:
            enabled.append(action["id"])
            if rank_for(settings, action) == 0:
                set_rank(addon, settings, action["id"], int(action["default_rank"]))
        else:
            set_rank(addon, settings, action["id"], 0)
    normalise_group(addon, settings, group, enabled)


def _edit_numeric(entrypoints, addon, settings, ui, group=None, action=None):
    if group is None:
        group = _choose_group(entrypoints, addon, ui, "Choose a menu group")
        if not group:
            return
    actions = sorted_group_actions(settings, group, include_disabled=True, include_mode_hidden=True)
    if action is None:
        choice = ui.select("Set numeric position", [
            "%03d  %s" % (rank_for(settings, item), _localised(entrypoints, addon, item)) for item in actions
        ])
        if choice < 0:
            return
        action = actions[choice]
    value = ui.numeric_input(
        "%s — enter 0 to hide" % _localised(entrypoints, addon, action),
        str(rank_for(settings, action)),
    )
    if value == "":
        return
    if not set_rank(addon, settings, action["id"], value):
        ui.notification("Position must be a whole number from 0 to %d." % MAX_RANK, error=True)


def _edit_group_order(entrypoints, addon, settings, ui, group):
    actions = sorted_group_actions(settings, group)
    if not actions:
        ui.notification("This menu group has no enabled items.")
        return
    item_choice = ui.select("Reorder %s" % _group_label(entrypoints, addon, group), [
        "%03d  %s" % (rank_for(settings, action), _localised(entrypoints, addon, action)) for action in actions
    ])
    if item_choice < 0:
        return
    moving = actions[item_choice]
    others = [action for action in actions if action["id"] != moving["id"]]
    destinations = ["Move to top", "Move to bottom", "Enter numeric position"]
    operations = [("top", None), ("bottom", None), ("numeric", None)]
    for action in others:
        label = _localised(entrypoints, addon, action)
        destinations.append("Move before: " + label)
        operations.append(("before", action["id"]))
        destinations.append("Move after: " + label)
        operations.append(("after", action["id"]))
    destination = ui.select("Move %s" % _localised(entrypoints, addon, moving), destinations)
    if destination < 0:
        return
    operation, target = operations[destination]
    if operation == "numeric":
        _edit_numeric(entrypoints, addon, settings, ui, group=group, action=moving)
        return
    order = [action["id"] for action in actions if action["id"] != moving["id"]]
    if operation == "top":
        order.insert(0, moving["id"])
    elif operation == "bottom":
        order.append(moving["id"])
    else:
        index = order.index(target)
        if operation == "after":
            index += 1
        order.insert(index, moving["id"])
    normalise_group(addon, settings, group, order)


def _edit_flattening(entrypoints, addon, settings, ui):
    groups = list(FLATTENABLE_GROUPS)
    selected = _multiselect(
        ui, "Flatten submenu blocks into the main menu",
        [_group_label(entrypoints, addon, group) for group in groups],
        [index for index, group in enumerate(groups) if is_flattened(settings, group)],
    )
    if selected is None:
        return
    selected_indexes = set(selected)
    for index, group in enumerate(groups):
        set_flattened(addon, settings, group, index in selected_indexes)


def run_configure_menu(entrypoints, addon, settings, logger, ui):
    del logger
    ensure_menu_layout(settings, addon)
    reorder_groups = list(MENU_GROUPS)
    while True:
        options = ["Choose visible items"]
        operations = [("visibility", None)]
        for group in reorder_groups:
            options.append("Reorder %s" % _group_label(entrypoints, addon, group))
            operations.append(("reorder", group))
        options.extend([
            "Set numeric position", "Choose flattened submenus", "Preview resolved menu",
            "Normalise positions", "Restore menu defaults", "Save and exit",
        ])
        operations.extend([
            ("numeric", None), ("flatten", None), ("preview", None),
            ("normalise", None), ("restore", None), ("exit", None),
        ])
        choice = ui.select("Configure menu", options)
        if choice < 0:
            return
        operation, group = operations[choice]
        if operation == "exit":
            return
        if operation == "visibility":
            _edit_visibility(entrypoints, addon, settings, ui)
        elif operation == "reorder":
            _edit_group_order(entrypoints, addon, settings, ui, group)
        elif operation == "numeric":
            _edit_numeric(entrypoints, addon, settings, ui)
        elif operation == "flatten":
            _edit_flattening(entrypoints, addon, settings, ui)
        elif operation == "preview":
            ui.text("Menu layout preview", render_preview(entrypoints, addon, settings))
        elif operation == "normalise":
            normalise_all(addon, settings)
            ui.notification("Menu positions normalised to 10, 20, 30, …")
        elif operation == "restore" and ui.confirm("Restore menu defaults", "Restore default positions, visibility and submenu layout?"):
            restore_defaults(addon, settings)
            ui.notification("Default menu visibility and ordering restored.")


def install(entrypoints):
    """Install the layout layer over the stable entrypoint dispatcher."""
    if getattr(entrypoints, "_menu_layout_installed", False):
        return

    original_settings = entrypoints.Settings
    original_run_action = entrypoints._run_action

    def layout_settings(addon):
        return attach_menu_layout(original_settings(addon), addon)

    def run_menu_group(group, addon, settings, logger, ui):
        ensure_menu_layout(settings, addon)
        actions = resolve_actions(settings, group)
        if not actions:
            return None
        options = [_runtime_label(entrypoints, addon, action) for action in actions]
        heading = addon.getAddonInfo("name")
        if group != "root":
            heading = _group_label(entrypoints, addon, group)
        choice = ui.select(heading, options)
        if choice >= 0:
            return entrypoints._run_action(actions[choice]["mode"], addon, settings, logger, ui)
        return None

    def run_action(action_mode, addon, settings, logger, ui):
        ensure_menu_layout(settings, addon)
        group_modes = {
            "menu": "root", "monitoring_menu": "monitoring", "queue_menu": "queue",
            "retention_menu": "retention", "tools_menu": "tools",
        }
        if action_mode in group_modes:
            return run_menu_group(group_modes[action_mode], addon, settings, logger, ui)
        if action_mode == "configure_menu":
            return run_configure_menu(entrypoints, addon, settings, logger, ui)
        if action_mode == "menu_preview":
            return ui.text("Menu layout preview", render_preview(entrypoints, addon, settings))
        if action_mode == "menu_normalise":
            normalise_all(addon, settings)
            return ui.notification("Menu positions normalised to 10, 20, 30, …")
        if action_mode == "menu_restore_defaults":
            if ui.confirm("Restore menu defaults", "Restore default positions, visibility and submenu layout?"):
                restore_defaults(addon, settings)
                return ui.notification("Default menu visibility and ordering restored.")
            return None
        if action_mode == "settings":
            return ui.open_settings()
        if action_mode == "test_radarr":
            return ui.ok(entrypoints._s(addon, 32710, "Radarr connection"), entrypoints._test_radarr(settings, logger))
        if action_mode == "test_sonarr":
            return ui.ok(entrypoints._s(addon, 32711, "Sonarr connection"), entrypoints._test_sonarr(settings, logger))
        if action_mode == "test_backend":
            return ui.ok(entrypoints._s(addon, 32712, "File backend"), entrypoints._test_backend(settings, logger, ui))
        if action_mode == "test_prowlarr":
            return ui.ok(
                entrypoints._s(addon, *entrypoints.INTERACTIVE_MESSAGES["prowlarr_connection"]),
                entrypoints._test_prowlarr(settings, logger),
            )
        if action_mode == "test_bazarr":
            return ui.ok(
                entrypoints._s(addon, *entrypoints.INTERACTIVE_MESSAGES["bazarr_connection"]),
                entrypoints._test_bazarr(settings, logger),
            )
        if action_mode == "diagnostics":
            return ui.ok(entrypoints._s(addon, 32600, "Diagnostics"), entrypoints._write_diagnostics(addon, settings, logger))
        return original_run_action(action_mode, addon, settings, logger, ui)

    entrypoints.Settings = layout_settings
    entrypoints._get_visible_actions = resolve_actions
    entrypoints._run_menu_group = run_menu_group
    entrypoints._run_configure_menu = lambda addon, settings, logger, ui: run_configure_menu(
        entrypoints, addon, settings, logger, ui,
    )
    entrypoints._run_action = run_action
    entrypoints.DIRECT_ACTIONS.update({"menu_preview", "menu_normalise", "menu_restore_defaults"})
    entrypoints._menu_layout_installed = True
