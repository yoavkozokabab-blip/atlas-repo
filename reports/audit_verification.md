# Audit Verification Report

**Date:** 2026-05-29  
**Method:** Every claim verified against exact file, line, and code snippet.  
**Scope:** Critical findings from `master_audit.md` only.  
**Rule:** If the code does not prove it, it is not in this report.

---

## Corrections to the Previous Audit

Three claims in `master_audit.md` were wrong and are retracted here:

| Claim | Verdict | Evidence |
|-------|---------|---------|
| "Action registry silently drops actions with import errors" | **WRONG** | All 558 imports in `actions/registry.py:1–562` are at module level with no try/except. An import error crashes the entire startup, not silently. |
| "TTS failure is silent to the user" | **WRONG** | `voice/tts.py:673–674` prints `[TTS ERROR]` to console and calls `_overlay_tts_warning()` which calls `notify_overlay_error()`. Failures are surfaced. |
| "Microphone disconnect kills voice permanently until restart" | **WRONG** | `voice/voice_loop.py:194–203` catches `MicrophoneError` and calls `continue`, keeping the loop alive. The real issue is different — see VF-4 below. |

---

## Verified Findings

### VF-1 — Backup files grow forever with no cleanup

**Severity:** CRITICAL  
**File:** `core/persistent_json.py`  
**Lines:** 28–34

```python
def atomic_write_json(path: Path, payload: Any, *, indent: int = 2) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.stat().st_size > 0:
        try:
            shutil.copy2(path, backup_dir / f"{path.stem}_{_timestamp()}.json")
        except OSError as exc:
            logger.debug("Backup skipped for %s: %s", path, exc)
```

**What it does:** Every call to `atomic_write_json` copies the existing file to `data/backups/<stem>_<YYYYMMDD_HHMMSS>.json`. No cleanup follows.

**The only cleanup in the file** is inside `load_json` (line 85), which reads `backups[:5]` when recovering a corrupt file. It never deletes old backups.

**Current state, verified by shell:**
- `data/backups/` contains **2,522 files totalling 66 MB**
- Sample file names: `verification_plans_20260528_145322.json`, `approved_apps_20260522_113024.json`
- 22 distinct JSON files are backed up via `atomic_write_json`
- `verification_plans_*`: **75 backup copies**; `hypotheses_*`: **118 backup copies**

**Call sites:** `atomic_write_json` is called from **45 locations** across `assistant/`, `investigation/`, `core/session.py`, `memory/repair.py`, and others. Every state-saving write creates a new backup.

**Production impact:** At current growth rate, the backup directory will exhaust a typical SSD partition. Directory listing above 10,000 files degrades on Windows NTFS.

**Proposed fix:** After writing the backup, delete all but the 5 most recent for that stem:
```python
# After shutil.copy2(...)
existing = sorted(backup_dir.glob(f"{path.stem}_*.json"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
for old in existing[5:]:
    old.unlink(missing_ok=True)
```
**Effort:** 30 minutes. **Priority:** P0.

---

### VF-2 — `observability_events.jsonl` appends forever with no rotation

**Severity:** HIGH  
**File:** `services/observability.py`  
**Lines:** 350–358

```python
def _append_jsonl(self, path: Path, record: dict[str, Any]) -> None:
    if not OBSERVABILITY_ENABLED:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError as exc:
        logger.debug("Observability JSONL write failed: %s", exc)
```

**What it does:** Opens the file in append mode (`"a"`) on every write. No size check. No rotation. No max-line count.

**Search for rotation:** `grep -rn "RotatingFile\|log_rotation\|maxBytes\|backupCount" local_jarvis/` returns zero hits.

**Current state:** `data/observability_events.jsonl` is **59,691 lines / 6.2 MB**. `data/runtime_traces.jsonl` follows the same pattern.

**Same pattern in `brain/router.py:447`** (command_history.jsonl, 4,019 lines / 1.8 MB):
```python
with Path(COMMAND_HISTORY_PATH).open("a", encoding="utf-8") as f:
    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

**Production impact:** Both files grow without bound. On a system running 8 hours/day with a moderate command rate, these files will reach 100 MB within months. They are loaded into memory as part of `deque(maxlen=...)` in-process, but the on-disk file is never truncated.

**Proposed fix:** Replace the `open("a")` pattern with Python's `logging.handlers.RotatingFileHandler` (max 10 MB, 3 rotations), or add a size check before each append.  
**Effort:** 4 hours. **Priority:** P0.

---

### VF-3 — Memory expired entries never deleted from disk

**Severity:** HIGH  
**File:** `memory/store.py`  
**Lines:** 166–187

```python
def list_visible(self, *, category: str | None = None, limit: int = 50) -> list[MemoryEntry]:
    out: list[MemoryEntry] = []
    now = datetime.now(timezone.utc)
    for row in self._load().get("entries", []):
        if row.get("hidden"):
            continue
        expires_at = str(row.get("expires_at", "") or "").strip()
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at) <= now:
                    continue          # <-- skips expired, but never deletes
            except ValueError:
                pass
        ...
```

**What it does:** Expired entries are silently skipped on every read. They remain in the JSON file. They are parsed on every `_load()` call.

**`forget()` also does not delete (lines 146–164):**
```python
def forget(self, query: str) -> int:
    ...
    for row in data.get("entries", []):
        if ...:
            row["hidden"] = True    # soft-delete only
            count += 1
    if count:
        self._save(data)
    return count
```

Hidden entries remain in the file with `"hidden": True`.

**Search for vacuum:** `grep -rn "def vacuum\|def purge\|def cleanup\|def expire" memory/` returns **zero results**. There is no function that removes expired or hidden entries from `memory_store.json`.

**Production impact:** Every `remember(..., ttl_seconds=N)` call adds an entry that will never be physically removed. Every `forget()` call marks an entry hidden but keeps it on disk. The JSON file grows unbounded; all entries are parsed on every `_load()` call.

**Proposed fix:** Add a `vacuum()` method that rewrites the file with only non-hidden, non-expired entries, and call it on startup.  
**Effort:** 2 hours. **Priority:** P1.

---

### VF-4 — Microphone reconnect loop spins at full CPU with no backoff

**Severity:** HIGH  
**File:** `voice/voice_loop.py`  
**Lines:** 183–203

```python
while app._running and state.running and state.voice_enabled:
    wav_path: Path | None = None
    begin_voice_command(source="push_to_talk")
    t_record = time.perf_counter()
    try:
        ...
        wav_path = record_fn()          # calls check_microphone_available() first
        ...
    except MicrophoneError as exc:
        app.console.print(f"[red]Microphone error:[/] {exc}")
        try:
            from ui.overlay_app import notify_overlay_error
            notify_overlay_error(str(exc))
        except Exception:
            pass
        finish_and_log()
        continue                        # immediately retries — no sleep
```

**What happens when the microphone is disconnected:** `record_fn()` calls `check_microphone_available()` (`microphone.py:57`), which raises `MicrophoneError`. The handler prints an error and calls `continue`. There is no `time.sleep()` anywhere in this path. The loop immediately tries again.

**Verified:** `grep -n "time.sleep\|backoff" voice/voice_loop.py` returns **zero hits**.

**Production impact:** When a USB microphone is disconnected, the push-to-talk loop enters a CPU-bound spin: `check_microphone_available()` → `MicrophoneError` → `continue` → repeat, potentially thousands of times per second. This saturates one CPU core and floods the console with error messages until the microphone is reconnected or the process is killed.

**Proposed fix:** Add `time.sleep(2.0)` (or exponential backoff) inside the `MicrophoneError` handler before `continue`.  
**Effort:** 15 minutes. **Priority:** P1.

---

### VF-5 — Voice acceptance has four hardcoded-True test cases

**Severity:** HIGH  
**File:** `reliability/voice_health.py`  
**Lines:** 70–99

```python
def _streaming_policy() -> tuple[bool, str]:
    from voice.streaming_stt.session_policy import get_streaming_disable_reason, is_streaming_stt_enabled_for_session
    return True, f"enabled={is_streaming_stt_enabled_for_session()} ..."  # line 73: always True

def _tts_backend() -> tuple[bool, str]:
    from voice.audio_status import get_audio_status
    audio = get_audio_status()
    return True, f"backend={audio.selected_verified_audio_backend or 'unverified'}"  # line 79: always True

score.cases.extend([
    run_case("voice_config_present", _cfg_ok),
    run_case("streaming_policy_readable", _streaming_policy),      # always PASS
    run_case("tts_backend_reported", _tts_backend),                # always PASS
    run_case("interruption_hooks", _interruption_hooks),
    run_case("stop_listening_intent", _wake_phrase_registered),
    run_case("long_sentence_normalization", lambda: (True, "spoken_normalization module available")),  # line 98: always PASS
    run_case("paragraph_transcription_path", lambda: (True, "streaming buffer policy available")),    # line 99: always PASS
])
```

**Specific problems:**

| Case | Code | Why it always passes |
|------|------|---------------------|
| `streaming_policy_readable` | `return True, f"enabled=..."` | Hardcoded `True`; the value of `is_streaming_stt_enabled_for_session()` is logged but never checked |
| `tts_backend_reported` | `return True, f"backend=..."` | Hardcoded `True`; if backend is `"unverified"`, still passes |
| `long_sentence_normalization` | `lambda: (True, "spoken_normalization module available")` | Never calls the normalization module |
| `paragraph_transcription_path` | `lambda: (True, "streaming buffer policy available")` | Never tests the STT buffer |

**Effect on scoring:** `hardening_core.py:40–43` computes the score as `pass_rate * 0.85 + (10 if pass_rate >= 90 else 0)`. With 4 of 7 cases hardcoded to pass, the voice score is inflated regardless of whether voice actually works.

**Production impact:** The product readiness report (`product_readiness.py:20`) reports `Voice: 65%`. This number is not derived from actual voice behavior; it partly reflects guaranteed-pass test cases.

**Proposed fix:** Replace each hardcoded True with a real behavioral check. For example, `long_sentence_normalization` should call `spoken_normalization.normalize("Hello world, this is a long sentence.")` and assert it returns a non-empty string.  
**Effort:** 2 hours. **Priority:** P1.

---

### VF-6 — Memory acceptance has four hardcoded-True or tautological cases

**Severity:** MEDIUM  
**File:** `reliability/memory_health.py`  
**Lines:** 93–115

```python
def _semantic() -> tuple[bool, str]:
    hits = store.semantic_search(tag, limit=3)
    return len(hits) >= 0, f"semantic_hits={len(hits)}"  # line 93: len() >= 0 is always True

def _update() -> tuple[bool, str]:
    store.remember(...)
    return True, "updated"                               # line 97: hardcoded

def _forget() -> tuple[bool, str]:
    n = store.forget(tag)
    return n >= 0, f"hidden={n}"                         # line 101: int >= 0 is always True

def _dup_detect() -> tuple[bool, str]:
    d = _diagnostics()
    return True, f"duplicates={d['duplicates']}"         # line 105: hardcoded

run_case("ranking_diagnostics", lambda: (True, show_memory_ranking_diagnostics()[:120]))  # line 115
```

**Specific problems:**

| Case | Why it always passes |
|------|---------------------|
| `semantic_retrieve` | `len(list) >= 0` is a Python invariant — a list length is never negative; returns True even if `semantic_search` returns empty |
| `update` | Calls `remember()` but returns `True` unconditionally — does not check the return value |
| `forget` | `forget()` returns `int(count_hidden)` which is `>= 0` by definition, even if 0 entries were hidden (i.e., the tag wasn't found) |
| `duplicate_detection` | Always True; the diagnostic value is logged but the test never fails |
| `ranking_diagnostics` | `lambda: (True, ...)` — hardcoded |

**Production impact:** The memory acceptance score has 5 of 7 cases that cannot fail due to being tautologies or hardcoded. The `forget` case in particular passes even when the entry being forgotten is not found.

**Proposed fix:** `_semantic` should assert `len(hits) > 0`; `_forget` should assert `n > 0`; `_update` should check that the updated entry is retrievable.  
**Effort:** 1 hour. **Priority:** P1.

---

### VF-7 — Integrations acceptance validates mock mode, not production readiness

**Severity:** HIGH  
**File:** `reliability/integrations_health.py`  
**Lines:** 7, 42–58

```python
_MOCK_MARKER = "MOCK MODE"

def _inbox() -> tuple[bool, str]:
    body = summarize_my_inbox(20)
    return _MOCK_MARKER in body and "urgent" in body.lower(), "mock read-only"  # passes when mock

def _urgent() -> tuple[bool, str]:
    body = show_urgent_emails()
    return _MOCK_MARKER in body, body[:80]   # passes when mock

def _calendar() -> tuple[bool, str]:
    body = summarize_my_calendar()
    return _MOCK_MARKER in body and "schedule" in body.lower(), "mock read-only"  # passes when mock

def _conflicts() -> tuple[bool, str]:
    from providers.daily_summary_provider import get_calendar_provider
    body = get_calendar_provider().find_conflicts().format("Conflicts")
    return _MOCK_MARKER in body, "conflicts mock"   # passes when mock
```

**What this means:** All four integration acceptance cases return `True` specifically when the system is in mock mode (i.e., `"MOCK MODE"` appears in the output). If a real email provider were connected, its output would not contain `"MOCK MODE"`, and all four cases would **fail**.

**Consequence:** The integrations acceptance suite is a test that the mock is active. It cannot be passed by a working integration. The product readiness report shows "Integrations: 12%" which the code acknowledges, but the acceptance framework validates the wrong thing — mock activity rather than real connectivity.

**Production impact:** A developer wiring a real Gmail adapter would see the integrations acceptance score drop from its current level. The test incentivizes keeping the mock.

**Proposed fix:** Cases should pass when the system is live **or** skip when credentials are absent. Replace `return _MOCK_MARKER in body` with: live credentials → test real response; no credentials → `return None, "SKIP"`.  
**Effort:** 4 hours. **Priority:** P1.

---

### VF-8 — `atomic_write_json` is called 45 times; backup accumulation is proportional

**Severity:** MEDIUM (supporting evidence for VF-1)  
**File:** Multiple callers

The 45 call sites include files that are written on every significant state change:

| Module | When written | Example path |
|--------|-------------|-------------|
| `assistant/hypothesis_engine.py` | On every hypothesis update | `data/hypotheses.json` → 118 backups |
| `assistant/verification_plans.py` | On every plan step | `data/verification_plans.json` → 75 backups |
| `assistant/investigation_scheduler.py` | On scheduling events | `data/investigation_scheduler.json` |
| `assistant/notifications.py` | On each notification | `data/notifications.json` |
| `core/session.py` | On session save | `data/session_state.json` |

With 22 distinct backing files and no per-file retention limit, the backup directory count is `22 × (writes per file)` with no upper bound.

---

### VF-9 — `_streaming_policy` and `_tts_backend` return True unconditionally even on degraded state

**Severity:** MEDIUM (supporting evidence for VF-5)  
**File:** `reliability/voice_health.py`  
**Lines:** 70–79

```python
def _streaming_policy() -> tuple[bool, str]:
    from voice.streaming_stt.session_policy import get_streaming_disable_reason, is_streaming_stt_enabled_for_session
    return True, f"enabled={is_streaming_stt_enabled_for_session()} reason={get_streaming_disable_reason() or 'none'}"
```

`is_streaming_stt_enabled_for_session()` could return `False` (streaming disabled due to error). The detail string would show `enabled=False reason=wake_stream_error:...`. The test still passes. A developer reading the score would not know streaming is broken.

```python
def _tts_backend() -> tuple[bool, str]:
    from voice.audio_status import get_audio_status
    audio = get_audio_status()
    return True, f"backend={audio.selected_verified_audio_backend or audio.last_provider or 'unverified'}"
```

If the TTS backend is `"unverified"` (which means no confirmed audio output path exists), the test still passes. The string `"unverified"` is logged but the acceptance case is `PASS`.

---

### VF-10 — `telegram_client.py` is a 2-line file with no implementation

**Severity:** LOW  
**File:** `integrations/telegram_client.py`

```python
"""Telegram notifications — optional integration."""
```

That is the entire file. It contains a module docstring and nothing else. Any code that attempts to import a function from this module will get `ImportError`. Any code that checks `if telegram_client` as a module will not detect that it is empty.

**Production impact:** If notifications (e.g., TTS failure alerts) are ever routed here, they will silently fail at import time.

---

## Summary Table

| ID | File | Lines | Severity | Status |
|----|------|-------|----------|--------|
| VF-1 | `core/persistent_json.py` | 28–34 | CRITICAL | Proven: 2,522 backups, 66 MB, zero cleanup logic |
| VF-2 | `services/observability.py` | 350–358 | HIGH | Proven: append-only, 59,691 lines, no rotation |
| VF-2b | `brain/router.py` | 447–450 | HIGH | Proven: append-only, 4,019 lines, no rotation |
| VF-3 | `memory/store.py` | 166–187 | HIGH | Proven: expired entries skipped on read, never deleted |
| VF-4 | `voice/voice_loop.py` | 194–203 | HIGH | Proven: no sleep on MicrophoneError, tight retry loop |
| VF-5 | `reliability/voice_health.py` | 70–99 | HIGH | Proven: 4 of 7 acceptance cases cannot fail |
| VF-6 | `reliability/memory_health.py` | 93–115 | MEDIUM | Proven: 5 of 7 acceptance cases are tautologies |
| VF-7 | `reliability/integrations_health.py` | 42–58 | HIGH | Proven: all 4 cases pass specifically when mock is active |
| VF-8 | 45 call sites | — | MEDIUM | Proven: no per-file backup retention limit |
| VF-9 | `reliability/voice_health.py` | 70–79 | MEDIUM | Proven: degraded state logged but acceptance still passes |
| VF-10 | `integrations/telegram_client.py` | 1 | LOW | Proven: file contains only a docstring |

---

## Retracted Claims from `master_audit.md`

| Original claim | Why retracted |
|----------------|--------------|
| "Registry silently drops actions with import errors" | `actions/registry.py:1–562` are all module-level imports. An import error crashes startup completely. No silent dropping occurs. |
| "TTS failure is silent to the user" | `voice/tts.py:673–674` explicitly prints `[TTS ERROR]` to stdout and calls `_overlay_tts_warning()` → `notify_overlay_error()` on async failure. Sync failures call `_overlay_tts_warning()` at lines 331, 440, 449. |
| "Microphone disconnect kills voice permanently" | `voice/voice_loop.py:203` calls `continue`, keeping the loop alive. The real issue is the absence of backoff (VF-4), not permanent termination. |

---

*End of Audit Verification — 2026-05-29*
