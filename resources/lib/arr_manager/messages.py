# SPDX-License-Identifier: GPL-3.0-or-later
"""Central catalogue for runtime text shown by the Kodi adapter."""

MESSAGES = {
    "continue": (32800, "Continue"),
    "cancel": (32801, "Cancel"),
    "cancelled": (32802, "Cancelled"),
    "no_selection": (32803, "No active Kodi library movie, TV show, or episode is selected."),
    "configuration_repair": (32804, "Configuration needs attention: {detail}\n\nSettings will open so it can be repaired."),
    "expected_error": (32805, "{summary}\n\nDetails: {detail}"),
    "unexpected_error": (32806, "Unexpected error: {error_type}\n\nCheck kodi.log for details."),
    "summary_configuration": (32807, "The add-on configuration is invalid. Nothing was changed."),
    "summary_resolution": (32808, "Kodi and Servarr could not identify exactly one matching item. Nothing was changed."),
    "summary_api": (32809, "The Servarr request failed. The operation stopped at the reported stage."),
    "summary_blocklist": (32810, "The release-history requirement was not satisfied. Nothing was deleted."),
    "summary_safety": (32811, "A safety check or post-commit stage failed. Review the details before retrying."),
    "summary_expected": (32812, "The operation could not be completed."),
    "movie_status": (32813, "Radarr {version}\nMovie: {title}\nMonitoring: {monitoring}\nQuality profile: {profile}\nFiles: {files}"),
    "episode_status": (32814, "Sonarr {version}\nEpisode: S{season:02d}E{episode:02d}\nMonitoring: {monitoring}\nFile: {file_state}\nSeries quality profile: {profile}"),
    "series_status": (32815, "Sonarr {version}\nSeries: {title}\nMonitoring: {monitoring}\nQuality profile: {profile}\nEpisode files: {files}"),
    "monitored": (32816, "Monitored"),
    "unmonitored": (32817, "Unmonitored"),
    "available": (32818, "Available"),
    "missing": (32819, "Missing"),
    "search_movie_done": (32820, "Radarr completed a search for {title}."),
    "search_series_done": (32821, "Sonarr completed a full series search for {title}."),
    "search_episode_done": (32822, "Sonarr completed a search for {title} S{season:02d}E{episode:02d}."),
    "monitor_movie_done": (32823, "{title} is now {state} in Radarr."),
    "monitor_episode_done": (32824, "{title} S{season:02d}E{episode:02d} is now {state} in Sonarr."),
    "monitor_series_done": (32825, "{title} and its seasons are now {state} in Sonarr."),
    "no_quality_profiles": (32826, "No usable quality profiles were returned by Servarr."),
    "quality_profile_missing": (32827, "The selected quality profile is no longer available."),
    "quality_movie_done": (32828, "Changed the Radarr quality profile for {title}."),
    "quality_series_done": (32829, "Changed the Sonarr quality profile for {title}."),
    "quality_episode_scope": (32830, "Changed the Sonarr quality profile for {title}. This is a series-wide setting and includes the selected episode."),
    "queue_item_missing": (32831, "The selected queue item is no longer available for this media item."),
    "queue_remove_heading": (32832, "Remove download"),
    "queue_remove_confirm": (32833, "Remove '{title}' from the download queue and download client?\n\nThe release will not be blocklisted."),
    "queue_removed": (32834, "Removed {title} from the {service} queue."),
    "queue_unnamed": (32835, "Unnamed download"),
    "queue_detail": (32836, "{status}{tracked} · {progress}%{remaining}"),
    "queue_remaining": (32837, " · {time_left} remaining"),
    "queue_tracked": (32838, " / {tracked}"),
    "service_line": (32839, "Service: {service}\nStatus: {detail}"),
    "movie_exclude_confirm": (32840, "Delete '{title}' from Radarr, delete its {files} file(s) and movie folder, and add a Radarr import-list exclusion?"),
    "series_exclude_confirm": (32841, "Delete '{title}' from Sonarr, delete its {files} episode file(s) and series folder, and add a Sonarr import-list exclusion?"),
    "episode_exclude_confirm": (32842, "Delete the file for {title} {episodes} and unmonitor the linked episode(s)?\n\nSonarr has no episode-level import-list exclusion."),
    "dry_exclude": (32843, "Dry run: would delete and exclude {title}."),
    "dry_episode_exclude": (32844, "Dry run: would delete and unmonitor {episodes}."),
    "exclude_done": (32845, "Deleted and excluded {title}."),
    "episode_exclude_done": (32846, "Deleted and unmonitored {episodes}."),
    "movie_replace_confirm": (32847, "{blocklist} Delete the current file for '{title}' and search for a replacement?"),
    "episode_replace_confirm": (32848, "{blocklist} Delete {title} {episodes} and search for a replacement?"),
    "series_replace_confirm": (32849, "{blocklist} Delete all {files} episode files for '{title}' and run a full series search?"),
    "dry_movie_replace": (32850, "Dry run: would replace {title}. {blocklist}"),
    "dry_episode_replace": (32851, "Dry run: would replace {title} {episodes}. {blocklist}"),
    "dry_series_replace": (32852, "Dry run: would replace all files for {title}. {blocklist}"),
    "movie_replace_done": (32853, "{blocklist} Deleted the file and completed a replacement search for {title}."),
    "episode_replace_done": (32854, "{blocklist} Deleted the file and completed a replacement search for {title} {episodes}."),
    "series_replace_done": (32855, "{blocklist} Deleted {files} files and completed a series search for {title}."),
    "replace_one_file_required": (32856, "Delete & Replace requires exactly one Radarr movie file; found {files}."),
    "series_no_files": (32857, "This Sonarr series has no episode files to replace."),
    "series_history_missing": (32858, "Could not match imported history for {missing} of {files} episode files. Nothing was deleted."),
    "strict_history_missing": (32859, "Could not prove which imported release created {description}. Nothing was deleted because strict release-history matching is enabled."),
    "blocklist_partial_confirm": (32860, "Blocklist {matched} matched release(s); {missing} file(s) have no history match and may be reacquired."),
    "blocklist_confirm": (32861, "Blocklist matched release(s): {names}."),
    "blocklist_none_confirm": (32862, "No imported-history match will be blocklisted; the same release may be reacquired."),
    "blocklist_partial_done": (32863, "Blocklisted {matched} matched release(s); {missing} file(s) had no history match and may be reacquired."),
    "blocklist_done": (32864, "Blocklisted {matched} matched release(s)."),
    "blocklist_none_done": (32865, "No release was blocklisted; unmatched media may be reacquired."),
    "connection_radarr": (32866, "Connected to Radarr {version} as {name}."),
    "connection_sonarr": (32867, "Connected to Sonarr {version} as {name}."),
    "backend_api": (32868, "Servarr API deletion is selected. Test Radarr and Sonarr separately."),
    "backend_movie": (32869, "Read-only Kodi VFS probe succeeded for the mapped movie folder. Found {dirs} folder(s) and {files} file(s)."),
    "backend_series": (32870, "Read-only Kodi VFS probe succeeded for the mapped series folder. Found {dirs} folder(s) and {files} file(s)."),
    "backend_episode": (32871, "Read-only Kodi VFS probe confirmed the selected episode file is accessible."),
    "diagnostics_written": (32872, "Wrote non-secret diagnostics to:\n{path}"),
    "operation_shutting_down": (32873, "Operation cancelled because Kodi is shutting down."),
    "profile_unknown": (32874, "ID {profile_id}"),
    "delete_exclude_heading": (32875, "Delete & Exclude"),
    "delete_replace_heading": (32876, "Delete & Replace"),
    "progress_preflight": (32877, "Preflighting files: {current}/{total}"),
    "progress_blocklist": (32878, "Blocklisting matched releases"),
    "progress_delete": (32879, "Deleting files: {current}/{total}"),
    "progress_reconcile": (32880, "Reconciling Sonarr"),
    "progress_search": (32881, "Running replacement search"),
    "progress_kodi": (32882, "Updating the Kodi library"),
    "cancelled_precommit": (32883, "Operation cancelled before destructive changes."),
    "backend_movie_unmapped": (32884, "The selected movie folder has no allowlisted Kodi mapping."),
    "backend_series_unmapped": (32885, "The selected series folder has no allowlisted Kodi mapping."),
    "backend_episode_unmapped": (32886, "The selected episode file has no allowlisted Kodi mapping."),
}


def message(source, key, **values):
    string_id, fallback = MESSAGES[key]
    addon = getattr(source, "addon", source)
    getter = getattr(addon, "getLocalizedString", None)
    translated = ""
    if getter:
        try:
            translated = getter(int(string_id)) or ""
        except Exception:
            translated = ""
    template = translated or fallback
    try:
        return template.format(**values)
    except (KeyError, ValueError, IndexError):
        return fallback.format(**values)
