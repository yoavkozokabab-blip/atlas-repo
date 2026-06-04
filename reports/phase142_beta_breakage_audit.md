# Phase 142 — Private Beta Breakage Audit

**Scenario:** Syron (formerly Atlas) ships to 20 external developers tomorrow.
This is a *prediction* of support tickets — no code, no features, no fixes. It
ranks where real users will hit friction, based on the actual current state of
the codebase.

**Probability** = likelihood ≥1 of 20 beta users hits it. **Severity** = impact
on that user (Critical = can't use the product; High = core flow broken; Medium =
confusing/slow but recoverable; Low = cosmetic).

## Headline risk

The single biggest theme is **packaging & cross-platform**: Syron is a
Windows-first, stdlib-only desktop app, but the only `requirements.txt` is the
full J.A.R.V.I.S monorepo (PySide6, faster-whisper, onnxruntime, sounddevice,
tesseract, playwright). A naive install will fail for reasons unrelated to the
product. Expect **installation tickets to dominate week one.**

---

## Top 20 likely support tickets

| # | Category | Ticket (what the user says) | Probability | Severity | Mitigation |
|---:|---|---|---|---|---|
| 1 | Install | "`pip install -r requirements.txt` fails building onnxruntime / faster-whisper / PySide6 / PyAudio." | **Very high** | **Critical** | Ship a desktop-only requirement set (the app needs only stdlib + optional `psutil`/`fastapi`); document `py -3 run_jarvis_desktop.py` needs no pip install at all. |
| 2 | Install | "App won't start — syntax errors / 'feature not supported'." (Python < 3.10) | High | Critical | `install_support.py` already gates 3.10+; surface that check at launch and put "Python 3.10+" at the top of the README. |
| 3 | Install | "`py -3` is not recognized" (macOS/Linux have no `py` launcher). | High (non-Windows) | High | Document `python3 run_jarvis_desktop.py`; provide a cross-platform launch note. |
| 4 | Install | "Windows SmartScreen / antivirus blocked the installer." (unsigned `jarvis.iss` build) | High (Windows) | High | Code-sign the installer; document "More info → Run anyway" and checksums. |
| 5 | Install | "There's no Mac/Linux installer." (only Inno Setup `.iss`) | High (non-Windows) | High | Document the manual `python3` run path clearly as the supported non-Windows route. |
| 6 | Install | "Port 8777 is already in use / blank page." | Medium | Medium | `--port` flag exists; document it and consider an auto-fallback port in the launcher. |
| 7 | Scanning | "I pointed it at my repo and it scanned 100k files / never finished." (scanned `node_modules`, `.venv`, `.git`, vendored repos) | **Very high** | High | Strong default ignores + a visible scope picker; the self-scan (2,400s) is the canonical example of this. |
| 8 | Scanning | "Huge monorepo is extremely slow or shows 0 modules." (massive-mode degenerate build) | Medium-high | High | Phase 140 retry + degraded-scan warning already added; document expected times by repo size. |
| 9 | Scanning | "Mixed-language repo only shows part of my code." (Go/Rust/Java/C# not graphed; Python/TS only) | Medium-high | Medium | Document supported languages explicitly; the zero-edge taxonomy surfaces unsupported layouts. |
| 10 | Scanning | "Impact says 'no dependency edges' / results look empty." (edge-sparse repos: scripts, algorithms, Rust/Go) | Medium | Medium | Phase 140 `zero_edge_graph` warning explains it; make the message non-alarming and actionable. |
| 11 | Scanning | "Scan errored / hung on a symlinked or junctioned repo." | Medium | Medium | Verify symlink-cycle handling; document; cap traversal depth. |
| 12 | Scanning | "Permission denied / path errors on protected folders or OneDrive-synced repos." | Medium | Medium | Catch and report per-file errors (already counted); surface a clear summary instead of failing the scan. |
| 13 | Performance | "My machine ran out of memory / swapped during a big scan." | Medium | High | Phase 140 `memory_pressure` detection exists in the harness; expose a RAM guidance note + scope guidance for >10k-file repos. |
| 14 | Performance | "Scan looks frozen for minutes, so I killed it." (HA-scale ≈ 10 min) | High | Medium | Progress stages exist (`scan_job`); ensure the UI shows live progress + an ETA, and that cancel is obvious. |
| 15 | Confusion | "It won't write or fix my code." (users expect an autonomous coding agent) | **Very high** | Medium | The "planning only — does not generate code" disclaimers exist; make this the first thing onboarding says, and frame the value (grounded context for *your* AI). |
| 16 | Confusion | "What is a 'compact packet' / 'blast radius' / 'fan-in' / 'subsystem'?" | Medium-high | Medium | Add plain-language tooltips/glossary; lead with outcomes ("files that break if you change X") over jargon. |
| 17 | Confusion | "I exported context — now what do I do with it?" | Medium | Medium | Export screen should state: paste into Claude/Codex/Cursor; show a one-line example. |
| 18 | Confusion | "Scores/percentages — what do they mean and are they trustworthy?" | Medium | Low-Medium | Clarify that scores are heuristic/structural, not guarantees (consistent with existing uncertainty framing). |
| 19 | Reliability | "Results were incomplete but it didn't tell me clearly." (partial/degraded graph) | Medium | Medium | Phase 140 attaches `health_warnings`; ensure the UI renders them prominently, not just in the payload. |
| 20 | Reliability | "It scanned but the whole app is empty." (persistent 0-module after retry, or scan_crash) | Low-medium (post-140) | High | Phase 140 retries the transient case; for persistent failures show a clear error + point to the diagnostics endpoint and `launcher.log`. |

---

## Per-category summary

### 1. Installation — *highest ticket volume*
- **Python version:** 3.10+ enforced (`install_support.py`); pre-3.10 users blocked. Document loudly.
- **Missing dependencies:** the product is stdlib-only, but the repo-level `requirements.txt` pulls heavy native packages — the #1 self-inflicted install failure.
- **Windows:** unsigned installer → SmartScreen/AV friction; otherwise the happy path.
- **macOS/Linux:** no installer and `py -3` doesn't exist there → must document the `python3` route; biggest non-Windows gap.

### 2. Repository scanning
Giant repos and monorepos are handled by massive mode but are slow and
occasionally degenerate; the dominant real-world failure is **scanning the wrong
thing** (vendored dirs, `node_modules`, `.git`). Symlink and mixed-language repos
are secondary risks. Non-Python/TS code yields zero-edge graphs.

### 3. Performance
Scan duration is the felt pain: HA-scale ≈ 10 min, a self/over-broad scan can hit
the 40-min timeout. Memory spikes on very large graphs are plausible. Perceived
"freezing" will cause users to kill scans prematurely.

### 4. User confusion
Two big ones: (a) **expectation mismatch** — users think it writes code; (b)
**terminology** — architecture jargon (packet/blast radius/fan-in) without
plain-language framing. Export-then-what and score-trust are smaller.

### 5. Reliability
Post-Phase-140, partial scans, graph degradation, and the transient 0-module case
are **detected and warned** rather than silent — the remaining risk is whether the
**UI surfaces those warnings** and whether persistent failures give a clear next
step (diagnostics + log).

### 6. Support burden — predicted volume ranking
1. **Installation / cross-platform** (tickets 1–6) — expect the majority of week-one volume.
2. **Scanning the wrong/huge tree** (7, 13, 14) — slow scans and "it never finished".
3. **Expectation mismatch** (15) — "it doesn't write code".
4. **Empty/degraded results** (8, 10, 19, 20).
5. **Terminology & workflow** (16, 17, 18).

---

## Bottom line

Syron's **core analysis is solid** (Phases 136–140); the beta will not break on
intelligence. It will break on **packaging, platform coverage, scan scoping, and
expectation-setting**. Five low-effort, non-feature mitigations would remove most
predicted tickets: (1) a desktop-only dependency story, (2) prominent Python-3.10+
and `python3` (non-Windows) instructions, (3) a signed installer + manual-run docs
for Mac/Linux, (4) aggressive default scan ignores with a visible scope picker, and
(5) onboarding that states up front "Syron maps your code and feeds your AI — it
does not write code." None require new features — only packaging, docs, and copy.
