# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import urllib.parse
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import os

from arr_manager.config import Settings
from arr_manager.clients import BazarrClient
from arr_manager.actions import ArrManager
from arr_manager.resolver import resolve_movie, resolve_series, resolve_episode
from arr_manager.kodi_log import KodiLogger

addon = xbmcaddon.Addon()
logger = KodiLogger()

class SubtitleSelectedItem:
    def __init__(self, title, year, season, episode, tvshow_title, db_id, file_path):
        self.title = title
        self.year = year
        self.season = season
        self.episode = episode
        self.tvshow_title = tvshow_title
        self.db_id = db_id
        self.file_path = file_path
        self.media_type = "movie" if not tvshow_title else "episode"
        self.imdb_id = None
        self.tvdb_id = None
        self.tmdb_id = None

def search_subtitles():
    params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
    action = params.get('action')

    if action in ['search', 'manualsearch']:
        settings = Settings(addon)
        bazarr = getattr(settings, "bazarr", None)
        if not bazarr or not bazarr.enabled:
            return

        bc = BazarrClient(bazarr.url, bazarr.api_key, bazarr.timeout, bazarr.verify_tls, logger)
        manager = ArrManager(settings, None, logger)

        filepath = urllib.parse.unquote(params.get('file_original_path', ''))

        item = SubtitleSelectedItem(
            title=urllib.parse.unquote(params.get('title', '')),
            year=params.get('year', ''),
            season=params.get('season', ''),
            episode=params.get('episode', ''),
            tvshow_title=urllib.parse.unquote(params.get('tvshow', '')),
            db_id=0,
            file_path=filepath
        )

        try:
            if item.media_type == "movie":
                entity = resolve_movie(item, manager.radarr, settings.path_mapper)
                search_data = bc.search_movie_subtitles(entity["id"])
                for sub in search_data.get("subtitles", []):
                    listitem = xbmcgui.ListItem(label=sub.get('subtitle', 'Unknown'))
                    listitem.setArt({'icon': "0", 'thumb': "0"})
                    listitem.setProperty("sync", "true" if sub.get('score', 0) > 90 else "false")
                    listitem.setProperty("hearing_impaired", "true" if sub.get('hi', False) else "false")
                    url = f"plugin://{addon.getAddonInfo('id')}/?action=download&id={sub.get('id')}&radarrid={entity['id']}&lang={sub.get('language')}"
                    import xbmcplugin
                    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listitem, isFolder=False)
            else:
                series = resolve_series(item, manager.sonarr, settings.path_mapper)
                episode = resolve_episode(item, manager.sonarr, series)
                search_data = bc.search_episode_subtitles(episode["id"])
                for sub in search_data.get("subtitles", []):
                    listitem = xbmcgui.ListItem(label=sub.get('subtitle', 'Unknown'))
                    listitem.setArt({'icon': "0", 'thumb': "0"})
                    listitem.setProperty("sync", "true" if sub.get('score', 0) > 90 else "false")
                    listitem.setProperty("hearing_impaired", "true" if sub.get('hi', False) else "false")
                    url = f"plugin://{addon.getAddonInfo('id')}/?action=download&id={sub.get('id')}&seriesid={series['id']}&episodeid={episode['id']}&lang={sub.get('language')}"
                    import xbmcplugin
                    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listitem, isFolder=False)
        except Exception as e:
            logger.error(f"Failed to find subtitles: {e}")

    elif action == 'download':
        settings = Settings(addon)
        bazarr = getattr(settings, "bazarr", None)
        bc = BazarrClient(bazarr.url, bazarr.api_key, bazarr.timeout, bazarr.verify_tls, logger)

        radarrid = params.get('radarrid')
        seriesid = params.get('seriesid')
        episodeid = params.get('episodeid')
        lang = params.get('lang')

        try:
            if radarrid:
                bc.download_movie_subtitle(radarrid, lang)
            else:
                bc.download_episode_subtitle(seriesid, episodeid, lang)
            xbmcgui.Dialog().notification("Bazarr", "Subtitle downloaded.", xbmcgui.NOTIFICATION_INFO, 5000)
        except Exception as e:
            logger.error(f"Failed to download subtitle: {e}")

    import xbmcplugin
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

if __name__ == '__main__':
    search_subtitles()
