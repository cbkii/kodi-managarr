# SPDX-License-Identifier: GPL-3.0-or-later

INTERACTIVE_MESSAGES = {
    "search_group": (33000, "Search"),
    "request_search": (32986, "Request & Search"),
    "interactive_search": (32987, "Interactive search"),
    "dashboard": (32983, "Dashboard"),
    "subtitles_group": (33004, "Subtitles"),
    "find_subtitles": (32984, "Find subtitles"),
    "configure_subtitle_languages": (32985, "Configure subtitle languages"),
    "configure_request_defaults": (32990, "Configure Request & Search defaults"),
    "request_defaults_missing": (33400, "Configure Request & Search defaults before adding new media."),
    "request_movie_done": (33401, "Radarr added and searched for {title}."),
    "request_series_done": (33402, "Sonarr added and searched for {title}."),
    "request_episode_done": (33403, "Sonarr is monitoring and searching for {title} S{season:02d}E{episode:02d}."),
    "request_existing_done": (33404, "The existing Arr item was monitored and searched."),
    "request_partial": (33405, "{title} was added successfully, but its search failed. Review the Arr command history before retrying."),
    "lookup_no_results": (33406, "No exact Arr lookup result was found for {title}."),
    "lookup_choose": (33407, "Choose the exact result"),
    "release_none": (32991, "No releases were returned by the selected Arr service."),
    "release_choose": (33409, "Choose a release"),
    "release_details": (33410, "Release details"),
    "release_confirm": (33411, "Grab this release through {service}?\n\n{details}"),
    "release_grabbed": (32992, "The selected release was sent to {service}."),
    "release_stale": (33413, "The selected release is no longer available. Search again."),
    "series_interactive_unsupported": (32993, "Interactive release selection supports movies and individual episodes."),
    "prowlarr_info": (33415, "Arr returned no releases. Prowlarr found {count} informational result(s); no download was bypassed around Arr."),
    "dashboard_title": (32983, "Dashboard"),
    "dashboard_line": (33417, "{service}: {detail}"),
    "service_unavailable": (33418, "Unavailable ({error_type})"),
    "configure_service": (33419, "Configure {service}"),
    "choose_root": (33420, "Choose the default {service} root folder"),
    "choose_profile": (33421, "Choose the default {service} quality profile"),
    "defaults_saved": (33422, "Saved Request & Search defaults."),
    "bazarr_disabled": (33423, "Enable and configure Bazarr first."),
    "languages_choose_slot": (33424, "Choose subtitle language {slot}"),
    "languages_none": (33425, "None"),
    "languages_saved": (33426, "Saved {count} subtitle language(s)."),
    "languages_required": (33427, "Configure at least one Bazarr subtitle language."),
    "subtitle_unknown": (33428, "Unknown"),
    "subtitle_downloaded": (33429, "Subtitle downloaded."),
    "subtitle_not_found": (33430, "Bazarr completed the request, but Kodi could not access the downloaded subtitle file."),
    "subtitle_invalid_request": (33431, "The subtitle request is incomplete or expired."),
    "subtitle_no_results": (33432, "No matching Bazarr subtitles were found for the configured languages."),
    "subtitle_search_failed": (33433, "Subtitle search failed: {error_type}"),
    "optional_connection": (33434, "Connected to {service} {version}."),
    "find_subtitles_playback": (33435, "Start playback before opening subtitle search."),
    "request_unsupported": (33436, "Request & Search does not support this Kodi item type."),
    "multiple_exact_movies": (33437, "Multiple Radarr movies exactly match {title}."),
    "multiple_exact_series": (33438, "Multiple Sonarr series exactly match {title}."),
    "movie_reresolve_failed": (33439, "Radarr accepted the movie, but it could not be re-resolved by stable identity."),
    "series_reresolve_failed": (33440, "Sonarr accepted the series, but it could not be re-resolved by stable identity."),
    "movie_not_managed": (33441, "The movie is not managed by Radarr. Use Request & Search first."),
    "series_not_managed": (33442, "The series is not managed by Sonarr. Use Request & Search first."),
    "release_state_accepted": (33443, "Accepted"),
    "release_state_rejected": (33444, "Rejected"),
    "release_rejections_none": (33445, "None"),
    "optional_disabled": (33446, "Disabled"),
    "defaults_no_services": (33447, "Enable Radarr or Sonarr before configuring Request & Search defaults."),
    "defaults_missing_choices": (33448, "{service} did not return a usable root folder and quality profile."),
    "bazarr_no_languages": (33449, "Bazarr returned no usable subtitle languages."),
    "subtitle_action_unknown": (33450, "Unknown subtitle action."),
    "subtitle_best_match": (33451, "Bazarr best match"),
    "subtitle_result_label": (33452, "{language} · {provider}{flags}"),
    "subtitle_flags": (33453, " · {flags}"),
    "subtitle_forced": (33454, "forced"),
    "subtitle_hi": (33455, "hearing impaired"),
    "release_detail_template": (33456, "{title}\nIndexer: {indexer}\nProtocol: {protocol}\nAge: {age} days\nCustom-format score: {score}\nRejections: {rejections}"),
    "subtitle_movie_metadata_missing": (33457, "Kodi did not return movie metadata for subtitle search."),
    "subtitle_episode_metadata_missing": (33458, "Kodi did not return episode metadata for subtitle search."),
    "subtitle_library_playback_required": (33459, "Subtitle search requires a playing Kodi library movie or episode."),
}


def imessage(source, key, **values):
    string_id, fallback = INTERACTIVE_MESSAGES[key]
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
