# SPDX-License-Identifier: GPL-3.0-or-later
"""Replacement reliability fallbacks kept separate from the stable string IDs."""

_REPLACEMENT_MESSAGES = {
    "search_movie_done": "Radarr queued a search for {title}.",
    "search_series_done": "Sonarr queued a full series search for {title}.",
    "search_episode_done": "Sonarr queued a search for {title} S{season:02d}E{episode:02d}.",
    "movie_replace_done": "{blocklist} Deleted the file and queued a replacement search for {title}.",
    "episode_replace_done": "{blocklist} Deleted the file and queued a replacement search for {title} {episodes}.",
    "series_replace_done": "{blocklist} Deleted {files} files and queued a series search for {title}.",
    "movie_missing_search_queued": "{title} is already missing in Radarr; a recovery search was queued without another deletion or blocklist action.",
    "episode_missing_search_queued": "{title} S{season:02d}E{episode:02d} is already missing in Sonarr; a recovery search was queued without another deletion or blocklist action.",
    "movie_missing_search_confirm": "{title} has no Radarr movie file. Queue an exact recovery search without deleting or blocklisting anything?",
    "episode_missing_search_confirm": "{title} S{season:02d}E{episode:02d} has no Sonarr episode file. Queue an exact recovery search without deleting or blocklisting anything?",
    "dry_movie_recovery": "Dry run: would queue an exact recovery search for {title}; nothing was changed.",
    "dry_episode_recovery": "Dry run: would queue an exact recovery search for {title} S{season:02d}E{episode:02d}; nothing was changed.",
}


def replacement_message(key, values):
    template = _REPLACEMENT_MESSAGES.get(key)
    if template is None:
        return None
    try:
        return template.format(**values)
    except (KeyError, ValueError, IndexError):
        return template
