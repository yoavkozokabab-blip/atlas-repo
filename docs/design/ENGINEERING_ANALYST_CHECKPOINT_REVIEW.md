# Engineering Analyst Checkpoint Review

**Branch:** `design/atlas-premium-experience`
**Base commit:** `43c5d5949da9c14ddb26b777675b32f1e605974d`
**Review date:** 2026-07-13
**Scope:** checkpoint closure only. No product behavior, website, installer, release, persistence, MCP, account, billing, or backend-contract changes.

## Decision Summary

**Verdict: A. APPROVE ENGINEERING ANALYST CHECKPOINT**

The presentation checkpoint is coherent and all required gates are green. The excluded Auth/Onboarding work was preserved byte-for-byte on `feature/auth-onboarding-finish` at `C:\J.A.R.V.I.S\atlas-auth-onboarding`, removed from this checkpoint worktree, and not merged. The clean real-path desktop suite passed with pytest's native exit code `0`; focused UX, JavaScript syntax, duplicate-ID, and diff checks also pass.

## Saved Full-Suite Evidence

Exact output file:

`C:\Users\babi2\AppData\Local\Temp\claude\C--Users-babi2\f98ac9b4-5a85-44a6-90c9-35acd6046b3a\tasks\bea7kud06.output`

Command recorded by the prior session:

```text
py -3 -m pytest atlas_desktop/tests --basetemp=AtlasPytestTemp/gate_full -p no:cacheprovider -q 2>&1 | tail -30
```

Exact executed tally:

| Field | Result |
|---|---:|
| Collected | 1,356 |
| Passed | 1,316 |
| Failed | 3 |
| Errors | 0 |
| Skipped | 37 |
| Duration | 1,553.08 s (25:53) |

`1,356` is the complete summary total: `1,316 + 3 + 37`.

### Exit-code audit

- Background task notification: exit code `0`.
- Pytest result: failed, with three assertion failures.
- Root cause: the shell returned the exit status of `tail`, not pytest. No `pipefail` equivalent or explicit pytest exit capture was used.
- Therefore the exit code `0` does not prove a passing suite.

### Hidden assertion failures

1. `test_phase119_atlas_product_polish.py::TestUIStructure::test_export_why_section_present`
2. `test_phase173b_beta_infrastructure_sprint.py::test_static_index_173b_ux_copy`
3. `test_phase175b_product_completion.py::test_export_cta_primary_after_change_plan`

All three asserted retired labels (`Plan Change` or `Advanced context export`). The frozen UI intentionally uses `Plan` / `Implementation Plan` and `Agent Handoff`. The tests were corrected without changing production code and rerun: **3 passed in 0.13 s**.

No test-ordering signature appeared in that historical run. The three deterministic vocabulary assertions pass independently after correction.

### Genuine post-fix replacement run before isolation

The ACL blocker was removed by using a fresh external temp root, verifying create/write/rename/delete access first, and stopping Atlas, installer/PyInstaller, and concurrent pytest processes before launch. Pytest ran directly in one process from the correct repository path. Its complete output and native exit code were captured separately.

- Collected: **1,370**
- Passed: **1,328**
- Failed: **5**
- Errors: **0**
- Skipped: **37**
- Duration: **1647.78 s (27:27)**
- Pytest exit code: **1**
- Output: `C:\J.A.R.V.I.S\atlas-rc1-clean\reports\design\engineering_analyst_full_suite_authoritative.txt`
- Exit-code record: `C:\J.A.R.V.I.S\atlas-rc1-clean\reports\design\engineering_analyst_full_suite_authoritative.exitcode.txt`

All five failures are deterministic assertions in `atlas_desktop/tests/test_auth_onboarding.py` for the later account/onboarding redesign: the default choice screen, three-action priority order, simplified registration form, logout-to-choice behavior, and guest badge. Those contracts are outside this checkpoint's permitted scope. There were no `WinError 5` failures and no pytest errors.

### Auth work preservation and clean post-isolation run

The six Auth/Onboarding files were copied to the dedicated worktree and verified byte-for-byte by SHA256 before this worktree was cleaned:

- `atlas_desktop/static/index.html`
- `atlas_desktop/static/atlas_accounts.js`
- `atlas_desktop/static/auth.css`
- `atlas_desktop/tests/test_auth_onboarding.py`
- `atlas_desktop/tests/test_phase188_auth_ux.py`
- `atlas_desktop/tests/test_home_state_led_experience.py`

The analyst worktree then restored the recorded pre-onboarding `index.html` checkpoint, removed the two untracked auth-only files, restored `atlas_accounts.js` and the Home test to their checkpoint baselines, and retained only the three approved analyst vocabulary assertions in `test_phase188_auth_ux.py`. The clean full suite ran directly in one process with a verified external temp root:

- Collected: **1,356**
- Passed: **1,319**
- Failed: **0**
- Errors: **0**
- Skipped: **37**
- Duration: **1579.12 s (26:19)**
- Pytest exit code: **0**
- Output: `C:\J.A.R.V.I.S\atlas-rc1-clean\reports\design\engineering_analyst_full_suite_clean.txt`
- Exit-code record: `C:\J.A.R.V.I.S\atlas-rc1-clean\reports\design\engineering_analyst_full_suite_clean.exitcode.txt`

This clean run replaces the red pre-isolation result for checkpoint approval. The earlier five failures were exclusively caused by the excluded, untracked Auth/Onboarding test file.

## Documented Skips

The saved tail output contains the count but not `-rs` reasons. The matching 37-item JUnit inventory from the immediately preceding desktop gate was parsed, and the skip predicates were unchanged by this presentation checkpoint:

| Reason | Count |
|---|---:|
| Home Assistant checkout absent or slow HA tests not enabled | 19 |
| Dev-only `accounts_service` not shipped, including 4 collection skips | 11 |
| Historical phase report not shipped | 5 |
| Manual repository-map smoke artifact not shipped | 1 |
| Phase 185 Claude demo proof script not run | 1 |
| **Total** | **37** |

These are documented environment/artifact skips, not hidden product failures.

## Original 24-File Scope

After the six secondary HTML/JS surfaces were removed, the prior checkpoint candidate contained 24 files before this closure review was created:

| Group | Count | Contents |
|---|---:|---|
| Product source | 12 | 10 presentation files plus `api.py` and `result_reports.py` |
| Tests | 9 | 7 adjusted contracts plus `test_engineering_analyst_ux.py` and `test_phase194_grounded_analysis.py` |
| Design reviews | 3 | Ask review, analyst audit, premium UX review |
| **Total** | **24** | |

That candidate was too broad for the final instruction because it included backend answer behavior and a backend test.

## Reduced Final Scope

The intended production scope is reduced from 12 source files to 10 presentation-only files. Backend behavior is excluded. Three stale legacy test contracts and this closure review are added as verification artifacts, producing a 25-file commit candidate only after a valid full rerun.

### Core presentation source (10)

- `atlas_desktop/static/index.html` - pre-account checkpoint snapshot only
- `atlas_desktop/static/app.js`
- `atlas_desktop/static/atlas_launch_ux.js`
- `atlas_desktop/static/atlas_polish.js`
- `atlas_desktop/static/atlas_workflows.js`
- `atlas_desktop/static/atlas_zero_friction.js`
- `atlas_desktop/static/ask_report.css`
- `atlas_desktop/static/ask_report.js`
- `atlas_desktop/static/investigation.css`
- `atlas_desktop/static/premium.css`

These cover Home, Ask, Impact, Debug, Plan, Handoff, and shared navigation/presentation needed by those screens.

### Focused regression tests (11)

- `atlas_desktop/tests/test_engineering_analyst_ux.py`
- `atlas_desktop/tests/test_hn_launch_ux.py`
- `atlas_desktop/tests/test_phase119_atlas_product_polish.py`
- `atlas_desktop/tests/test_phase122_product_hardening.py`
- `atlas_desktop/tests/test_phase146_beta_polish.py`
- `atlas_desktop/tests/test_phase155_first_user_experience.py`
- `atlas_desktop/tests/test_phase173b_beta_infrastructure_sprint.py`
- `atlas_desktop/tests/test_phase175b_product_completion.py`
- `atlas_desktop/tests/test_phase184_ux_consistency.py`
- `atlas_desktop/tests/test_phase188_auth_ux.py`
- `atlas_desktop/tests/test_phase193b_home_navigation.py`

### Design review documentation (4)

- `docs/design/ASK_CHECKPOINT_REVIEW.md`
- `docs/design/ENGINEERING_ANALYST_AUDIT.md`
- `docs/design/ENGINEERING_ANALYST_CHECKPOINT_REVIEW.md`
- `docs/design/PREMIUM_UX_REVIEW.md`

## Worktree Classification

### Intended core checkpoint

The 25 candidate files listed above. `index.html` is mixed in the live worktree: its core presentation changes are intended, while later account/onboarding hunks are excluded. The reconstructed pre-account snapshot has SHA256:

`72AC0042D16EDE5B5542B449122AB1C7E0A8B2FDAE94159E7781D45EAE7CF883`

### Secondary surfaces excluded

The following have no remaining diff and are not part of the candidate:

- `atlas_desktop/static/admin.html`
- `atlas_desktop/static/billing.js`
- `atlas_desktop/static/about.html`
- `atlas_desktop/static/docs.html`
- `atlas_desktop/static/demo.html`
- `atlas_desktop/static/gallery.html`

No unavoidable shared dependency requires committing those surface rewrites.

### Unrelated or pre-existing, never stage

- `atlas_desktop/api.py`
- `atlas_desktop/result_reports.py`
- `atlas_desktop/tests/test_phase194_grounded_analysis.py`
- `atlas_desktop/static/atlas_accounts.js`
- Post-suite account/onboarding hunks inside `atlas_desktop/static/index.html`
- `.phase152_packaging_lib/**`
- `benchmarks/agent_comparison/runs/**/.gitkeep`
- `benchmarks/agent_comparison/scripts/lib/__init__.py`
- `external_repos/requests` submodule pointer

The account/onboarding edits were made after the saved full suite completed. They are preserved on `feature/auth-onboarding-finish` in `C:\J.A.R.V.I.S\atlas-auth-onboarding` and are absent from this checkpoint candidate.

### Generated or temporary, never stage

- `.design_runtime/**`
- `.home_checkpoint_agents_empty/**`
- `.home_checkpoint_runtime/**`
- `.home_checkpoint_stale_repo/**`
- `.manual_py_temp/**`
- `.pytest_tmp_clean_20260711_182512/**`
- `.pytest_*` and `pytest_*` roots
- `AtlasPytestTemp/**`
- `.checkpoint_gate_20260712_1900/**`

Some old pytest roots are unreadable because of Windows ACLs. They remain classified as generated evidence and were not modified or committed.

## Vocabulary Decisions

| UI slot | Final wording | Reason |
|---|---|---|
| Navigation | Home, Scan, HN demo, Ask, Debug, Impact, Plan, Map | Short, familiar navigation labels |
| Ask title | Repository Analysis | Describes a report, not a conversation |
| Ask submit | Run analysis | Verb-led command |
| Ask input | Investigation brief | Frames the task before output |
| Debug title | Failure Investigation | Makes hypotheses and verification explicit |
| Impact title | Change Impact | Names the engineering question directly |
| Plan title | Implementation Plan | Avoids subscription-plan ambiguity |
| Export title | Agent Handoff | Describes the artifact and recipient |
| Loading | Scoping investigation, resolving evidence, assembling report | Describes repository work without simulated thinking |

The short navigation and descriptive page-title split keeps the product operational rather than bureaucratic.

## Data Provenance

| Displayed fact | Frontend source | API/backend source | Missing or stale behavior |
|---|---|---|---|
| Repository identity | `homeRepoName`, repository chip | `summary.repo_name` from scan state | Row hidden when unavailable |
| Files indexed | `homeFileCount`, ready-state facts | `summary.file_count` from index | Hidden when unavailable |
| Graph nodes | `homeNodeCount` | `summary.module_count` | Hidden when unavailable |
| Graph edges | `homeEdgeCount`, ready-state facts | `summary.dependency_edges` | Hidden when unavailable |
| Last indexed | `homeLastIndexed` | recent repository `last_scan_at` | Hidden when no matching record |
| Restore status | `homeRestoreStatus` | health `persistence.restored` | Falls back to readiness copy, never a fabricated latency |
| Freshness | Home freshness labels | trust-status `user_trust_label` | Shows checking/stale state explicitly |
| Connected agents | Home agent labels | MCP status `atlas_configured` | Shows no agent connected |
| Evidence count | Ask evidence cards | existing response `report.evidence[]` | Section omitted when empty |
| Confidence | Verdict and report footer | existing report/response confidence | Omitted when absent |
| Unknowns | Cannot-conclude and limitations sections | existing report limitations | Omitted when empty |
| Impact risk | Impact hierarchy | existing risk/blast/direct-impact fields | Unknown is labeled; zero remains zero |
| Analysis time | Not displayed | Not available | No value fabricated |

No new backend contract is required by the presentation checkpoint.

## Preserved Handlers

| Workflow | Existing handler retained |
|---|---|
| Scan local repository | existing scan/browse handlers |
| Load sample repository | `loadDemoMode('medium')` |
| Home ask / Ask | `submitHomeAsk`, `sendCopilotQuestion` |
| Impact | `runImpact` |
| Debug | `runInvestigationPlan` |
| Plan | `runChangePlan` |
| Handoff generation | `generateAgentExport` |
| Handoff copy/download | `copyExport`, `saveExport`, `copyForTarget` |
| Navigation and keyboard | existing `go`, Ctrl+K, Escape handlers |

The prior audit found the `index.html` inline-handler set and changed-JS API/fetch call sets unchanged from the base. The checkpoint adds presentation routing around existing handlers, not new backend endpoints.

## Width and Accessibility Review

The prior live computed-DOM review covered 1920x1080, 1440x900, 1024, 720, and 125 percent zoom:

- No horizontal overflow at any reviewed width.
- Navigation remained visible; it wrapped to two rows at 1024 rather than clipping.
- Labels remained readable without incoherent overlap.
- One blue-filled primary action remained per reviewed core screen after the Ask result-state fix.
- No ChatGPT-style bubble elements were found.
- Keyboard focus, Ctrl+K, Escape, reduced-motion rules, labels, and non-color status text were present.
- Structured HTML duplicate-ID check: pass.

The environment could not produce raster screenshots, so the review is DOM/computed-layout evidence rather than image evidence.

## Focused Tests and Lightweight Gates

### Prior broad focused run

- **213 passed, 7 skipped in 125.72 s**.
- Six skips require `ATLAS_RUN_HA=1` and a Home Assistant checkout.
- One skip is a historical phase report not shipped in the product repo.

### Final isolated checkpoint snapshot

The post-suite account changes were excluded using recorded pre-account snapshots of `index.html` and `atlas_accounts.js` in a verification copy.

- Pure UX contracts: **74 passed, 1 deselected in 4.61 s**.
- The deselected test uses `tmp_path` and was already covered by the prior valid isolated run.
- Three corrected legacy vocabulary contracts: **3 passed in 0.13 s**.
- Real-path focused validation of the previously failing guest, scan-route, and vocabulary areas: **9 passed in 2.23 s**.
- Final focused Engineering Analyst contract suite: **176 passed, 1 skipped in 65.55 s**, exit code `0`.
- A broader in-sandbox rerun was invalidated by `WinError 5` pytest temp ACL errors and is not counted.

### Other gates

- JavaScript syntax: pass for all six intended changed/new JS files.
- Excluded `atlas_accounts.js`: syntax also passes, but it is not part of this checkpoint.
- Duplicate IDs and dead Home inline handlers: pass (`1 passed in 0.08 s`).
- `git diff --check`: pass; output contained line-ending warnings only.

## Remaining Weaknesses

1. Home's pre-existing Resume card can show a second primary action during boot.
2. Navigation wraps at 1024 px; functional but visually less compact.
3. Evidence signals remain semi-structured, so file/symbol display is best-effort.
4. Copy path is not a true editor-open action because no OS bridge contract exists.
5. Impact responses have less structured report metadata than repository-analysis modes.
6. A final human eyes-on raster review remains desirable.

## Final Verdict

**A. APPROVE ENGINEERING ANALYST CHECKPOINT**

The checkpoint is approved for a scoped commit containing only the 10 presentation assets, 11 focused regression tests, and 4 design review documents listed above. Auth/Onboarding, backend, website, installer, benchmark, generated, and unrelated files remain excluded.
