# Phase 116C Native Browse Flow

**Date:** 2026-06-02
**Scope:** Local desktop repository-folder selection only
**Status:** Implemented and test-verified
**Builder Core analysis changes:** None

## Goal

Allow a first-time user to choose a local repository folder without knowing or
typing its full filesystem path.

## User Flow

1. User opens JARVIS Desktop on localhost.
2. User clicks `Browse`.
3. JARVIS requests `POST /api/system/browse-folder`.
4. The backend opens a Windows folder picker when the local desktop session
   supports it.
5. A selected folder path returns to the browser.
6. The repository input is populated.
7. Existing repository validation runs automatically.
8. The user explicitly clicks `Scan Repository`.

Manual paste-path entry remains available at all times.

## Implementation

### Backend

Added `jarvis_desktop/system_browse.py`:

- Uses `tkinter.filedialog.askdirectory()`.
- Requests a folder, not a file.
- Runs the native picker in a bounded daemon worker.
- Returns after `120s` if the picker does not respond.
- Returns structured success, cancellation, timeout, invalid-path, and
  unsupported-environment payloads.
- Returns only a local path.
- Does not upload files.
- Does not execute commands.

Added route:

```text
POST /api/system/browse-folder
```

The stdlib HTTP handler and optional FastAPI handler reject non-loopback HTTP
clients for this endpoint.

### Frontend

Added a `Browse` button beside the Home repository-path input.

Frontend behavior:

- disable the button while the picker request is active;
- keep current input unchanged on cancellation;
- populate the input after a selection;
- run existing validation immediately after selection;
- display a friendly manual-path fallback if native browsing is unavailable;
- preserve the existing Validate button, Scan button, Enter key, and recent
  repository chips.

## API Contract

### Selected Folder

```json
{
  "ok": true,
  "supported": true,
  "cancelled": false,
  "path": "C:\\projects\\my-repository"
}
```

### Cancellation

```json
{
  "ok": true,
  "supported": true,
  "cancelled": true,
  "path": null
}
```

### Unsupported Desktop Session

```json
{
  "ok": false,
  "supported": false,
  "cancelled": false,
  "code": "unsupported_browse_dialog",
  "error": "unsupported_browse_dialog",
  "message": "Paste the folder path manually."
}
```

### Timeout

```json
{
  "ok": false,
  "supported": false,
  "cancelled": false,
  "code": "picker_timeout",
  "error": "The folder picker did not respond. Paste the repository path manually."
}
```

## Security

- Native browsing is exposed only through a localhost route.
- The endpoint opens a folder chooser only.
- The response contains a local path only.
- No file contents are read by the Browse endpoint.
- No file upload exists.
- No shell command or arbitrary executable path is accepted.
- Raw native-picker exception strings are not returned to the UI.

## Tests

Added and exercised:

- mocked selected path returns the chosen repository path;
- cancellation returns `cancelled=true`;
- unsupported environment returns a structured fallback;
- raw unsupported exception text is not leaked;
- loopback restriction helper accepts `127.0.0.1` and `::1`;
- frontend calls the Browse endpoint;
- selected path populates the input before validation;
- Scan still uses the validated input path;
- manual paste-path entry remains present;
- recent-repository chips remain present;
- frontend API calls all map to registered backend routes;
- no frontend Browse call can produce `Unknown endpoint`.

Full desktop verification:

```text
py -3 -m pytest jarvis_desktop/tests -q -p no:cacheprovider --basetemp <isolated-temp>

146 passed in 20.70s
```

## Manual Verification

Verified in the live localhost UI:

- `Browse` is visible beside repository input.
- Clicking `Browse` calls the endpoint.
- The hidden background-hosted preview returned a clean cancellation without
  corrupting the current input.
- Manual fallback validation worked with `C:\J.A.R.V.I.S\fastapi`.
- FastAPI scan completed through the UI.
- Django and VS Code scans completed through the localhost API.

Not fully verified in this environment:

- A visible native Explorer window did not surface while the local preview
  server was running as a hidden background helper.
- A final foreground Windows launch should confirm click -> Explorer folder
  picker -> select folder -> populated path -> validation.

## Files

Phase 116C Browse-related files:

- `jarvis_desktop/system_browse.py`
- `jarvis_desktop/server.py`
- `jarvis_desktop/static/index.html`
- `jarvis_desktop/static/app.js`
- `jarvis_desktop/tests/test_phase107_desktop_api.py`
- `jarvis_desktop/tests/test_phase116c_native_browse_flow.py`

Concurrent Phase 116D/F work overlaps several desktop files. A clean Browse-only
commit should be prepared only after those edits are merged or separated.
