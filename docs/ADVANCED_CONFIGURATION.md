# Advanced configuration

This guide is for users who need more control than the basic setup in the [README](../README.md).

Most users only need:

- a working Radarr or Sonarr connection;
- Servarr API deletion;
- the default path and network settings;
- dry run enabled for the first destructive tests.

Change advanced settings only when you understand why they are needed.

## Contents

- [Deletion methods](#deletion-methods)
- [Path mappings](#path-mappings)
- [Request and Search behaviour](#request-and-search-behaviour)
- [Prowlarr](#prowlarr)
- [Bazarr subtitles](#bazarr-subtitles)
- [Menu layout](#menu-layout)
- [PIN protection](#pin-protection)
- [Retention](#retention)
- [Remote-button shortcuts](#remote-button-shortcuts)
- [Diagnostics](#diagnostics)
- [Safety behaviour](#safety-behaviour)
- [Developer documentation](#developer-documentation)

## Deletion methods

Managarr supports two deletion approaches.

### Servarr API deletion

This is the default and recommended method.

Radarr or Sonarr performs the deletion. The service can update its own database and filesystem state together.

Use this method unless you have a specific reason to use Kodi VFS deletion.

Retention always uses the Servarr API method.

### Kodi VFS deletion

Kodi VFS deletion is intended for an explicit media path that Kodi can access, including an `smb://` path.

This method may be useful when:

- the server path and Kodi path are different;
- Kodi already has working share credentials;
- the Servarr service cannot delete the file itself.

Kodi VFS deletion needs correct path mappings. Managarr validates the path before it changes anything.

Direct deletion always asks for confirmation. This remains true when normal API confirmations are disabled.

## Path mappings

A path mapping converts a media path returned by Radarr, Sonarr, or Bazarr into a path that Kodi can access.

Use a mapping when the server and Kodi use different path formats.

Example:

```text
/media/Movies=>smb://server/Movies;/media/Shows=>smb://server/Shows
```

The left side is the server path. The right side is the Kodi path.

Separate multiple mappings with a semicolon.

Another example with SFTP:

```text
/media/Shows=>sftp://server:22/media/Shows
```

Only use SFTP when the Kodi environment has the required support and credentials.

### Path protection

Every configured mapping root is protected automatically.

Managarr can operate on a validated child path. It will not delete:

- `/`;
- an empty path;
- a share root;
- a mapping root;
- a configured protected path;
- an ancestor of a protected path;
- a malformed or traversal path;
- an ambiguous path.

A path-mapping problem does not block ordinary Servarr API actions that do not need the mapping.

## Request and Search behaviour

**Request & Search** can work with an item that is already managed or an item that is only present in Kodi.

### Managed item

Managarr finds the existing Radarr or Sonarr item, updates monitoring when needed, and starts the correct search.

### Unmanaged item

Managarr uses the saved request defaults to add the movie or series. It then starts a search.

The saved defaults are:

- one Radarr root folder;
- one Radarr quality profile;
- one Sonarr root folder;
- one Sonarr quality profile;
- one Sonarr monitoring mode.

These are persistent defaults. They are not per-request routing rules. Managarr does not provide multi-instance, HD/4K, or tag-based request routing through this feature.

### Identity matching

Managarr prefers stable IDs:

- TMDb for movies;
- TVDb for series.

When a stable ID is unavailable, it can use an exact normalised title and year. Ambiguous results require a Kodi selection. Managarr does not silently use the first result.

Episode actions obtain the parent TV show identity through Kodi. They do not treat an episode TVDb ID as a series TVDb ID.

Title fallback matching keeps letters and numbers from many writing systems. It removes or normalises punctuation and spacing only where needed for an exact comparison.

## Prowlarr

Prowlarr is optional.

Managarr can use Prowlarr for:

- service status;
- health information;
- indexer information;
- an informational search count when Radarr or Sonarr returns no releases.

Prowlarr is read-only from Managarr. It does not:

- download a release;
- replace Radarr or Sonarr release handling;
- delete media;
- manage movie or episode history;
- become the authority for a media item.

## Bazarr subtitles

Bazarr is optional.

Choose one to three unique subtitle languages in preference order.

A base language accepts its normal variants. For example, `en` can accept normal, forced, and hearing-impaired English results.

A qualified language accepts only that variant. For example, `en:forced` accepts forced English results only.

During playback:

1. Open Kodi's subtitle-search window.
2. Select the Kodi Managarr or Bazarr provider.
3. Select a result.

Managarr stores only short-lived provider identity and stable database IDs for a result. It consumes the result token before requesting the Bazarr download. It then confirms that playback still matches the original item.

The final subtitle path must already be accessible to Kodi or be safely converted through a path mapping.

## Menu layout

The normal menu is hierarchical. Monitoring, Download queue, Retention, and Tools open their own submenus.

Each configurable item has a numeric rank:

- `0` disables the item;
- `1` to `999` enables it;
- a lower number appears earlier.

Default ranks use gaps of ten. You can place a new item between `10` and `20` by using a number such as `15`.

The TV-remote editor can:

- change visible items as a group;
- move an item directly to the top or bottom;
- move an item before or after another item;
- enter a numeric rank;
- flatten selected submenus;
- preview the final menu;
- normalise ranks;
- restore defaults.

Flattening replaces a submenu parent with one labelled block of its enabled child items.

See [Menu layout](MENU_LAYOUT.md) for the full ordering, migration, and recovery rules.

## PIN protection

The local PIN contains 4 to 8 digits.

Managarr stores a salted PBKDF2-HMAC derivation. It does not store the plaintext PIN.

The PIN protects:

- Delete & Exclude;
- Delete & Replace;
- real manual retention cleanup;
- enabling real periodic retention.

Queue removal and disabling periodic retention use their own confirmation rules.

Changing, repairing, or removing the PIN invalidates previous authorisation for real periodic retention. Periodic deletion must be enabled again when required.

The PIN prevents accidental use through the normal Kodi interface. It is not a security boundary against a person who can edit Kodi profile files or add-on data.

## Retention

Retention is an optional cleanup feature. It is disabled by default.

Movies and episodes must be enabled separately.

### Recommended setup order

1. Enable retention features.
2. Enable movies, episodes, or both.
3. Keep **Require watched state** enabled.
4. Set the age rules.
5. Set movie rating protection when needed.
6. Add explicit exclusions.
7. Keep manual and periodic dry run enabled.
8. Set a low maximum deletion limit.
9. Run several previews.
10. Review the last report after each test.
11. Enable real deletion only when every result is correct.

### Age rules

Retention can use:

- minimum days since added;
- minimum days since watched.

Choose whether **all** enabled age rules or **any** enabled age rule must pass.

For added age, Managarr uses the newest usable Kodi, movie, series, or media-file timestamp. This protects a file that was recently imported or added again.

For watched age, Managarr uses Kodi's last-played timestamp. Missing or future timestamps protect the media instead of making it eligible.

### Movie rating protection

Set a value from `0` to `10`.

- `0` disables rating protection.
- A higher value protects movies rated at or above that value.
- When rating protection is enabled, an unrated movie is also protected.

An invalid value blocks retention instead of weakening protection.

### Explicit exclusions

Separate entries with commas, semicolons, or new lines.

Supported forms:

```text
movie:<Kodi movie ID>
episode:<Kodi episode ID>
series:<Kodi TV show ID>
season:<Kodi TV show ID>:<season number>
```

Example:

```text
movie:42;series:17;season:17:0
```

An invalid exclusion entry makes the retention configuration invalid. Managarr does not ignore an unsafe exclusion error.

### Episode files

One physical Sonarr file can contain more than one episode.

Managarr protects the file unless every linked episode:

- is still present in Kodi;
- matches the retention rules;
- is safe to unmonitor and delete.

Before deleting an eligible file, Managarr unmonitors every linked Sonarr episode.

### Movies

Movie cleanup uses Radarr deletion and adds a Radarr import-list exclusion.

### Periodic retention

Periodic retention runs through the Kodi background service.

It stores authorisation for the current PIN generation. A PIN change disables real periodic deletion until you enable it again.

The service checks the schedule, authorisation, ownership state, and target eligibility again during a run. A state or report persistence failure suspends periodic retention rather than allowing an uncontrolled repeat.

## Remote-button shortcuts

Kodi Keymap Editor can expose **Launch Kodi Managarr** under add-on actions.

Advanced keymaps can call a mode directly:

```xml
<key>RunScript(context.arr.manager,mode=request_search)</key>
<key>RunScript(context.arr.manager,mode=interactive_search)</key>
<key>RunScript(context.arr.manager,mode=dashboard)</key>
<key>RunScript(context.arr.manager,mode=retention_preview)</key>
<key>RunScript(context.arr.manager,mode=retention_cleanup)</key>
<key>RunScript(context.arr.manager,mode=delete_replace)</key>
```

A hidden menu item can still be called by a direct mode. Destructive modes still pass through the same PIN, confirmation, matching, and safety checks.

## Diagnostics

Use **Tools & settings → Write diagnostics**.

The diagnostics file contains non-secret configuration and runtime information. It can help identify:

- connection problems;
- path-mapping problems;
- selected-item resolution problems;
- the last non-secret transaction state.

Managarr excludes API keys and credential-bearing URLs from diagnostics.

When reporting a problem, include:

- the diagnostics file;
- the relevant Kodi log section;
- the Kodi version;
- the Managarr version;
- the affected media type;
- the action that failed;
- whether dry run was enabled.

Do not include passwords, API keys, private keys, private URLs, or share credentials.

## Safety behaviour

Managarr is designed to stop when important information is missing or ambiguous.

Important rules include:

- dry run is enabled on a fresh installation;
- retention is disabled on a fresh installation;
- Servarr API deletion is the default;
- direct deletion always requires confirmation;
- destructive matching must identify exactly one intended item or file;
- strict replacement can require an imported release-history match;
- a replacement search does not start after a required deletion or blocklist failure;
- path boundaries are checked before direct deletion;
- all files in a multi-file operation are checked before the first mutation;
- Servarr rescans and file-record reconciliation use bounded polling;
- partial changes are recorded and reported by stage;
- API keys and credential-bearing URLs are not written to normal logs or diagnostics.

For implementation details, see [Architecture](ARCHITECTURE.md).

## Developer documentation

End-user and contributor material is kept separate.

- [README](../README.md) — installation and everyday use.
- [Contributing](../CONTRIBUTING.md) — development setup and required checks.
- [Architecture](ARCHITECTURE.md) — runtime boundaries and design decisions.
- [Agent sources](AGENT_SOURCES.md) — authoritative external sources.
- [Android Kodi validation](ANDROID_KODI_VALIDATION.md) — device test procedure.
- [Release checklist](RELEASE_CHECKLIST.md) — maintainer release process.