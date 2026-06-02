# Phase 78 — Tool Registry v1 Implementation Plan (no code)
**Date:** 2026-05-29
**Goal:** Stand up the LLM-first **Tool Registry** as an *additive* layer over the existing 487 handlers — typed, safety-classed, centrally enforced — without breaking a single existing intent, without any mock success, and with LLM routing behind an off-by-default flag.
**Reads:** `reports/llm_first_architecture.md`, `reports/phase73_100_roadmap.md`, `reports/jarvis_codebase_audit_phase73_100.md`.

> Phase 78 builds the registry + adapters + the first 40 tools + parity tests + a shadow path. It does **not** change production routing (that is Phase 79). The keyword classifier and `ActionRegistry` remain authoritative.

---

## Hard-constraint compliance (how each is met)
- **No big-bang rewrite** — tools are *adapters* over existing handlers; `ActionRegistry` is untouched and stays the executor of record.
- **No breaking existing intents** — production text→intent→handler path is unchanged; the registry is additive and (for routing) flag-gated off.
- **No mock success** — the catalog is *forbidden* from mapping any tool to a known mock-success handler (legacy `phase62_browser_actions` excluded); web/research capability is provided **only** via the Phase 71/72/74 no-mock `tooluse`/`autonomy` path. The adapter never upgrades a non-SUCCESS result to SUCCESS.
- **Central safety_class enforcement** — the registry refuses to register FORBIDDEN tools, never exposes them to selection, and the adapter refuses to invoke anything above the allowed class for the turn.
- **Forbidden actions stay forbidden** — payments/orders/bookings/logins/submits/downloads/deletes/sends are not in the catalog and are rejected centrally (reuse `tooluse.contracts.scan_forbidden` + `autonomy.capabilities`).
- **LLM routing behind a flag** — `LLM_TOOL_ROUTER_ENABLED` (default **false**). Phase 78 only scaffolds the shadow; it does not route.
- **Keyword classifier remains as fallback/cache** — unchanged; it stays the production front door this phase.

---

## 1. Final ToolSpec schema (field-by-field)

A `ToolSpec` is a frozen, declarative record. Fields:

| Field | Type | Required | Meaning / rule |
|-------|------|----------|----------------|
| `name` | str | yes | Namespaced, lowercase, `^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$` (e.g. `memory.recall`). Unique. |
| `version` | int | yes | Starts at 1; bump on schema/behavior change (enables A/B + rollback). |
| `description` | str | yes | Natural-language, written **for the LLM** — this is what tool-retrieval embeds/ranks on. Must state what it does and when to use it. |
| `input_schema` | dict (JSON-Schema subset) | yes | Typed params: `properties`, `required`, types, enums. v1 validation = required-keys + primitive-type checks (jsonschema optional later). |
| `output_schema` | dict | yes | Declared result shape (keys the tool guarantees in `data`). Enables structured synthesis + verification. |
| `safety_class` | enum | yes | `READ_ONLY` \| `REVERSIBLE` \| `IRREVERSIBLE_FORBIDDEN`. FORBIDDEN tools may not be registered. |
| `side_effects` | enum | yes | `none` \| `local_write` (memory/notes/report — reversible, ungated) \| `local_launch` (open allowlisted app/site) \| `external_read` \| `external_reversible` \| `external_irreversible` (forbidden). |
| `idempotent` | bool | yes | Affects retry/recovery safety. |
| `requires_approval` | bool | derived | Derived from `safety_class`: READ_ONLY → false; REVERSIBLE → true (Phase 95 gate); FORBIDDEN → n/a (never runs). |
| `verification` | enum/list | yes | Declared post-condition contract: `result_success` \| `non_empty_summary` \| `provider_real` \| `schema_valid` \| `cross_source`. Drives "did it actually work". |
| `maps_to_intent` | str | yes (v1) | The existing `Intent.value` this adapter dispatches to. (In later phases tools may have native handlers.) |
| `arg_map` | dict[str,str] | no | Tool-arg name → `CommandRequest.params` key. |
| `raw_text_template` | str | no | Template to synthesize `raw_text` for handlers that parse it (e.g. `"find function {name}"`). |
| `auth` | enum | yes | `none` \| `connector_token` (keychain-backed; Phase 88+). |
| `cost_hint` | enum | yes | `free` \| `cheap` \| `network` \| `expensive` — for planner budgeting. |
| `latency_hint` | enum | yes | `instant` \| `fast` \| `slow`. |
| `enabled` | bool | yes | Allows disabling a tool without removing it. |
| `tags` | tuple[str] | no | For retrieval/grouping (e.g. `memory`, `research`, `trading`). |

**Invariants enforced at registration (central):**
1. `safety_class != IRREVERSIBLE_FORBIDDEN` (else reject).
2. `side_effects != external_irreversible` (else reject).
3. `maps_to_intent` is in `IMPLEMENTED_INTENTS` and has a handler in `ActionRegistry` (else reject — fail closed).
4. `maps_to_intent` is **not** in the mock-success denylist (legacy `find_information_about`/`extract_key_facts_from_this_page` legacy mock path excluded).
5. `name` unique; schemas well-formed.

---

## 2. Adapter strategy (existing handler → tool)

The adapter is the bridge; `ActionRegistry` stays the executor.

**Invocation flow `ToolRegistry.invoke(tool_name, args, *, allowed_classes, approved=False)`:**
1. **Lookup + enabled check.** Unknown/disabled tool → typed `ToolResult(status=error, reason="unknown_tool")`.
2. **Safety gate (central).** If `tool.safety_class` not in `allowed_classes` for this turn, or REVERSIBLE and not `approved` → `ToolResult(status=blocked, reason="requires_approval"/"forbidden")`. FORBIDDEN can't reach here (never registered).
3. **Schema validation.** Validate `args` vs `input_schema`; on failure → `ToolResult(status=error, reason="invalid_args", detail=...)` (never execute on bad args).
4. **Build request.** Map args via `arg_map` into `CommandRequest.params`; synthesize `raw_text` via `raw_text_template` (or pass-through); `confirmed = approved`.
5. **Execute via ActionRegistry.** `result = ActionRegistry().execute(request)` — same code path as today (so behavior parity + the Phase 3.1 agent metadata/health gating already apply).
6. **Fidelity-preserving map.** Translate `CommandResult` → `ToolResult` **without upgrading status**: SUCCESS→success, FAILED→failed, BLOCKED→blocked, CONFIRMATION_REQUIRED→needs_approval, NOT_IMPLEMENTED→error. Carry `summary`, `data`, `agent_id`. **A mock/unavailable underlying result stays non-success.**
7. **Verification.** Apply the tool's declared `verification` to the result/`data`; attach `verified: bool` + reason. (READ_ONLY status tools: `result_success`; research tools: `provider_real`/`non_empty_summary` via the tooluse/autonomy result data.)
8. **Audit.** Record tool name, args (redacted), result status, verified, latency to the existing audit stream.

**Web/research tools do NOT use legacy mock browser.** `web.*`/`autonomous.*` tools map to the Phase 71/72/74 intents (`run_tool_task`, `run_autonomous_task`, …) whose execution is the isolated no-mock provider. The legacy `search_web_for`/`find_information_about` handlers are **excluded** from the catalog (denylist).

---

## 3. First 40 tools — ranked by usefulness × safety

Ordering: safest + highest-daily-value first. (R/O = READ_ONLY, ungated; REV = REVERSIBLE, approval-gated; lw = local_write, ll = local_launch, er = external_read.)

| # | Tool | maps_to_intent | safety_class / side_effect | verification | Why |
|---|------|----------------|----------------------------|--------------|-----|
| 1 | `assistant.capabilities` | show_capabilities | R/O none | result_success | discoverability core |
| 2 | `assistant.help` | help_for_command | R/O none | result_success | onboarding |
| 3 | `assistant.list_skills` | list_skills | R/O none | result_success | discoverability |
| 4 | `memory.recall` | search_memory | R/O none | non_empty_summary | "remember me" core |
| 5 | `memory.remember` | remember_fact | R/O local_write | result_success | capture facts (reversible/ungated) |
| 6 | `memory.show` | show_memory | R/O none | result_success | inspect memory |
| 7 | `memory.list` | list_memory | R/O none | result_success | inspect memory |
| 8 | `memory.set_preference` | set_preference | R/O local_write | result_success | personalization |
| 9 | `memory.list_preferences` | list_preferences | R/O none | result_success | personalization |
| 10 | `memory.set_alias` | set_alias | R/O local_write | result_success | personalization |
| 11 | `memory.list_aliases` | list_aliases | R/O none | result_success | personalization |
| 12 | `session.summarize` | summarize_session | R/O none | non_empty_summary | continuity |
| 13 | `session.recall` | what_were_we_doing | R/O none | result_success | continuity |
| 14 | `code.find_function` | find_function | R/O none | result_success | dev value |
| 15 | `code.find_class` | find_class | R/O none | result_success | dev value |
| 16 | `code.search_text` | search_code_text | R/O none | result_success | dev value |
| 17 | `code.search_file` | search_project_file_by_name | R/O none | result_success | dev value |
| 18 | `code.inspect_project` | inspect_project | R/O none | non_empty_summary | dev value |
| 19 | `system.status` | show_system_status | R/O none | result_success | health |
| 20 | `system.disk` | show_disk_usage | R/O none | result_success | health |
| 21 | `system.network` | show_network_status | R/O none | result_success | health |
| 22 | `system.health` | show_system_health | R/O none | result_success | health |
| 23 | `system.jarvis_health` | run_jarvis_health_check | R/O none | result_success | health |
| 24 | `system.watchdog_status` | show_watchdog_status | R/O none | result_success | reliability |
| 25 | `system.runtime_status` | show_runtime_status | R/O none | result_success | reliability |
| 26 | `screen.describe` | describe_screen | R/O external_read | non_empty_summary | desktop value |
| 27 | `screen.read_text` | read_screen_text | R/O external_read | non_empty_summary | desktop value |
| 28 | `screen.active_window` | get_active_window | R/O external_read | result_success | desktop value |
| 29 | `screen.list_windows` | list_visible_windows | R/O external_read | result_success | desktop value |
| 30 | `diagnostics.run` | run_diagnostics | R/O none | result_success | support |
| 31 | `diagnostics.explain_last_failure` | explain_last_failure | R/O none | result_success | support |
| 32 | `diagnostics.recent_commands` | show_recent_commands | R/O none | result_success | support |
| 33 | `trading.dashboard_health` | show_dashboard_health | R/O external_read | result_success | domain value |
| 34 | `trading.open_positions` | show_open_positions | R/O external_read | result_success | domain value |
| 35 | `trading.last_errors` | show_last_errors | R/O none | result_success | domain value |
| 36 | `research.plan` | plan_tool_task | R/O none | result_success | preview research (no exec) |
| 37 | `research.run` | run_tool_task | REV external_reversible | provider_real | bounded research (no mock) |
| 38 | `research.show_last` | show_last_tool_run | R/O none | result_success | read-only review |
| 39 | `autonomous.plan` | plan_autonomous_task | R/O none | result_success | preview deep research |
| 40 | `autonomous.research` | run_autonomous_task | REV external_reversible | provider_real | deep multi-source (no mock) |

(Reserve for batch 2: `autonomous.compare`, `autonomous.show_last`, `trading.latest_report`, `trading.search_logs`, and **REVERSIBLE local launches** `app.open`/`web.open`/`browser.open` — deferred so v1 stays parity-clean on approval semantics.)

Counts: **35 READ_ONLY**, **2 REVERSIBLE** (research.run, autonomous.research — already approval-gated via Phase 72/74), **0 FORBIDDEN**.

---

## 4. Exact files to add / change

**Add (new `tools/` package):**
- `tools/__init__.py` — exports.
- `tools/spec.py` — `ToolSpec` dataclass + `SafetyClass`, `SideEffect`, `CostHint`, `LatencyHint` enums + `ToolResult`.
- `tools/registry.py` — `ToolRegistry` (register w/ invariants, get, list, by_tag, `select(query, k)` retrieval stub, central safety gate, schema validation, `invoke(...)`).
- `tools/adapters.py` — `IntentAdapter` (handler→tool invocation, fidelity-preserving result map, verification, audit) + the mock-success **denylist**.
- `tools/catalog.py` — declarative definitions of the 40 `ToolSpec`s + `build_default_tool_registry()`.
- `tools/verification.py` — verifier functions for the declared `verification` enums (reuse `tooluse.verifier` idioms).
- `tools/audit.py` — `data/tool_registry_audit.jsonl` writer (RotatingJSONLWriter; reuse pattern).
- `tests/test_phase78_tool_registry.py` — unit/parity tests.
- `scripts/smoke_phase78_tool_registry.py` — catalog + parity + safety smoke.
- `reports/phase78_tool_registry.md` — completion report (after build).

**Change (minimal, additive):**
- `config.py` — add flags: `TOOL_REGISTRY_ENABLED` (default true; build+validate catalog at startup, no routing change), `LLM_TOOL_ROUTER_ENABLED` (default **false**; Phase 79 shadow).
- `core/runtime_bootstrap.py` — when `TOOL_REGISTRY_ENABLED`, `build_default_tool_registry()` once at startup and log catalog size + any invariant rejections. **No routing change.**
- `core/startup_validation.py` — add `validate_tool_catalog()` (every tool's `maps_to_intent` has a handler; no denylisted mappings; no FORBIDDEN tools). Logs; non-fatal.

**Not touched:** `actions/registry.py`, `brain/intent_classifier.py` (classifier stays authoritative), `brain/router.py` (production path unchanged), `browser/runtime.py`, `actions/phase62_browser_actions.py` (legacy mock — explicitly excluded from catalog, not modified).

---

## 5. Migration path (current intents/handlers → tool catalog)

1. **Build registry additively** (this phase): 40 adapters, parity-tested. `ActionRegistry` unchanged.
2. **Shadow validation:** with `TOOL_REGISTRY_ENABLED`, the catalog is built + validated at startup but not used for routing. Optional: a dev-only "shadow compare" that, for a sample of commands, checks `ToolRegistry.invoke` produces the same status as the direct handler (parity telemetry).
3. **Phase 79 (next):** behind `LLM_TOOL_ROUTER_ENABLED`, the LLM routes *misses* (what the keyword cache doesn't confidently match) to tools; classifier stays as the fast-path cache. Measured on the Phase 75 eval set before default-on.
4. **Phase 84:** migrate remaining valuable handlers into tools; deprecate dead intents; trading → plugin namespace. Net intent surface falls.
- At every step the legacy path remains available; rollback = flip a flag.

---

## 6. Feature flags & rollback

| Flag | Default | Effect | Rollback |
|------|---------|--------|----------|
| `TOOL_REGISTRY_ENABLED` | **true** | Build + validate the catalog at startup (no routing change). | Set false → registry not built; zero behavior change. |
| `LLM_TOOL_ROUTER_ENABLED` | **false** | (Phase 79) LLM routes misses to tools. | Off by default; flip false → classifier-only, exactly today. |
| `TOOL_REGISTRY_SHADOW_COMPARE` | **false** | Dev-only parity telemetry (no user effect). | Off by default. |

Rollback is always "flip the flag": production behavior with both routing flags off is byte-for-byte the current system. Tool `version` + `enabled` allow per-tool rollback without redeploy.

---

## 7. Test plan (deterministic; `tests/test_phase78_tool_registry.py`)

- **Catalog integrity:** all 40 tools register; every `maps_to_intent` ∈ `IMPLEMENTED_INTENTS` and has a handler; names unique; schemas well-formed.
- **Safety invariants:** registering a FORBIDDEN tool is rejected; registering a tool mapped to a denylisted (mock-success) intent is rejected; `external_irreversible` rejected.
- **Central safety gate:** invoking a REVERSIBLE tool without `approved=True` → `needs_approval`/`blocked` (no execution); READ_ONLY runs without approval.
- **Schema validation:** invalid/missing args → `invalid_args`, handler never called (spy).
- **Fidelity (no fake success):** a handler returning FAILED/BLOCKED/NOT_IMPLEMENTED maps to non-success ToolResult; assert no upgrade to success. A stubbed mock/unavailable result stays non-success.
- **Parity:** for ~10 READ_ONLY tools, `ToolRegistry.invoke(tool, args)` yields the same status + core summary as the direct `ActionRegistry.execute(intent)` (proves additive, non-breaking).
- **Web no-mock routing:** `research.run`/`autonomous.research` map to the Phase 72/74 intents (not legacy mock handlers); with an injected fake provider that's `is_real()=False`, the tool result is BLOCKED, never success.
- **Verification attach:** READ_ONLY status tool → `verified` reflects `result_success`; research tool → `verified` reflects `provider_real`.
- **Audit:** invoking a tool writes a `tool_registry_audit.jsonl` record with status + verified.
- **Startup validation:** `validate_tool_catalog()` returns empty errors on the real catalog.
- **No-regression:** existing `test_phase71/72`, `test_router`, `test_intent_registry_consistency`, `test_sprint3_agents` still pass (classifier/router unchanged).

(Use injected fakes for provider-backed tools; no live network in unit tests.)

## 8. Smoke plan (`scripts/smoke_phase78_tool_registry.py`)
- **Catalog smoke:** build the registry; print tool count, per-safety-class counts; assert 0 FORBIDDEN, 0 denylisted mappings → SMOKE PASS.
- **Parity smoke:** invoke 5 READ_ONLY tools (e.g. `assistant.capabilities`, `system.health`, `code.find_function`) and the equivalent direct intents; assert matching status.
- **Safety smoke:** attempt to register a FORBIDDEN/denylisted tool → assert rejection; attempt REVERSIBLE invoke without approval → assert blocked.
- **No-mock smoke:** `research.run` via fake `is_real()=False` provider → assert BLOCKED, never success.
- Honest exit codes; deterministic (no live web required).

## 9. Definition of done
- `ToolSpec` + `ToolRegistry` + adapters implemented; **40 tools registered** with the invariants enforced centrally.
- Production routing **unchanged**; both router flags off by default; classifier remains authoritative.
- All Phase 78 tests pass; catalog + parity + safety + no-mock smokes pass.
- Existing Phase 71/72 + router + intent-consistency tests still green.
- No FORBIDDEN tool registrable; denylisted (mock) handlers excluded; no result-status upgrades.
- `reports/phase78_tool_registry.md` written; branch contains only relevant changes; git status reported; commit created on the phase branch.

## 10. Risks & mitigations
| Risk | Mitigation |
|------|-----------|
| Adapter subtly changes behavior vs direct handler | Parity tests on 10+ tools; shadow-compare telemetry flag |
| A mock-success handler sneaks into the catalog | Central denylist + registration invariant + a test asserting it's rejected |
| Schema validation rejects valid real args | Keep v1 validation lightweight (required + type); expand cautiously |
| Result-status upgrade hides failure | Explicit fidelity map with a test that FAILED/BLOCKED never become success |
| Startup cost grows (catalog build) | Build is cheap (40 specs); lazy-embed tool descriptions only when retrieval is enabled (Phase 79) |
| REVERSIBLE tools executed without approval | Central gate defaults to deny for REVERSIBLE unless `approved=True`; test enforces |
| Flag drift turns LLM routing on prematurely | `LLM_TOOL_ROUTER_ENABLED` default false; Phase 79 owns turning it on behind evals |
| Scope creep beyond 40 tools | Hard cap this phase at the listed 40; batch 2 is a separate change |

*End of plan — no code written.*
