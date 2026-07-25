# SPDX-License-Identifier: GPL-3.0-or-later
"""Kodi entrypoint adapter and TV-remote editor for the menu layout model."""

from .menu_layout import (
    MAX_RANK,
    MENU_ACTIONS,
    attach_menu_layout,
    duplicate_ranks,
    ensure_menu_layout,
    is_flattened,
    normalise_all,
    normalise_group,
    rank_for,
    resolve_actions,
    restore_defaults,
    set_flattened,
    set_rank,
    sorted_group_actions,
)
from .menu_localization import SETTINGS_MESSAGES
from .registry import FLATTENABLE_GROUPS, GROUP_LABELS, MENU_GROUPS, get_action_by_id


def _text(entrypoints, addon, key, **values):
    string_id, fallback = SETTINGS_MESSAGES[key]
    template = entrypoints._s(addon, string_id, fallback)
    try:
        return template.format(**values)
    except (KeyError, ValueError, IndexError):
        return fallback.format(**values)


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
    lines = [_group_label(entrypoints, addon, "root").upper(), ""]
    visible_root = sorted_group_actions(settings, "root")
    visible_root_ids = {action["id"] for action in visible_root}
    for action in resolve_actions(settings, "root"):
        if action.get("flattened_from"):
            rank_text = "%03d/%03d" % (int(action["parent_rank"]), rank_for(settings, action))
        else:
            rank_text = "%03d" % rank_for(settings, action)
        suffix = " ›" if action.get("is_submenu") else ""
        lines.append("%s  %s%s" % (rank_text, _runtime_label(entrypoints, addon, action), suffix))

    for group in FLATTENABLE_GROUPS:
        parent = get_action_by_id(group)
        if (
            not parent
            or parent["id"] not in visible_root_ids
            or is_flattened(settings, group)
        ):
            continue
        lines.extend(["", _group_label(entrypoints, addon, group).upper(), ""])
        for action in sorted_group_actions(settings, group):
            lines.append("%03d  %s" % (rank_for(settings, action), _localised(entrypoints, addon, action)))

    disabled = [action for action in MENU_ACTIONS if rank_for(settings, action) == 0]
    if disabled:
        lines.extend(["", _text(entrypoints, addon, "preview_disabled_heading"), ""])
        for action in sorted(disabled, key=lambda item: (MENU_GROUPS.index(item["group"]), item["default_rank"])):
            lines.append("000  %s › %s" % (
                _group_label(entrypoints, addon, action["group"]),
                _localised(entrypoints, addon, action),
            ))

    warnings = list(getattr(settings, "menu_layout_warnings", []) or [])
    for group, rank, actions in duplicate_ranks(settings):
        warnings.append(_text(
            entrypoints,
            addon,
            "duplicate_rank_warning",
            group=_group_label(entrypoints, addon, group),
            rank=rank,
            actions=", ".join(_localised(entrypoints, addon, action) for action in actions),
        ))
    if warnings:
        lines.extend(["", _text(entrypoints, addon, "preview_warnings_heading"), ""])
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


def _choose_group(entrypoints, addon, ui):
    groups = list(MENU_GROUPS)
    choice = ui.select(
        _text(entrypoints, addon, "choose_group_heading"),
        [_group_label(entrypoints, addon, group) for group in groups],
    )
    return groups[choice] if 0 <= choice < len(groups) else None


def _edit_visibility(entrypoints, addon, settings, ui):
    group = _choose_group(entrypoints, addon, ui)
    if not group:
        return
    actions = sorted_group_actions(settings, group, include_disabled=True, include_mode_hidden=True)
    options = [_localised(entrypoints, addon, action) for action in actions]
    selected = _multiselect(
        ui,
        _text(entrypoints, addon, "visible_items_heading", group=_group_label(entrypoints, addon, group)),
        options,
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
        group = _choose_group(entrypoints, addon, ui)
        if not group:
            return
    actions = sorted_group_actions(settings, group, include_disabled=True, include_mode_hidden=True)
    if action is None:
        choice = ui.select(
            _text(entrypoints, addon, "numeric_position_heading"),
            [
                "%03d  %s" % (rank_for(settings, item), _localised(entrypoints, addon, item))
                for item in actions
            ],
        )
        if choice < 0:
            return
        action = actions[choice]
    value = ui.numeric_input(
        _text(
            entrypoints,
            addon,
            "numeric_input_heading",
            action=_localised(entrypoints, addon, action),
        ),
        str(rank_for(settings, action)),
    )
    if value == "":
        return
    if not set_rank(addon, settings, action["id"], value):
        ui.notification(
            _text(entrypoints, addon, "invalid_position", maximum=MAX_RANK),
            error=True,
        )


def _edit_group_order(entrypoints, addon, settings, ui, group):
    actions = sorted_group_actions(settings, group, include_mode_hidden=True)
    if not actions:
        ui.notification(_text(entrypoints, addon, "no_enabled_items"))
        return
    item_choice = ui.select(
        _text(entrypoints, addon, "reorder_group_heading", group=_group_label(entrypoints, addon, group)),
        [
            "%03d  %s" % (rank_for(settings, action), _localised(entrypoints, addon, action))
            for action in actions
        ],
    )
    if item_choice < 0:
        return
    moving = actions[item_choice]
    others = [action for action in actions if action["id"] != moving["id"]]
    destinations = [
        _text(entrypoints, addon, "move_top"),
        _text(entrypoints, addon, "move_bottom"),
        _text(entrypoints, addon, "enter_numeric_position"),
    ]
    operations = [("top", None), ("bottom", None), ("numeric", None)]
    for action in others:
        label = _localised(entrypoints, addon, action)
        destinations.append(_text(entrypoints, addon, "move_before", action=label))
        operations.append(("before", action["id"]))
        destinations.append(_text(entrypoints, addon, "move_after", action=label))
        operations.append(("after", action["id"]))
    destination = ui.select(
        _text(entrypoints, addon, "move_action_heading", action=_localised(entrypoints, addon, moving)),
        destinations,
    )
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
        ui,
        _text(entrypoints, addon, "flatten_blocks_heading"),
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
        options = [_text(entrypoints, addon, "choose_visible_items")]
        operations = [("visibility", None)]
        for group in reorder_groups:
            options.append(
                _text(entrypoints, addon, "reorder_group_option", group=_group_label(entrypoints, addon, group))
            )
            operations.append(("reorder", group))
        options.extend([
            _text(entrypoints, addon, "numeric_position_heading"),
            _text(entrypoints, addon, "choose_flattened_submenus"),
            _text(entrypoints, addon, "preview_label"),
            _text(entrypoints, addon, "normalise_label"),
            _text(entrypoints, addon, "restore_label"),
            _text(entrypoints, addon, "save_exit"),
        ])
        operations.extend([
            ("numeric", None),
            ("flatten", None),
            ("preview", None),
            ("normalise", None),
            ("restore", None),
            ("exit", None),
        ])
        choice = ui.select(_text(entrypoints, addon, "configure_menu_heading"), options)
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
            ui.text(
                _text(entrypoints, addon, "preview_heading"),
                render_preview(entrypoints, addon, settings),
            )
        elif operation == "normalise":
            normalise_all(addon, settings)
            ui.notification(_text(entrypoints, addon, "positions_normalised"))
        elif operation == "restore" and ui.confirm(
            _text(entrypoints, addon, "restore_label"),
            _text(entrypoints, addon, "restore_confirm"),
        ):
            restore_defaults(addon, settings)
            ui.notification(_text(entrypoints, addon, "defaults_restored"))


def install(entrypoints):
    """Install the Kodi menu adapter over the stable entrypoint dispatcher."""
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
            "menu": "root",
            "monitoring_menu": "monitoring",
            "queue_menu": "queue",
            "retention_menu": "retention",
            "tools_menu": "tools",
        }
        if action_mode in group_modes:
            return run_menu_group(group_modes[action_mode], addon, settings, logger, ui)
        if action_mode == "configure_menu":
            return run_configure_menu(entrypoints, addon, settings, logger, ui)
        if action_mode == "menu_preview":
            return ui.text(
                _text(entrypoints, addon, "preview_heading"),
                render_preview(entrypoints, addon, settings),
            )
        if action_mode == "menu_normalise":
            normalise_all(addon, settings)
            return ui.notification(_text(entrypoints, addon, "positions_normalised"))
        if action_mode == "menu_restore_defaults":
            if ui.confirm(
                _text(entrypoints, addon, "restore_label"),
                _text(entrypoints, addon, "restore_confirm"),
            ):
                restore_defaults(addon, settings)
                return ui.notification(_text(entrypoints, addon, "defaults_restored"))
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
            return ui.ok(
                entrypoints._s(addon, 32600, "Diagnostics"),
                entrypoints._write_diagnostics(addon, settings, logger),
            )
        return original_run_action(action_mode, addon, settings, logger, ui)

    entrypoints.Settings = layout_settings
    entrypoints._get_visible_actions = resolve_actions
    entrypoints._run_menu_group = run_menu_group
    entrypoints._run_configure_menu = lambda addon, settings, logger, ui: run_configure_menu(
        entrypoints,
        addon,
        settings,
        logger,
        ui,
    )
    entrypoints._run_action = run_action
    entrypoints.DIRECT_ACTIONS.update({"menu_preview", "menu_normalise", "menu_restore_defaults"})
    entrypoints._menu_layout_installed = True
