# Phase 96D pilot packet comparisons

Structured single-reviewer pass on baseline vs contract-enriched packets.

## 1. actions/service_actions.py:21 (return_only)

### Baseline packet

```text
ITEM 1/20  record_id=RR-ff7762f625185de7
repo: local-jarvis-pilot  file: actions/service_actions.py:21
rule: inconsistent_return  kind: pattern  severity: medium  confidence: low
title: 'execute' may fall through to an implicit None

EXPLANATION
'execute' returns a value inside a branch but can also reach the end of the function without returning, yielding None. A missing final return is a common logic bug.

EVIDENCE
def execute(self, request: CommandRequest) -> CommandResult:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  18: class EnableAutostartAction(BaseAction):
  19:     intent = Intent.ENABLE_AUTOSTART.value
  20: 
  21:     def execute(self, request: CommandRequest) -> CommandResult:
  22:         try:
  23:             status = enable_autostart()
  24:             summary = (
```

### Enriched packet

```text
ITEM 1/20  record_id=RR-ff7762f625185de7
repo: local-jarvis-pilot  file: actions/service_actions.py:21
rule: inconsistent_return  kind: pattern  severity: medium  confidence: low
title: 'execute' may fall through to an implicit None

EXPLANATION
'execute' returns a value inside a branch but can also reach the end of the function without returning, yielding None. A missing final return is a common logic bug.

EVIDENCE
def execute(self, request: CommandRequest) -> CommandResult:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  18: class EnableAutostartAction(BaseAction):
  19:     intent = Intent.ENABLE_AUTOSTART.value
  20: 
  21:     def execute(self, request: CommandRequest) -> CommandResult:
  22:         try:
  23:             status = enable_autostart()
  24:             summary = (

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

RETURN CONTRACT EVIDENCE
  - {'confidence': 'explicit', 'obligation': 'return.non_none', 'sources': ['type_hint'], 'subject': {'file': 'actions/service_actions.py', 'qualname': 'EnableAutostartAction.execute', 'slot': 'return'}}

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 4
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: helped
- review minutes (est.): 1.33 -> 1.85
- missing for confirmation: inferred_strong caller dereference or non-null use path, interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 2. actions/website_actions.py:43 (conflict_only)

### Baseline packet

```text
ITEM 2/20  record_id=RR-31eb0982084ce6a6
repo: local-jarvis-pilot  file: actions/website_actions.py:43
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in '_entry_from_params'

EXPLANATION
'_entry_from_params' returns differing kinds of values (none, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def _entry_from_params(data: dict) -> WebsiteEntry | None:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  40:     return normalize_website_query(raw) if raw else ""
  41: 
  42: 
  43: def _entry_from_params(data: dict) -> WebsiteEntry | None:
  44:     if not data:
  45:         return None
  46:     try:
```

### Enriched packet

```text
ITEM 2/20  record_id=RR-31eb0982084ce6a6
repo: local-jarvis-pilot  file: actions/website_actions.py:43
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in '_entry_from_params'

EXPLANATION
'_entry_from_params' returns differing kinds of values (none, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def _entry_from_params(data: dict) -> WebsiteEntry | None:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  40:     return normalize_website_query(raw) if raw else ""
  41: 
  42: 
  43: def _entry_from_params(data: dict) -> WebsiteEntry | None:
  44:     if not data:
  45:         return None
  46:     try:

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

CONFLICTING EVIDENCE
  - {'confidence': 'explicit', 'conflict_reason': 'optional_return_signal', 'obligation': 'return.optional', 'sources': ['type_hint'], 'subject': {'file': 'actions/website_actions.py', 'qualname': '_entry_from_params', 'slot': 'return'}}
  - {'confidence': 'inferred_weak', 'conflict_reason': 'optional_return_signal', 'obligation': 'return.optional', 'sources': ['caller_behavior'], 'subject': {'file': 'actions/website_actions.py', 'qualname': '_entry_from_params', 'slot': 'return'}}
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
  - No explicit return type-hint contract or strong caller-behavior contract attached for this function.
```

### Pilot scores

- labels: baseline=false_positive enriched=false_positive
- confidence: 2 -> 3
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: neutral
- review minutes (est.): 1.29 -> 1.96
- missing for confirmation: explicit non-optional return type hint on flagged function, inferred_strong caller dereference or non-null use path, interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 3. alpha/session_log.py:40 (return_only)

### Baseline packet

```text
ITEM 3/20  record_id=RR-c46ee76fe3b8d918
repo: local-jarvis-pilot  file: alpha/session_log.py:40
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in '_infer_provider'

EXPLANATION
'_infer_provider' returns differing kinds of values (str, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def _infer_provider(summary: str, data: dict[str, Any] | None) -> str:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  37:     return _SESSION_DIR / "session.jsonl"
  38: 
  39: 
  40: def _infer_provider(summary: str, data: dict[str, Any] | None) -> str:
  41:     if data:
  42:         if data.get("alpha_blocked"):
  43:             return "blocked"
```

### Enriched packet

```text
ITEM 3/20  record_id=RR-c46ee76fe3b8d918
repo: local-jarvis-pilot  file: alpha/session_log.py:40
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in '_infer_provider'

EXPLANATION
'_infer_provider' returns differing kinds of values (str, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def _infer_provider(summary: str, data: dict[str, Any] | None) -> str:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  37:     return _SESSION_DIR / "session.jsonl"
  38: 
  39: 
  40: def _infer_provider(summary: str, data: dict[str, Any] | None) -> str:
  41:     if data:
  42:         if data.get("alpha_blocked"):
  43:             return "blocked"

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

RETURN CONTRACT EVIDENCE
  - {'confidence': 'explicit', 'obligation': 'return.non_none', 'sources': ['type_hint'], 'subject': {'file': 'alpha/session_log.py', 'qualname': '_infer_provider', 'slot': 'return'}}

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 4
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: helped
- review minutes (est.): 1.31 -> 1.83
- missing for confirmation: inferred_strong caller dereference or non-null use path, interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 4. assistant/investigation_scheduler.py:161 (return_only)

### Baseline packet

```text
ITEM 4/20  record_id=RR-9e301472d7138ce2
repo: local-jarvis-pilot  file: assistant/investigation_scheduler.py:161
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in 'scheduler_tick'

EXPLANATION
'scheduler_tick' returns differing kinds of values (list, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def scheduler_tick(*, force: bool = False) -> list[str]:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  158:     return (time.time() - last_ts) >= interval
  159: 
  160: 
  161: def scheduler_tick(*, force: bool = False) -> list[str]:
  162:     state = _load()
  163:     if state.get("paused") and not force:
  164:         return []
```

### Enriched packet

```text
ITEM 4/20  record_id=RR-9e301472d7138ce2
repo: local-jarvis-pilot  file: assistant/investigation_scheduler.py:161
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in 'scheduler_tick'

EXPLANATION
'scheduler_tick' returns differing kinds of values (list, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def scheduler_tick(*, force: bool = False) -> list[str]:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  158:     return (time.time() - last_ts) >= interval
  159: 
  160: 
  161: def scheduler_tick(*, force: bool = False) -> list[str]:
  162:     state = _load()
  163:     if state.get("paused") and not force:
  164:         return []

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

RETURN CONTRACT EVIDENCE
  - {'confidence': 'explicit', 'obligation': 'return.non_none', 'sources': ['type_hint'], 'subject': {'file': 'assistant/investigation_scheduler.py', 'qualname': 'scheduler_tick', 'slot': 'return'}}

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 4
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: helped
- review minutes (est.): 1.32 -> 1.84
- missing for confirmation: inferred_strong caller dereference or non-null use path, interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 5. backups/jarvis_patches/20260526_121610_95ec3bbe/services__live_paper_engine.py:960 (return_and_caller)

### Baseline packet

```text
ITEM 5/20  record_id=RR-d3ac070672e99137
repo: local-jarvis-pilot  file: backups/jarvis_patches/20260526_121610_95ec3bbe/services__live_paper_engine.py:960
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in '_safe_reconcile_adapter_positions'

EXPLANATION
'_safe_reconcile_adapter_positions' returns differing kinds of values (dict, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def _safe_reconcile_adapter_positions(

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  957:     }
  958: 
  959: 
  960: def _safe_reconcile_adapter_positions(
  961:     execution_adapter: ExecutionAdapter | None,
  962:     open_positions: list[dict[str, Any]],
  963: ) -> dict[str, Any]:
```

### Enriched packet

```text
ITEM 5/20  record_id=RR-d3ac070672e99137
repo: local-jarvis-pilot  file: backups/jarvis_patches/20260526_121610_95ec3bbe/services__live_paper_engine.py:960
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in '_safe_reconcile_adapter_positions'

EXPLANATION
'_safe_reconcile_adapter_positions' returns differing kinds of values (dict, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def _safe_reconcile_adapter_positions(

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  957:     }
  958: 
  959: 
  960: def _safe_reconcile_adapter_positions(
  961:     execution_adapter: ExecutionAdapter | None,
  962:     open_positions: list[dict[str, Any]],
  963: ) -> dict[str, Any]:

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

RETURN CONTRACT EVIDENCE
  - {'confidence': 'explicit', 'obligation': 'return.non_none', 'sources': ['type_hint'], 'subject': {'file': 'backups/jarvis_patches/20260526_121610_95ec3bbe/services__live_paper_engine.py', 'qualname': '_safe_reconcile_adapter_positions', 'slot': 'return'}}

CALLER BEHAVIOR EVIDENCE
  - {'confidence': 'inferred_strong', 'obligation': 'return.non_none', 'sources': ['caller_behavior'], 'subject': {'file': 'backups/jarvis_patches/20260526_121610_95ec3bbe/services__live_paper_engine.py', 'qualname': '_safe_reconcile_adapter_positions', 'slot': 'return'}}
  - {'confidence': 'inferred_strong', 'obligation': 'null.forbidden', 'sources': ['caller_behavior'], 'subject': {'file': 'backups/jarvis_patches/20260526_121610_95ec3bbe/services__live_paper_engine.py', 'qualname': '_safe_reconcile_adapter_positions', 'slot': 'return'}}

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 4
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: helped
- review minutes (est.): 1.25 -> 1.92
- missing for confirmation: interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 6. brain/patch_command_phrases.py:118 (return_only)

### Baseline packet

```text
ITEM 6/20  record_id=RR-64ec717ecc70c8f1
repo: local-jarvis-pilot  file: brain/patch_command_phrases.py:118
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in 'is_patch_workflow_phrase'

EXPLANATION
'is_patch_workflow_phrase' returns differing kinds of values (bool, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def is_patch_workflow_phrase(text: str) -> bool:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  115:         return text.strip()
  116: 
  117: 
  118: def is_patch_workflow_phrase(text: str) -> bool:
  119:     normalized = _normalize(_prepare_text(text))
  120:     if not normalized:
  121:         return False
```

### Enriched packet

```text
ITEM 6/20  record_id=RR-64ec717ecc70c8f1
repo: local-jarvis-pilot  file: brain/patch_command_phrases.py:118
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in 'is_patch_workflow_phrase'

EXPLANATION
'is_patch_workflow_phrase' returns differing kinds of values (bool, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def is_patch_workflow_phrase(text: str) -> bool:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  115:         return text.strip()
  116: 
  117: 
  118: def is_patch_workflow_phrase(text: str) -> bool:
  119:     normalized = _normalize(_prepare_text(text))
  120:     if not normalized:
  121:         return False

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

RETURN CONTRACT EVIDENCE
  - {'confidence': 'explicit', 'obligation': 'return.non_none', 'sources': ['type_hint'], 'subject': {'file': 'brain/patch_command_phrases.py', 'qualname': 'is_patch_workflow_phrase', 'slot': 'return'}}

CONFLICTING EVIDENCE
  - {'confidence': 'inferred_weak', 'conflict_reason': 'optional_return_signal', 'obligation': 'return.optional', 'sources': ['caller_behavior'], 'subject': {'file': 'brain/patch_command_phrases.py', 'qualname': 'is_patch_workflow_phrase', 'slot': 'return'}}
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 4
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: helped
- review minutes (est.): 1.27 -> 1.86
- missing for confirmation: inferred_strong caller dereference or non-null use path, interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 7. builder_core/gitutil.py:70 (return_only)

### Baseline packet

```text
ITEM 7/20  record_id=RR-1fab6576343789e6
repo: local-jarvis-pilot  file: builder_core/gitutil.py:70
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in 'churn_counts'

EXPLANATION
'churn_counts' returns differing kinds of values (dict, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def churn_counts(cwd: str, limit: int = 400) -> Dict[str, int]:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  67:     return commits
  68: 
  69: 
  70: def churn_counts(cwd: str, limit: int = 400) -> Dict[str, int]:
  71:     """Map of relative file path -> number of recent commits that touched it."""
  72:     out = _run(
  73:         ["log", f"-n{limit}", "--name-only", "--pretty=format:%x00"], cwd
```

### Enriched packet

```text
ITEM 7/20  record_id=RR-1fab6576343789e6
repo: local-jarvis-pilot  file: builder_core/gitutil.py:70
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in 'churn_counts'

EXPLANATION
'churn_counts' returns differing kinds of values (dict, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def churn_counts(cwd: str, limit: int = 400) -> Dict[str, int]:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  67:     return commits
  68: 
  69: 
  70: def churn_counts(cwd: str, limit: int = 400) -> Dict[str, int]:
  71:     """Map of relative file path -> number of recent commits that touched it."""
  72:     out = _run(
  73:         ["log", f"-n{limit}", "--name-only", "--pretty=format:%x00"], cwd

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

RETURN CONTRACT EVIDENCE
  - {'confidence': 'explicit', 'obligation': 'return.non_none', 'sources': ['type_hint'], 'subject': {'file': 'builder_core/gitutil.py', 'qualname': 'churn_counts', 'slot': 'return'}}

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 4
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: helped
- review minutes (est.): 1.38 -> 1.9
- missing for confirmation: inferred_strong caller dereference or non-null use path, interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 8. desktop/control_runtime.py:208 (return_only)

### Baseline packet

```text
ITEM 8/20  record_id=RR-51c25255cdce8c68
repo: local-jarvis-pilot  file: desktop/control_runtime.py:208
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in 'extract_button_label'

EXPLANATION
'extract_button_label' returns differing kinds of values (str, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def extract_button_label(raw: str) -> str:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  205:     return ""
  206: 
  207: 
  208: def extract_button_label(raw: str) -> str:
  209:     text = (raw or "").strip()
  210:     patterns = [
  211:         r"click\s+the\s+button\s+that\s+says\s+(.+)$",
```

### Enriched packet

```text
ITEM 8/20  record_id=RR-51c25255cdce8c68
repo: local-jarvis-pilot  file: desktop/control_runtime.py:208
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in 'extract_button_label'

EXPLANATION
'extract_button_label' returns differing kinds of values (str, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def extract_button_label(raw: str) -> str:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  205:     return ""
  206: 
  207: 
  208: def extract_button_label(raw: str) -> str:
  209:     text = (raw or "").strip()
  210:     patterns = [
  211:         r"click\s+the\s+button\s+that\s+says\s+(.+)$",

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

RETURN CONTRACT EVIDENCE
  - {'confidence': 'explicit', 'obligation': 'return.non_none', 'sources': ['type_hint'], 'subject': {'file': 'desktop/control_runtime.py', 'qualname': 'extract_button_label', 'slot': 'return'}}

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 4
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: helped
- review minutes (est.): 1.27 -> 1.79
- missing for confirmation: inferred_strong caller dereference or non-null use path, interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 9. investigation/replay_cache.py:12 (conflict_only)

### Baseline packet

```text
ITEM 9/20  record_id=RR-9cb7b286ef97eb22
repo: local-jarvis-pilot  file: investigation/replay_cache.py:12
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in 'get_cache'

EXPLANATION
'get_cache' returns differing kinds of values (none, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def get_cache(key: str) -> Any | None:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  9: _MAX = 64
  10: 
  11: 
  12: def get_cache(key: str) -> Any | None:
  13:     if key not in _CACHE:
  14:         return None
  15:     value = _CACHE.pop(key)
```

### Enriched packet

```text
ITEM 9/20  record_id=RR-9cb7b286ef97eb22
repo: local-jarvis-pilot  file: investigation/replay_cache.py:12
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in 'get_cache'

EXPLANATION
'get_cache' returns differing kinds of values (none, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def get_cache(key: str) -> Any | None:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  9: _MAX = 64
  10: 
  11: 
  12: def get_cache(key: str) -> Any | None:
  13:     if key not in _CACHE:
  14:         return None
  15:     value = _CACHE.pop(key)

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

CONFLICTING EVIDENCE
  - {'confidence': 'explicit', 'conflict_reason': 'optional_return_signal', 'obligation': 'return.optional', 'sources': ['type_hint'], 'subject': {'file': 'investigation/replay_cache.py', 'qualname': 'get_cache', 'slot': 'return'}}
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
  - No explicit return type-hint contract or strong caller-behavior contract attached for this function.
```

### Pilot scores

- labels: baseline=false_positive enriched=false_positive
- confidence: 2 -> 3
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: neutral
- review minutes (est.): 1.3 -> 1.89
- missing for confirmation: explicit non-optional return type hint on flagged function, inferred_strong caller dereference or non-null use path, interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 10. runtime/dashboard_health.py:27 (return_and_caller)

### Baseline packet

```text
ITEM 10/20  record_id=RR-85aa7373738f78fa
repo: local-jarvis-pilot  file: runtime/dashboard_health.py:27
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in '_load'

EXPLANATION
'_load' returns differing kinds of values (dict, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def _load() -> dict[str, Any]:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  24:     return datetime.now(timezone.utc).isoformat()
  25: 
  26: 
  27: def _load() -> dict[str, Any]:
  28:     if not DASHBOARD_HEALTH_PATH.exists():
  29:         return {}
  30:     try:
```

### Enriched packet

```text
ITEM 10/20  record_id=RR-85aa7373738f78fa
repo: local-jarvis-pilot  file: runtime/dashboard_health.py:27
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in '_load'

EXPLANATION
'_load' returns differing kinds of values (dict, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def _load() -> dict[str, Any]:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  24:     return datetime.now(timezone.utc).isoformat()
  25: 
  26: 
  27: def _load() -> dict[str, Any]:
  28:     if not DASHBOARD_HEALTH_PATH.exists():
  29:         return {}
  30:     try:

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

RETURN CONTRACT EVIDENCE
  - {'confidence': 'explicit', 'obligation': 'return.non_none', 'sources': ['type_hint'], 'subject': {'file': 'runtime/dashboard_health.py', 'qualname': '_load', 'slot': 'return'}}

CALLER BEHAVIOR EVIDENCE
  - {'confidence': 'inferred_strong', 'obligation': 'return.non_none', 'sources': ['caller_behavior'], 'subject': {'file': 'runtime/dashboard_health.py', 'qualname': '_load', 'slot': 'return'}}
  - {'confidence': 'inferred_strong', 'obligation': 'null.forbidden', 'sources': ['caller_behavior'], 'subject': {'file': 'runtime/dashboard_health.py', 'qualname': '_load', 'slot': 'return'}}

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 4
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: helped
- review minutes (est.): 1.25 -> 1.93
- missing for confirmation: interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 11. tests/test_phase41_6_tts_runtime.py:162 (conflict_only)

### Baseline packet

```text
ITEM 11/20  record_id=RR-ac85cc7772ea17ab
repo: local-jarvis-pilot  file: tests/test_phase41_6_tts_runtime.py:162
rule: inconsistent_return  kind: pattern  severity: medium  confidence: low
title: 'test_streaming_retry_blocking_on_failure' may fall through to an implicit None

EXPLANATION
'test_streaming_retry_blocking_on_failure' returns a value inside a branch but can also reach the end of the function without returning, yielding None. A missing final return is a common logic bug.

EVIDENCE
def test_streaming_retry_blocking_on_failure(monkeypatch):

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  159:     assert sub_called == ["hi"]
  160: 
  161: 
  162: def test_streaming_retry_blocking_on_failure(monkeypatch):
  163:     monkeypatch.setattr("config.TTS_SAFE_MODE", False, raising=False)
  164:     monkeypatch.setattr("config.TTS_STREAMING_ENABLED", True, raising=False)
  165:     monkeypatch.setattr("config.TTS_ENGINE", "edge_tts", raising=False)
```

### Enriched packet

```text
ITEM 11/20  record_id=RR-ac85cc7772ea17ab
repo: local-jarvis-pilot  file: tests/test_phase41_6_tts_runtime.py:162
rule: inconsistent_return  kind: pattern  severity: medium  confidence: low
title: 'test_streaming_retry_blocking_on_failure' may fall through to an implicit None

EXPLANATION
'test_streaming_retry_blocking_on_failure' returns a value inside a branch but can also reach the end of the function without returning, yielding None. A missing final return is a common logic bug.

EVIDENCE
def test_streaming_retry_blocking_on_failure(monkeypatch):

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  159:     assert sub_called == ["hi"]
  160: 
  161: 
  162: def test_streaming_retry_blocking_on_failure(monkeypatch):
  163:     monkeypatch.setattr("config.TTS_SAFE_MODE", False, raising=False)
  164:     monkeypatch.setattr("config.TTS_STREAMING_ENABLED", True, raising=False)
  165:     monkeypatch.setattr("config.TTS_ENGINE", "edge_tts", raising=False)

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
  - No explicit return type-hint contract or strong caller-behavior contract attached for this function.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 3
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: neutral
- review minutes (est.): 1.3 -> 1.8
- missing for confirmation: explicit non-optional return type hint on flagged function, inferred_strong caller dereference or non-null use path, interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 12. tests/test_phase71_tool_use.py:127 (conflict_only)

### Baseline packet

```text
ITEM 12/20  record_id=RR-78abdc44140a6644
repo: local-jarvis-pilot  file: tests/test_phase71_tool_use.py:127
rule: inconsistent_return  kind: pattern  severity: medium  confidence: low
title: 'test_approval_required_for_every_external_step' may fall through to an implicit None

EXPLANATION
'test_approval_required_for_every_external_step' returns a value inside a branch but can also reach the end of the function without returning, yielding None. A missing final return is a common logic bug.

EVIDENCE
def test_approval_required_for_every_external_step():

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  124:     assert len(run.steps) == 1
  125: 
  126: 
  127: def test_approval_required_for_every_external_step():
  128:     seen: list[str] = []
  129: 
  130:     def approver(step: PlanStep) -> bool:
```

### Enriched packet

```text
ITEM 12/20  record_id=RR-78abdc44140a6644
repo: local-jarvis-pilot  file: tests/test_phase71_tool_use.py:127
rule: inconsistent_return  kind: pattern  severity: medium  confidence: low
title: 'test_approval_required_for_every_external_step' may fall through to an implicit None

EXPLANATION
'test_approval_required_for_every_external_step' returns a value inside a branch but can also reach the end of the function without returning, yielding None. A missing final return is a common logic bug.

EVIDENCE
def test_approval_required_for_every_external_step():

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  124:     assert len(run.steps) == 1
  125: 
  126: 
  127: def test_approval_required_for_every_external_step():
  128:     seen: list[str] = []
  129: 
  130:     def approver(step: PlanStep) -> bool:

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
  - No explicit return type-hint contract or strong caller-behavior contract attached for this function.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 3
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: neutral
- review minutes (est.): 1.3 -> 1.8
- missing for confirmation: explicit non-optional return type hint on flagged function, inferred_strong caller dereference or non-null use path, interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 13. tests/test_tts_failure_visibility.py:35 (conflict_only)

### Baseline packet

```text
ITEM 13/20  record_id=RR-2e517bafbae2d513
repo: local-jarvis-pilot  file: tests/test_tts_failure_visibility.py:35
rule: inconsistent_return  kind: pattern  severity: medium  confidence: low
title: 'test_async_tts_failure_recorded' may fall through to an implicit None

EXPLANATION
'test_async_tts_failure_recorded' returns a value inside a branch but can also reach the end of the function without returning, yielding None. A missing final return is a common logic bug.

EVIDENCE
def test_async_tts_failure_recorded(monkeypatch, capsys):

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  32:     reset_tts_status_cache()
  33: 
  34: 
  35: def test_async_tts_failure_recorded(monkeypatch, capsys):
  36:     monkeypatch.setattr("config.TTS_ASYNC", True, raising=False)
  37:     monkeypatch.setattr("voice.tts.TTS_ASYNC", True, raising=False)
  38:     monkeypatch.setattr("config.TTS_ENGINE", "edge_tts", raising=False)
```

### Enriched packet

```text
ITEM 13/20  record_id=RR-2e517bafbae2d513
repo: local-jarvis-pilot  file: tests/test_tts_failure_visibility.py:35
rule: inconsistent_return  kind: pattern  severity: medium  confidence: low
title: 'test_async_tts_failure_recorded' may fall through to an implicit None

EXPLANATION
'test_async_tts_failure_recorded' returns a value inside a branch but can also reach the end of the function without returning, yielding None. A missing final return is a common logic bug.

EVIDENCE
def test_async_tts_failure_recorded(monkeypatch, capsys):

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  32:     reset_tts_status_cache()
  33: 
  34: 
  35: def test_async_tts_failure_recorded(monkeypatch, capsys):
  36:     monkeypatch.setattr("config.TTS_ASYNC", True, raising=False)
  37:     monkeypatch.setattr("voice.tts.TTS_ASYNC", True, raising=False)
  38:     monkeypatch.setattr("config.TTS_ENGINE", "edge_tts", raising=False)

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
  - No explicit return type-hint contract or strong caller-behavior contract attached for this function.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 3
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: neutral
- review minutes (est.): 1.29 -> 1.8
- missing for confirmation: explicit non-optional return type hint on flagged function, inferred_strong caller dereference or non-null use path, interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 14. tests_tmp/pytest_temp/pytest-of-babi2/pytest-341/test_cli_ask_returns_bug_findi0/fake_repo/python_programs/off_by_one.py:1 (conflict_only)

### Baseline packet

```text
ITEM 14/20  record_id=RR-9449cab35a21afcf
repo: local-jarvis-pilot  file: tests_tmp/pytest_temp/pytest-of-babi2/pytest-341/test_cli_ask_returns_bug_findi0/fake_repo/python_programs/off_by_one.py:1
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: 'last_item' may fall through to an implicit None

EXPLANATION
'last_item' returns a value on some paths but can also reach the end of its body without returning, yielding None. Interprocedural evidence is insufficient to confirm this is a bug (callers null-check it, do not dereference it, or are unresolved), so this is a diagnostic only.

EVIDENCE


WHY THIS MIGHT BE WRONG
The fall-through path may be unreachable in a way the intraprocedural control-flow approximation cannot see, or returning None on that path may be an unstated but intended outcome that callers tolerate.

NEXT VERIFICATION STEP
Confirm whether the no-return path is reachable; if so, add an explicit return value (or an explicit `return None` if None is intended).

SOURCE WINDOW
  1: def last_item(items):
  2:     for index in range(len(items) + 1):
  3:         return items[index]
```

### Enriched packet

```text
ITEM 14/20  record_id=RR-9449cab35a21afcf
repo: local-jarvis-pilot  file: tests_tmp/pytest_temp/pytest-of-babi2/pytest-341/test_cli_ask_returns_bug_findi0/fake_repo/python_programs/off_by_one.py:1
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: 'last_item' may fall through to an implicit None

EXPLANATION
'last_item' returns a value on some paths but can also reach the end of its body without returning, yielding None. Interprocedural evidence is insufficient to confirm this is a bug (callers null-check it, do not dereference it, or are unresolved), so this is a diagnostic only.

EVIDENCE


WHY THIS MIGHT BE WRONG
The fall-through path may be unreachable in a way the intraprocedural control-flow approximation cannot see, or returning None on that path may be an unstated but intended outcome that callers tolerate.

NEXT VERIFICATION STEP
Confirm whether the no-return path is reachable; if so, add an explicit return value (or an explicit `return None` if None is intended).

SOURCE WINDOW
  1: def last_item(items):
  2:     for index in range(len(items) + 1):
  3:         return items[index]

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
  - No explicit return type-hint contract or strong caller-behavior contract attached for this function.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 3
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: neutral
- review minutes (est.): 1.5 -> 2.0
- missing for confirmation: explicit non-optional return type hint on flagged function, inferred_strong caller dereference or non-null use path, interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 15. ui/console_modal.py:150 (conflict_only)

### Baseline packet

```text
ITEM 15/20  record_id=RR-c65b16fe00a9eac0
repo: local-jarvis-pilot  file: ui/console_modal.py:150
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in '_run_modal_with_input_fn'

EXPLANATION
'_run_modal_with_input_fn' returns differing kinds of values (none, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def _run_modal_with_input_fn(

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  147:         return True
  148: 
  149: 
  150: def _run_modal_with_input_fn(
  151:     prompt: str,
  152:     input_fn: Callable[[str], str],
  153:     parse_yes_no: Callable[[str], bool | None],
```

### Enriched packet

```text
ITEM 15/20  record_id=RR-c65b16fe00a9eac0
repo: local-jarvis-pilot  file: ui/console_modal.py:150
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in '_run_modal_with_input_fn'

EXPLANATION
'_run_modal_with_input_fn' returns differing kinds of values (none, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def _run_modal_with_input_fn(

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  147:         return True
  148: 
  149: 
  150: def _run_modal_with_input_fn(
  151:     prompt: str,
  152:     input_fn: Callable[[str], str],
  153:     parse_yes_no: Callable[[str], bool | None],

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

CONFLICTING EVIDENCE
  - {'confidence': 'explicit', 'conflict_reason': 'optional_return_signal', 'obligation': 'return.optional', 'sources': ['type_hint'], 'subject': {'file': 'ui/console_modal.py', 'qualname': '_run_modal_with_input_fn', 'slot': 'return'}}
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
  - No explicit return type-hint contract or strong caller-behavior contract attached for this function.
```

### Pilot scores

- labels: baseline=unclear enriched=unclear
- confidence: 2 -> 3
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: neutral
- review minutes (est.): 1.25 -> 1.83
- missing for confirmation: explicit non-optional return type hint on flagged function, inferred_strong caller dereference or non-null use path, interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 16. voice/providers/elevenlabs_websocket.py:30 (caller_only)

### Baseline packet

```text
ITEM 16/20  record_id=RR-ff90c3494c7f555a
repo: local-jarvis-pilot  file: voice/providers/elevenlabs_websocket.py:30
rule: inconsistent_return  kind: pattern  severity: medium  confidence: low
title: 'get_elevenlabs_ws_session' may fall through to an implicit None

EXPLANATION
'get_elevenlabs_ws_session' returns a value inside a branch but can also reach the end of the function without returning, yielding None. A missing final return is a common logic bug.

EVIDENCE
def get_elevenlabs_ws_session() -> "ElevenLabsWebSocketSession":

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  27:         return True
  28: 
  29: 
  30: def get_elevenlabs_ws_session() -> "ElevenLabsWebSocketSession":
  31:     global _session
  32:     with _session_lock:
  33:         if _session is None:
```

### Enriched packet

```text
ITEM 16/20  record_id=RR-ff90c3494c7f555a
repo: local-jarvis-pilot  file: voice/providers/elevenlabs_websocket.py:30
rule: inconsistent_return  kind: pattern  severity: medium  confidence: low
title: 'get_elevenlabs_ws_session' may fall through to an implicit None

EXPLANATION
'get_elevenlabs_ws_session' returns a value inside a branch but can also reach the end of the function without returning, yielding None. A missing final return is a common logic bug.

EVIDENCE
def get_elevenlabs_ws_session() -> "ElevenLabsWebSocketSession":

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  27:         return True
  28: 
  29: 
  30: def get_elevenlabs_ws_session() -> "ElevenLabsWebSocketSession":
  31:     global _session
  32:     with _session_lock:
  33:         if _session is None:

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

CALLER BEHAVIOR EVIDENCE
  - {'confidence': 'inferred_strong', 'obligation': 'return.non_none', 'sources': ['caller_behavior'], 'subject': {'file': 'voice/providers/elevenlabs_websocket.py', 'qualname': 'get_elevenlabs_ws_session', 'slot': 'return'}}
  - {'confidence': 'inferred_strong', 'obligation': 'null.forbidden', 'sources': ['caller_behavior'], 'subject': {'file': 'voice/providers/elevenlabs_websocket.py', 'qualname': 'get_elevenlabs_ws_session', 'slot': 'return'}}

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 4
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: helped
- review minutes (est.): 1.31 -> 1.9
- missing for confirmation: explicit non-optional return type hint on flagged function, interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 17. voice/pyttsx3_completion.py:333 (return_and_caller)

### Baseline packet

```text
ITEM 17/20  record_id=RR-f19b93ae409b5e1e
repo: local-jarvis-pilot  file: voice/pyttsx3_completion.py:333
rule: inconsistent_return  kind: pattern  severity: medium  confidence: low
title: 'snapshot' may fall through to an implicit None

EXPLANATION
'snapshot' returns a value inside a branch but can also reach the end of the function without returning, yielding None. A missing final return is a common logic bug.

EVIDENCE
def snapshot(self) -> dict[str, object]:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  330:     worker_thread_id: int = 0
  331:     error: Exception | None = None
  332: 
  333:     def snapshot(self) -> dict[str, object]:
  334:         with self.lock:
  335:             return {
  336:                 "playback_started": self.playback_started,
```

### Enriched packet

```text
ITEM 17/20  record_id=RR-f19b93ae409b5e1e
repo: local-jarvis-pilot  file: voice/pyttsx3_completion.py:333
rule: inconsistent_return  kind: pattern  severity: medium  confidence: low
title: 'snapshot' may fall through to an implicit None

EXPLANATION
'snapshot' returns a value inside a branch but can also reach the end of the function without returning, yielding None. A missing final return is a common logic bug.

EVIDENCE
def snapshot(self) -> dict[str, object]:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  330:     worker_thread_id: int = 0
  331:     error: Exception | None = None
  332: 
  333:     def snapshot(self) -> dict[str, object]:
  334:         with self.lock:
  335:             return {
  336:                 "playback_started": self.playback_started,

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

RETURN CONTRACT EVIDENCE
  - {'confidence': 'explicit', 'obligation': 'return.non_none', 'sources': ['type_hint'], 'subject': {'file': 'voice/pyttsx3_completion.py', 'qualname': '_WorkerState.snapshot', 'slot': 'return'}}

CALLER BEHAVIOR EVIDENCE
  - {'confidence': 'inferred_strong', 'obligation': 'return.non_none', 'sources': ['caller_behavior'], 'subject': {'file': 'voice/pyttsx3_completion.py', 'qualname': '_WorkerState.snapshot', 'slot': 'return'}}
  - {'confidence': 'inferred_strong', 'obligation': 'null.forbidden', 'sources': ['caller_behavior'], 'subject': {'file': 'voice/pyttsx3_completion.py', 'qualname': '_WorkerState.snapshot', 'slot': 'return'}}

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 4
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: helped
- review minutes (est.): 1.34 -> 2.02
- missing for confirmation: interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 18. voice/tts_pyttsx3.py:40 (caller_only)

### Baseline packet

```text
ITEM 18/20  record_id=RR-bee9192471b79acc
repo: local-jarvis-pilot  file: voice/tts_pyttsx3.py:40
rule: inconsistent_return  kind: pattern  severity: medium  confidence: low
title: '_get_engine' may fall through to an implicit None

EXPLANATION
'_get_engine' returns a value inside a branch but can also reach the end of the function without returning, yielding None. A missing final return is a common logic bug.

EVIDENCE
def _get_engine(rate_raw: str):

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  37:     _select_voice(engine)
  38: 
  39: 
  40: def _get_engine(rate_raw: str):
  41:     global _engine
  42:     with _engine_lock:
  43:         if _engine is not None:
```

### Enriched packet

```text
ITEM 18/20  record_id=RR-bee9192471b79acc
repo: local-jarvis-pilot  file: voice/tts_pyttsx3.py:40
rule: inconsistent_return  kind: pattern  severity: medium  confidence: low
title: '_get_engine' may fall through to an implicit None

EXPLANATION
'_get_engine' returns a value inside a branch but can also reach the end of the function without returning, yielding None. A missing final return is a common logic bug.

EVIDENCE
def _get_engine(rate_raw: str):

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  37:     _select_voice(engine)
  38: 
  39: 
  40: def _get_engine(rate_raw: str):
  41:     global _engine
  42:     with _engine_lock:
  43:         if _engine is not None:

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

CALLER BEHAVIOR EVIDENCE
  - {'confidence': 'inferred_strong', 'obligation': 'return.non_none', 'sources': ['caller_behavior'], 'subject': {'file': 'voice/tts_pyttsx3.py', 'qualname': '_get_engine', 'slot': 'return'}}
  - {'confidence': 'inferred_strong', 'obligation': 'null.forbidden', 'sources': ['caller_behavior'], 'subject': {'file': 'voice/tts_pyttsx3.py', 'qualname': '_get_engine', 'slot': 'return'}}

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 4
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: helped
- review minutes (est.): 1.29 -> 1.89
- missing for confirmation: explicit non-optional return type hint on flagged function, interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 19. voice/voice_calibration.py:58 (return_and_caller)

### Baseline packet

```text
ITEM 19/20  record_id=RR-36460abb83e89a0e
repo: local-jarvis-pilot  file: voice/voice_calibration.py:58
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in '_load_payload'

EXPLANATION
'_load_payload' returns differing kinds of values (dict, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def _load_payload() -> dict:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  55:     return normalize_spoken_command(cleanup_transcript(text or ""))[:240]
  56: 
  57: 
  58: def _load_payload() -> dict:
  59:     path = Path(VOICE_CALIBRATION_PATH)
  60:     if not path.is_file():
  61:         return {"samples": [], "correction_pairs": []}
```

### Enriched packet

```text
ITEM 19/20  record_id=RR-36460abb83e89a0e
repo: local-jarvis-pilot  file: voice/voice_calibration.py:58
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in '_load_payload'

EXPLANATION
'_load_payload' returns differing kinds of values (dict, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def _load_payload() -> dict:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  55:     return normalize_spoken_command(cleanup_transcript(text or ""))[:240]
  56: 
  57: 
  58: def _load_payload() -> dict:
  59:     path = Path(VOICE_CALIBRATION_PATH)
  60:     if not path.is_file():
  61:         return {"samples": [], "correction_pairs": []}

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

RETURN CONTRACT EVIDENCE
  - {'confidence': 'explicit', 'obligation': 'return.non_none', 'sources': ['type_hint'], 'subject': {'file': 'voice/voice_calibration.py', 'qualname': '_load_payload', 'slot': 'return'}}

CALLER BEHAVIOR EVIDENCE
  - {'confidence': 'inferred_strong', 'obligation': 'return.non_none', 'sources': ['caller_behavior'], 'subject': {'file': 'voice/voice_calibration.py', 'qualname': '_load_payload', 'slot': 'return'}}
  - {'confidence': 'inferred_strong', 'obligation': 'null.forbidden', 'sources': ['caller_behavior'], 'subject': {'file': 'voice/voice_calibration.py', 'qualname': '_load_payload', 'slot': 'return'}}

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 4
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: helped
- review minutes (est.): 1.28 -> 1.96
- missing for confirmation: interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path

## 20. website_audit/inspector.py:42 (return_and_caller)

### Baseline packet

```text
ITEM 20/20  record_id=RR-902344e075c1b6ff
repo: local-jarvis-pilot  file: website_audit/inspector.py:42
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in '_read'

EXPLANATION
'_read' returns differing kinds of values (str, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def _read(path: Path) -> str:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  39:     notes: list[str] = field(default_factory=list)
  40: 
  41: 
  42: def _read(path: Path) -> str:
  43:     try:
  44:         return path.read_text(encoding="utf-8", errors="replace")
  45:     except OSError:
```

### Enriched packet

```text
ITEM 20/20  record_id=RR-902344e075c1b6ff
repo: local-jarvis-pilot  file: website_audit/inspector.py:42
rule: inconsistent_return  kind: pattern  severity: medium  confidence: medium
title: Inconsistent return types in '_read'

EXPLANATION
'_read' returns differing kinds of values (str, value). Callers cannot rely on a stable return type; this often signals a missed case.

EVIDENCE
def _read(path: Path) -> str:

WHY THIS MIGHT BE WRONG
Mixed return shapes can be intentional (e.g. value-or-None APIs).

NEXT VERIFICATION STEP
Check every return path and the callers' expectations for a consistent contract.

SOURCE WINDOW
  39:     notes: list[str] = field(default_factory=list)
  40: 
  41: 
  42: def _read(path: Path) -> str:
  43:     try:
  44:         return path.read_text(encoding="utf-8", errors="replace")
  45:     except OSError:

CONTRACT REVIEW (supporting evidence — review lead only)
status: review_lead_only

RETURN CONTRACT EVIDENCE
  - {'confidence': 'explicit', 'obligation': 'return.non_none', 'sources': ['type_hint'], 'subject': {'file': 'website_audit/inspector.py', 'qualname': '_read', 'slot': 'return'}}

CALLER BEHAVIOR EVIDENCE
  - {'confidence': 'inferred_strong', 'obligation': 'return.non_none', 'sources': ['caller_behavior'], 'subject': {'file': 'website_audit/inspector.py', 'qualname': '_read', 'slot': 'return'}}
  - {'confidence': 'inferred_strong', 'obligation': 'null.forbidden', 'sources': ['caller_behavior'], 'subject': {'file': 'website_audit/inspector.py', 'qualname': '_read', 'slot': 'return'}}

CONFLICTING EVIDENCE
  - {'conflict_reason': 'interprocedural_gate_not_met', 'detail': 'No unambiguous same-file caller dereferences the return without null-checking it (Phase 93B promotion gate).'}

WHY NOT CONFIRMED
  - Contract enrichment is supporting evidence only; no confirmation evaluators are enabled.
  - This finding is labeled review_lead_only — not a confirmed defect.
  - callee_behavior, guard, and docstring-return facts are excluded from promotion and confirmation.
  - Finding remains quarantined (kind=pattern); contract facts do not change promotion.
  - Conflicting contract or interprocedural signals prevent confirmation.
```

### Pilot scores

- labels: baseline=useful_advisory enriched=useful_advisory
- confidence: 2 -> 4
- fp clarity: 3 -> 4
- why-not-confirmed understood: partial -> yes
- contract evidence: helped
- review minutes (est.): 1.27 -> 1.94
- missing for confirmation: interprocedural promotion gate evidence (currently not met), runtime or test proof of reachable inconsistent return path
