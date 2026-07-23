from pathlib import Path


def replace_once(path, old, new):
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8")
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Expected one match in {path}, found {count}: {old[:80]!r}")
    file_path.write_text(source.replace(old, new, 1), encoding="utf-8")


replace_once(
    "resources/lib/arr_manager/models.py",
    '''    @property
    def display_name(self) -> str:
''',
    '''    def effective_unique_ids(self) -> Dict[str, str]:
        if self.media_type == "episode":
            return self.series_unique_ids or {}
        return self.unique_ids or {}

    def effective_year(self) -> int:
        value = self.series_year if self.media_type == "episode" else self.year
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def display_name(self) -> str:
''',
)

replace_once(
    "resources/lib/arr_manager/resolver.py",
    '''def _series_unique_ids(selected):
    if selected.media_type == "episode":
        return getattr(selected, "series_unique_ids", {}) or {}
    return selected.unique_ids or {}


def _series_year(selected):
    if selected.media_type == "episode":
        return _year(getattr(selected, "series_year", 0))
    return _year(selected.year)


''',
    "",
)
replace_once(
    "resources/lib/arr_manager/resolver.py",
    '    tvdb_id = _numeric_unique_id(_series_unique_ids(selected).get("tvdb"))\n',
    '    tvdb_id = _numeric_unique_id(selected.effective_unique_ids().get("tvdb"))\n',
)
replace_once(
    "resources/lib/arr_manager/resolver.py",
    '        selected_year = _series_year(selected)\n',
    '        selected_year = selected.effective_year()\n',
)

replace_once(
    "resources/lib/arr_manager/kodi_selected.py",
    '''def _series_unique_ids(selected):
    if getattr(selected, "media_type", "") == "episode":
        return getattr(selected, "series_unique_ids", {}) or {}
    return getattr(selected, "unique_ids", {}) or {}


def _series_year(selected):
    if getattr(selected, "media_type", "") == "episode":
        return int(getattr(selected, "series_year", 0) or 0)
    return int(getattr(selected, "year", 0) or 0)


''',
    "",
)
replace_once(
    "resources/lib/arr_manager/kodi_selected.py",
    '''def _tvshow_has_strong_identity(selected):
    return bool(_series_unique_ids(selected)) or bool(
        (getattr(selected, "tvshow_title", "") or getattr(selected, "title", "")) and _series_year(selected)
    )
''',
    '''def _tvshow_has_strong_identity(selected):
    return bool(selected.effective_unique_ids()) or bool(
        (selected.tvshow_title or selected.title) and selected.effective_year()
    )
''',
)
replace_once(
    "resources/lib/arr_manager/kodi_selected.py",
    '    selected_year = _series_year(selected)\n',
    '    selected_year = selected.effective_year()\n',
)
replace_once(
    "resources/lib/arr_manager/kodi_selected.py",
    '    unique_state = _unique_id_state(_series_unique_ids(selected), details.get("uniqueid"))\n',
    '    unique_state = _unique_id_state(selected.effective_unique_ids(), details.get("uniqueid"))\n',
)

replace_once(
    "resources/lib/arr_manager/actions_interactive.py",
    '''def _series_tvdb_id(selected):
    ids = selected.unique_ids if selected.media_type == "tvshow" else getattr(selected, "series_unique_ids", {})
    return _positive_id((ids or {}).get("tvdb"))


def _series_year(selected):
    return int(selected.year or 0) if selected.media_type == "tvshow" else int(getattr(selected, "series_year", 0) or 0)
''',
    '''def _series_tvdb_id(selected):
    return _positive_id(selected.effective_unique_ids().get("tvdb"))


def _series_year(selected):
    return selected.effective_year()
''',
)

replace_once(
    "resources/lib/arr_manager/interactive_messages.py",
    '    "subtitle_playback_changed": (33463, "Kodi playback changed before the subtitle download completed."),\n',
    '    "subtitle_playback_changed": (33463, "Kodi playback changed before the subtitle download completed."),\n'
    '    "prowlarr_connection": (33464, "Prowlarr connection"),\n'
    '    "bazarr_connection": (33465, "Bazarr connection"),\n',
)
replace_once(
    "resources/lib/arr_manager/entrypoints.py",
    'from .interactive_messages import imessage\n',
    'from .interactive_messages import INTERACTIVE_MESSAGES, imessage\n',
)
replace_once(
    "resources/lib/arr_manager/entrypoints.py",
    '''        if mode == "test_prowlarr":
            ui.ok("Prowlarr", _test_prowlarr(settings, logger)); return
        if mode == "test_bazarr":
            ui.ok("Bazarr", _test_bazarr(settings, logger)); return
''',
    '''        if mode == "test_prowlarr":
            ui.ok(_s(addon, *INTERACTIVE_MESSAGES["prowlarr_connection"]), _test_prowlarr(settings, logger)); return
        if mode == "test_bazarr":
            ui.ok(_s(addon, *INTERACTIVE_MESSAGES["bazarr_connection"]), _test_bazarr(settings, logger)); return
''',
)

replace_once(
    "tests/test_release_readiness.py",
    'from arr_manager import entrypoints\n',
    'from arr_manager import entrypoints\nfrom arr_manager.actions_interactive import _series_tvdb_id, _series_year\n',
)
replace_once(
    "tests/test_release_readiness.py",
    'from arr_manager.kodi_selected import enrich_selected_series_identity\n',
    'from arr_manager.interactive_messages import INTERACTIVE_MESSAGES\nfrom arr_manager.kodi_selected import enrich_selected_series_identity\n',
)
replace_once(
    "tests/test_release_readiness.py",
    '''    def test_episode_parent_series_identity_is_enriched_and_episode_tvdb_is_not_reused(self):
''',
    '''    def test_effective_identity_uses_series_values_only_for_episodes(self):
        episode = SelectedItem(
            media_type="episode", unique_ids={"tvdb": "555"}, year=2024,
            series_unique_ids={"tvdb": "99"}, series_year=2020,
        )
        movie = SelectedItem(
            media_type="movie", unique_ids={"tvdb": "7"}, year=2023,
            series_unique_ids={"tvdb": "999"}, series_year=1999,
        )
        self.assertEqual(episode.effective_unique_ids(), {"tvdb": "99"})
        self.assertEqual(episode.effective_year(), 2020)
        self.assertEqual(movie.effective_unique_ids(), {"tvdb": "7"})
        self.assertEqual(movie.effective_year(), 2023)
        self.assertEqual(_series_tvdb_id(movie), 7)
        self.assertEqual(_series_year(movie), 2023)

    def test_optional_service_connection_headings_are_catalog_backed(self):
        self.assertEqual(INTERACTIVE_MESSAGES["prowlarr_connection"], (33464, "Prowlarr connection"))
        self.assertEqual(INTERACTIVE_MESSAGES["bazarr_connection"], (33465, "Bazarr connection"))

    def test_episode_parent_series_identity_is_enriched_and_episode_tvdb_is_not_reused(self):
''',
)
