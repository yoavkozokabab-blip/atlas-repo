# Phase 116E — `analytics.jsonl` Permission Failure Investigation

**Date:** 2026-06-02  
**Scope:** Investigation only (no product fixes applied).  
**Target path:** `C:\Users\babi2\.jarvis_desktop\analytics.jsonl`

---

## Executive summary

| Question | Finding |
|----------|---------|
| Where is `analytics.jsonl` written? | **One function only:** `jarvis_desktop/analytics.py` → `track_event()` |
| Append or overwrite? | **Append** (`open(path, "a", encoding="utf-8")`) |
| App-level file locking? | **None** |
| Handles closed? | **Yes** — `with open(...)` context manager on every read/write |
| Reproduced `PermissionError` in lab today? | **No** (single process, threaded, and 4-process probes all succeeded) |
| Demo + Scan same failure path? | **Yes** for scan completion — both call `track_analytics_event("scan_completed", ...)` inside `scan_repository()` without error handling |
| Telemetry regression? | **Yes (Phase 112)** — analytics added 2026-06-02; scan/demo now **fail hard** if append raises `OSError` |

**Most likely root cause (environmental, intermittent):** Windows denied append while another actor held or protected the file (second JARVIS Desktop process, antivirus/Controlled Folder Access, backup/indexer, or exclusive open in another app). **Confirmed architectural amplifier:** telemetry is on the **critical path** of `scan_repository()` / `load_demo_mode()` with no `try/except`, so any `PermissionError` surfaces as scan/demo failure (`500` from `server.dispatch`).

---

## 1. Every write path to `analytics.jsonl`

| # | Location | How it reaches the file |
|---|----------|-------------------------|
| 1 | `jarvis_desktop/analytics.py:track_event` | **Only direct writer** — `open(..., "a")` + one `write()` line |
| 2 | `jarvis_desktop/api.py:track_analytics_event` | Thin wrapper → `analytics.track_event` |
| 3 | `jarvis_desktop/server.py` | `POST /api/analytics/event` → `api.track_analytics_event` |
| 4 | `jarvis_desktop/api.py` (server-side events) | See call table below |
| 5 | `jarvis_desktop/static/app.js` | `trackAnalytics()` → HTTP `POST /api/analytics/event` (same backend path) |
| 6 | `jarvis_desktop/static/marketing.js` | `fetch("/api/analytics/event", ...)` (fire-and-forget) |

**No other code** opens `analytics.jsonl` for writing (grep across `local_jarvis/jarvis_desktop`, excluding demo repo *folder names* named `analytics/`).

### Server-side `track_analytics_event` call sites (`api.py`)

| Event | Function | Line (approx.) | Triggers when |
|-------|----------|----------------|---------------|
| `demo_loaded` | `load_demo_mode` | 593 | After `scan_repository` returns OK |
| `scan_completed` | `scan_repository` (cache hit) | 671 | Cached scan restore completes |
| `scan_completed` | `scan_repository` (full scan) | 939–946 | Full scan completes |
| `export_created` | `context_export` | 1969 | Context export |
| `bundle_exported` | `export_demo_bundle` | 2106 | Demo bundle zip |
| `copilot_question` | `copilot_ask` | 2763 | Copilot question |

### Read-only access (not writers)

| Function | Mode | Purpose |
|----------|------|---------|
| `analytics._read_events` | `"r"` | Load all lines for `analytics_summary()` |
| `analytics.reset_analytics_for_tests` | `os.remove` | Tests only |

---

## 2. I/O semantics (measured from code)

```python
# jarvis_desktop/analytics.py — track_event (writer)
os.makedirs(analytics_data_dir(), exist_ok=True)
with open(path, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
```

| Property | Value |
|----------|--------|
| Write mode | **`"a"` (append)** — never truncates |
| Write mode `"w"` | **Not used** |
| File locking | **None** (no `msvcrt`, `fcntl`, or portalocker) |
| Handle lifetime | Context manager — **closed on exit** (success or exception) |
| Concurrent server | `ThreadingHTTPServer` in `server.py` — **one thread per HTTP request** |

**Conclusion for B/C:** No in-code handle leak; no intentional long-lived write handle. If a handle stays open, it would be **outside** this module (external process or OS/AV).

---

## 3. Temporary diagnostics (Phase 116E)

Added to `jarvis_desktop/analytics.py` (investigation only; remove after fix):

- Log file: `%USERPROFILE%\.jarvis_desktop\analytics_write_diag.log`
- Disable: set env `JARVIS_ANALYTICS_DIAG=0`
- Each append logs: **PID**, **thread id**, **caller** (`file:function:line`), **mode**, **path**
- Stages: `open_attempt` → `open_ok` → `write_ok` or `write_failed` (+ traceback)
- Reads (`analytics_summary`) log: `read_open_attempt` / `read_open_ok` / `read_failed`

**On next user failure:** inspect the last `write_failed` line for PID/tid/caller and compare PIDs across concurrent JARVIS instances.

Probe scripts (investigation, not product):

- `scripts/phase116e_analytics_write_probe.py` — 4 processes × 50 appends
- `scripts/_phase116e_analytics_worker.py`

---

## 4. Hypothesis matrix (A–E)

### A. Multiple JARVIS processes writing simultaneously?

| Evidence | Result |
|----------|--------|
| During investigation | **One** `run_jarvis_desktop.py` (PID 19308) + stray probe workers |
| 4-process probe (`phase116e_analytics_write_probe.py`) | **0 errors**, all exit 0 |
| 64-thread single-process probe | **0 errors** |
| Plausibility | **Possible intermittently** if two desktops run during real use; not reproduced today |

**Recommendation when error occurs:** Task Manager → filter `python.exe` → count command lines containing `run_jarvis_desktop.py`. Diag log should show **different PIDs** on colliding writes.

### B. File handle leak?

| Evidence | Result |
|----------|--------|
| Code review | All I/O uses `with open(...)` |
| **Ruled out** in application code | ✓ |

### C. File never closed?

| Evidence | Result |
|----------|--------|
| Same as B | **Ruled out** in application code |
| Note | `_read_events` holds read handle only for duration of `with` block while iterating lines |

### D. Directory / file permission issue?

| Measurement (2026-06-02) | Result |
|--------------------------|--------|
| File exists | Yes, ~98 KB |
| `IsReadOnly` | **False** |
| `icacls` | `DESKTOP-SVQ1O4E\babi2:(F)` |
| Append from Python (sequential + concurrent) | **OK** |
| **Ruled out as steady-state** on this profile | ✓ for today’s check |
| Caveat | **Controlled Folder Access**, OneDrive “Files On-Demand”, or ACL changes after install can still cause **intermittent** `PermissionError` |

### E. Telemetry regression introduced recently?

| Evidence | Result |
|----------|--------|
| `analytics.py` introduced | **Phase 112** (`phase112-installer-demo`, report `phase112_installer_and_demo_pack.md`) |
| `scan_repository` | Calls `track_analytics_event("scan_completed", ...)` **before return** with **no try/except** |
| `server.dispatch` | Catches any `Exception` → `500` + `"PermissionError: ..."` |
| Frontend `trackAnalytics` | **Swallows** errors — does **not** fail scan UI |
| **Confirmed regression class** | Optional telemetry can **abort** scan/demo when disk/OS denies append |

---

## 5. Demo Mode vs Repository Scan — same path?

### Repository scan (user repo)

```
POST /api/repositories/scan
  → api.scan_repository()
      → … build graph / cache …
      → track_analytics_event("scan_completed", ...)   # api.py ~939 or ~671
          → analytics.track_event()
              → open(analytics.jsonl, "a")
```

If `PermissionError` is raised here, the HTTP response is **500** and the UI shows scan failure **after** analysis work may have completed.

### Demo Mode

```
POST /api/demo/load
  → api.load_demo_mode()
      → api.scan_repository(demo_path)     # same scan_completed analytics tail
      → track_analytics_event("demo_loaded", ...)   # second append if scan succeeded
```

| Path | Fails on analytics? |
|------|---------------------|
| Scan completion (`scan_completed`) | **Yes** — shared |
| `demo_loaded` | Only if scan path already succeeded |
| Frontend-only events (`graph_opened`, `product_tour_started`) | **No** — `app.js` catches errors; scan already done |

**Answer:** Demo and repository scan **share the same blocking analytics write** at the end of `scan_repository()`. Demo adds one more append (`demo_loaded`) only after scan returns OK.

---

## 6. Exact failing call stack (expected when error occurs)

When the user sees `PermissionError: C:\Users\babi2\.jarvis_desktop\analytics.jsonl`, the stack is:

```
http.server (ThreadingHTTPServer worker thread)
  JarvisHandler → server.dispatch()
    handler POST /api/repositories/scan  OR  POST /api/demo/load
      api.scan_repository()                    [api.py ~597]
        track_analytics_event("scan_completed", ...)   [api.py ~671 or ~939]
          analytics.track_event()                [analytics.py ~62]
            open(path, "a", encoding="utf-8")    [analytics.py ~75]  ← raises PermissionError
```

Demo-only second stack (if scan analytics succeeded):

```
api.load_demo_mode() [api.py ~593]
  track_analytics_event("demo_loaded", ...)
    analytics.track_event() → open(..., "a")
```

**Exact writer:** `analytics.track_event` — **line with `open(path, "a", ...)`**.

---

## 7. Reproduction steps (for confirming on user machine)

1. Ensure diagnostics enabled (default on): restart JARVIS from `local_jarvis`:
   ```powershell
   cd c:\J.A.R.V.I.S\local_jarvis
   py -3 run_jarvis_desktop.py
   ```
2. Note whether **more than one** `run_jarvis_desktop.py` is running.
3. Trigger failure path:
   - **Scan:** Home → path → Scan, or  
   - **Demo:** Try Demo / Product Tour (uses `POST /api/demo/load`).
4. On failure, capture:
   - UI / network error body (`PermissionError: ...`)
   - Tail of `%USERPROFILE%\.jarvis_desktop\analytics_write_diag.log` (look for `write_failed`)
   - `icacls %USERPROFILE%\.jarvis_desktop\analytics.jsonl`
   - Process list: `Get-CimInstance Win32_Process -Filter "name='python.exe'" | ? { $_.CommandLine -match 'jarvis' }`
5. Optional stress: with desktop running, open `static/admin.html` (polls `GET /api/analytics/summary`) while starting a large scan.

**Lab reproduction today:** Could not trigger `PermissionError` under steps above or probe scripts.

---

## 8. Measurements run (2026-06-02)

| Test | Result |
|------|--------|
| Sequential 5× append | OK |
| 64 threads × append (1 process) | OK |
| 20× concurrent `GET /api/analytics/summary` + 20× `track_analytics_event` | OK |
| 4 processes × 50 appends (`phase116e_analytics_write_probe.py`) | OK |
| Read held 2s + 8 concurrent appends | OK |
| Append handle held 2s + 5 concurrent appends | OK |
| `msvcrt` byte lock + append | OK (append still succeeded) |
| File ACL / read-only flag | User has **(F)**, not read-only |

---

## 9. Recommended fix (do not implement in 116E)

Priority order for a follow-up phase:

1. **Decouple telemetry from scan success** — wrap `track_analytics_event` (or `track_event`) in `try/except OSError`, log warning, never fail `scan_repository` / `load_demo_mode`.
2. **Serialize writes** — module-level `threading.Lock` around append (prevents same-process races; helps some Windows sharing cases).
3. **Retry with backoff** — 2–3 retries on `PermissionError` / `WinError 32`.
4. **Operational** — document “only one JARVIS Desktop instance”; detect second instance on `run_jarvis_desktop.py` startup.
5. **Remove Phase 116E diagnostics** after fix verified — `analytics_write_diag.log` + `JARVIS_ANALYTICS_DIAG` gate.

No Builder Core changes required.

---

## 10. Files touched in this investigation

| File | Change |
|------|--------|
| `jarvis_desktop/analytics.py` | Temporary write/read diagnostics |
| `scripts/phase116e_analytics_write_probe.py` | Multi-process probe (new) |
| `scripts/_phase116e_analytics_worker.py` | Probe worker (new) |
| `reports/phase116e_analytics_permission_failure.md` | This report |

**Not changed:** `builder_core/`, scan/graph logic, fixes to telemetry behavior.
