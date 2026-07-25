# TV-friendly menu layout

Kodi Managarr uses one canonical numeric rank for every configurable menu action.

## Rank rules

- `0` disables an action.
- Any positive integer enables it.
- Lower values appear first.
- Defaults are spaced by ten (`10`, `20`, `30`, …), but every integer is valid so an item can be inserted between two existing entries.
- Equal ranks are resolved deterministically by the registry default and action ID. The preview reports the tie instead of silently rewriting it.
- **Normalise positions** rewrites enabled items in each group to `10`, `20`, `30`, … while leaving disabled items at `0`.

Numeric ranks are the canonical stored representation. The standard Kodi settings page and the remote-friendly dialog editor both update the same values.

## Three configuration layers

1. **Numbered Kodi settings** — direct integer entry with concise focus help for every action.
2. **Remote-friendly editor** — batch visibility, one-step destination moves, direct numeric entry, preview, normalisation and restore.
3. **Hierarchical layout with optional block flattening** — Monitoring, Download queue, Retention and Tools remain coherent submenus by default, or their children can be inserted as a contiguous labelled block at the parent position.

## Menu hierarchy

### Main menu

| Default | Entry |
| ---: | --- |
| 10 | Request & Search |
| 20 | Status |
| 30 | Search & download now |
| 40 | Interactive search |
| 50 | Monitoring |
| 60 | Download queue |
| 70 | Dashboard |
| 80 | Find subtitles |
| 90 | Retention |
| 100 | Delete & Exclude |
| 110 | Delete & Replace |
| 120 | Tools & settings |

### Monitoring

`Monitor`, `Unmonitor`, `Change quality profile`.

### Download queue

`View status`, `Remove from queue`.

### Retention

`Retention preview`, `Run retention cleanup`, `Last retention report`.

### Tools & settings

`Open settings`, request defaults, subtitle languages, connection tests, diagnostics, menu configuration and PIN management.

## Flattening

Flattening replaces a submenu parent with its enabled children as one contiguous block. Runtime labels are prefixed with their group, for example `Monitoring › Monitor`. Sorting uses `(parent rank, child rank, registry default, action ID)`; child ranks never collide with the next root item.

Setting a parent rank to `0` hides the whole group without erasing its child ranks. Disabling an individual child sets only that child's rank to `0`.

## Migration

On first use of layout version 1:

1. Validate legacy `hidden_actions` and `action_order` IDs against the registry.
2. Resolve the old effective order separately for every group.
3. Assign visible entries `10`, `20`, `30`, … and hidden entries `0`.
4. Persist all canonical rank settings and `menu_layout_version=1`.
5. Retain bounded legacy shadow values for downgrade compatibility; runtime ordering no longer depends on them.

Fresh installations with no legacy state receive the registry defaults.

## Safety and recovery

- Direct/Keymap actions remain callable even when their menu entry is disabled.
- The settings page always retains actions to preview, normalise and restore the layout.
- Invalid rank text or out-of-range values fall back to the registry default and are reported in the preview.
- Restoring defaults resets ranks and flattening only; it does not alter service, deletion, retention or PIN settings.
