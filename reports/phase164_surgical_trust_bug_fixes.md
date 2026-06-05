# Phase 164 — Surgical Trust Bug Fixes

Surgical fixes for four confirmed root causes from Phase 164 diagnostic reports. No new systems, no broad refactors.

## BUG A — Quality boost equals threshold (EMA leakage)

**Root cause:** `quality_confidence_boost("source_backed")` was `2.0`, equal to `LOCAL_CONFIDENCE_THRESHOLD`. A source-backed concept (EMA) could match with **zero alias hits** via quality boost alone. Tie-breaking then favored EMA over unrelated prompts.

**Files:** `jarvis_desktop/atlas_knowledge/quality.py`, `jarvis_desktop/atlas_knowledge/engine.py`

**Fix:**
1. Reduced `source_backed` boost to `1.9` (below threshold).
2. Require `len(hits) >= 1` before accepting any local concept match (threshold pass, cache, or low-confidence partial).
3. Reject boost-only matches with `concept_id=None` and an explicit unknown.

**Before:**
```
match_text("add event bus tracing") → concept_id=ema, score=2.0, hits=[]
plan_change(...) → domain_knowledge.concept_id=ema
```

**After:**
```
match_text("add event bus tracing") → concept_id=None, score=1.9, hits=[]
plan_change(...) → domain_knowledge without EMA
match_text("add EMA indicator") → concept_id=ema (real alias hit)
```

## BUG B — Trading repo evidence false positives

**Root cause:** `_TRADING_REPO_PATH_SIGNALS` included broad substrings `registry.py`, `signal.py`, and `strategy`. Home Assistant (`entity_registry.py`, `helpers/signal.py`) and Celery (`worker/strategy.py`) falsely set `_repo_has_trading_evidence(ctx)=True`, bypassing the P158 trading guardrail.

**File:** `jarvis_desktop/planning_engine.py`

**Fix:** Removed broad tokens. Replaced with trading-specific path signals: `trading/`, `trading_strategy`, `trading/strategy`, `backtest`, `backtesting`, `trade_signal`, `market_signal`, `order_book`, `broker`, `portfolio`, `ohlcv`, `candle`, `position_sizing`, `slippage`, `execution_model`, `indicators/`, `paper_trading`, `live_trade`.

**Before:**
```
_repo_has_trading_evidence(HA with device_registry.py) → True
```

**After:**
```
_repo_has_trading_evidence(HA / Django / Celery contexts) → False
_repo_has_trading_evidence(trading/strategy.py, indicators/ema.py) → True
```

## BUG C — Copilot and legacy routes bypass trust fields

**Root cause:**
- `bug_investigation` returned `ok=true` + `mock=true` when no paths matched.
- Legacy `impact()` with no scan used a mock-style error without clear deprecation.
- EMA leakage in planning (BUG A) could surface via any route using `classify_request`.

**File:** `jarvis_desktop/api.py`

**Fix:**
1. `bug_investigation`: unmatched input → `ok=false`, `status=insufficient_evidence`, `mock=false`, message to use modern investigate route.
2. `impact()` with no scan → `ok=false`, `status=legacy_route_unsupported`, message to use modern planning impact.
3. Unresolved target still returns `ok=false` via `_impact_mock` (unchanged from P161).

**Before:**
```json
{"ok": true, "mock": true, "likely_modules": []}
```

**After:**
```json
{"ok": false, "status": "insufficient_evidence", "mock": false, "message": "Use the modern planning route."}
```

## BUG D — Export strips trust metadata

**Root cause:** Send-to-AI prompt builders in `atlas_zero_friction.js` omitted confidence, evidence summary, and graph health warnings.

**File:** `jarvis_desktop/static/atlas_zero_friction.js`

**Fix:** Added `zfTrustBlock(result)` — concise `## Trust & grounding` section with confidence, evidence summary, graph health caveat, and insufficient-evidence status. Wired into Build, Investigation, and Impact export bodies.

**Before:** Export contained implementation steps only.

**After:** Export includes:
```
## Trust & grounding
- Confidence: medium
- Evidence: ...
- Graph health: ...
```

## Tests

**New:** `jarvis_desktop/tests/test_phase164_surgical_trust_fixes.py` (15 cases)

**Validation (all passed):**
```
py -3 -m pytest jarvis_desktop/tests/test_phase158_no_leakage.py -q
py -3 -m pytest jarvis_desktop/tests/test_phase161_grounding.py -q
py -3 -m pytest jarvis_desktop/tests/test_phase163_symbol_evidence.py -q
py -3 -m pytest jarvis_desktop/tests/test_phase164_surgical_trust_fixes.py -q
```

**Result:** 44 passed (combined Phase 158/161/163/164 suites).

## Files changed

| File | Change |
|------|--------|
| `atlas_knowledge/quality.py` | Boost cap 1.9 |
| `atlas_knowledge/engine.py` | Hits-required gate |
| `planning_engine.py` | Trading path signals |
| `api.py` | Legacy/mock success disabled |
| `static/atlas_zero_friction.js` | Trust block in exports |
| `tests/test_phase164_surgical_trust_fixes.py` | New coverage |
| `reports/phase164_surgical_trust_bug_fixes.md` | This report |
