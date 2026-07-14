# Development references

The initial scaffold was cross-checked against:

## Official Kodi documentation

- Context item add-ons, nested submenus, action arguments, visibility expressions and `sys.listitem`: <https://kodi.wiki/view/Context_Item_Add-ons>
- Add-on metadata and extension declarations: <https://kodi.wiki/view/Addon.xml>
- Add-on layout and `resources/lib`: <https://kodi.wiki/view/Add-on_structure>
- Settings UI definitions and action settings: <https://kodi.wiki/view/Add-on_settings>
- Kodi Python libraries, including `xbmcvfs`: <https://kodi.wiki/view/Python_libraries>

## Battle-tested Kodi examples

- Officially referenced Python video plug-in example: <https://github.com/romanvm/plugin.video.example>
- Trakt context-menu add-on, used to verify the established `kodi.context.item` structure and video-library visibility pattern: <https://github.com/razzeee/context.trakt.contextmenu>

## Servarr source contracts

- Radarr movie deletion and import exclusion: `Radarr.Api.V3/Movies/MovieController.cs`
- Radarr movie-file deletion: `Radarr.Api.V3/MovieFiles/MovieFileController.cs`
- Radarr imported-history failure/blocklist path: `Radarr.Api.V3/History/HistoryController.cs`
- Sonarr series deletion and import-list exclusion: `Sonarr.Api.V3/Series/SeriesController.cs`
- Sonarr episode-file deletion: `Sonarr.Api.V3/EpisodeFiles/EpisodeFileController.cs`
- Sonarr imported-history failure/blocklist path: `Sonarr.Api.V3/History/HistoryController.cs`
- Search command payloads: `MoviesSearchCommand`, `EpisodeSearchCommand`, and `SeriesSearchCommand` in the respective Radarr/Sonarr repositories.
