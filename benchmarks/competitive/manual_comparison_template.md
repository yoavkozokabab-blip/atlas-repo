# Phase 130 — Manual competitive evaluation template

Use this template to compare **Atlas** vs **Claude Code** vs **Cursor** on the same benchmark prompt.
No API integration — paste each assistant's output and score manually.

## Scenario

| Field | Value |
|-------|-------|
| Repository | |
| Scenario ID | |
| Prompt | |
| Category | feature_addition / bug_investigation / impact_analysis |

## Scoring rubric (0–10 each)

| Dimension | Atlas | Claude Code | Cursor | Notes |
|-----------|-------|-------------|--------|-------|
| File precision | | | | recommended files that match ground truth |
| File recall | | | | expected files found |
| Insertion point | | | | correct module/symbol for change |
| Concept accuracy | | | | correct domain concept |
| Evidence quality | | | | claims backed by repo facts |
| Risk identification | | | | major risks named |
| Test suggestions | | | | relevant tests listed |

## Paste outputs

### Atlas (automated)

```
(paste Build Plan / Investigate / Impact output)
```

### Claude Code (manual)

```
(paste)
```

### Cursor (manual)

```
(paste)
```

## Where Atlas loses

| Gap | Example | Priority |
|-----|---------|----------|
| | | P0 / P1 / P2 |

## Where Atlas wins

| Advantage | Example |
|-----------|---------|
| | |
