# Bazarr subtitle reliability

Kodi Managarr v1.3.3 uses Bazarr's authenticated `/api` contract:

- `GET /api/system/status` and `GET /api/system/languages` for compatibility checks;
- `GET /api/providers/movies?radarrid=…` and `GET /api/providers/episodes?episodeid=…` for manual search;
- `POST` to the same provider endpoint with the exact provider/subtitle identity and required `hi`, `forced`, and `original_format` fields for selection.

The provider fails closed on bootstrap, malformed handles/queries, unsupported actions, playback identity changes, malformed API responses, stale/replayed tokens, and inaccessible paths. It never returns an unverified server-local path to Android Kodi. Delivery accepts an already accessible Kodi path, a verified remote-to-Kodi mapping, or a newly visible sidecar beside the playing SMB file.

Bazarr failures are reduced to operation, category and optional HTTP status. URLs, API keys, payload identities, media paths and response bodies are not logged or shown.

## Android validation

Physical Hisense/Toshiba A4 execution is **NOT TESTED** in the automated gate. Use disposable media and verify:

1. provider search closes its directory on both success and failure;
2. one and three configured languages retain order and forced/HI qualifiers;
3. movie, episode, season-zero and multi-episode playback resolve the intended Arr item;
4. exact provider download produces an SMB sidecar or mapped Kodi-accessible path;
5. an unmapped Debian path is rejected rather than returned;
6. a consumed or expired token cannot be replayed;
7. diagnostics and logs contain no API key, URL or private media path.
