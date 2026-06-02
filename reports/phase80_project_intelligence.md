# Phase 80 — Project Intelligence Foundation

Date: 2026-05-30

## Goal

Read-only answers to builder questions about the JARVIS project itself, grounded in
repository evidence under `local_jarvis/` — never `FINAL_ALGO_TRADER`.

## Architecture

```
User question
  -> project_intelligence.routing.match_builder_question()  [deterministic, early in classify()]
  -> Intent.ANSWER_PROJECT_QUESTION
  -> ActionRegistry -> AnswerProjectQuestionAction
  -> project_intelligence.engine.answer_question()
       -> retrieval.gather_evidence()  [reports/, README*, brain/, tools/, git log]
       -> summarizer.format_answer()   [extractive, no LLM required]
```

### Package layout

| Module | Role |
|--------|------|
| `project_intelligence/routing.py` | Deterministic builder-question patterns |
| `project_intelligence/evidence.py` | JARVIS root, contamination guards |
| `project_intelligence/retrieval.py` | File + git evidence search |
| `project_intelligence/ranking.py` | Keyword scoring, question topics |
| `project_intelligence/summarizer.py` | Analyst-style extractive answers |
| `project_intelligence/engine.py` | Orchestrator |

### Tool

- `project.answer_question` — `READ_ONLY`, maps to `answer_project_question`

## Routing fix

Builder questions are matched **before** semantic reformulation and follow-up expansion.
When `SEMANTIC_UNDERSTANDING_ENABLED=true` and `LLM_CLASSIFIER_ENABLED=false`, rules now
win over semantic UNKNOWN (fixes prior bypass).

## Run JARVIS

```powershell
cd C:\J.A.R.V.I.S\local_jarvis
py -3 main.py
```

Example:

```
JARVIS> Why was Phase 73A built?
```

## Tests

```powershell
py -3 -m pytest tests/test_project_intelligence_questions.py -q
py -3 scripts/smoke_project_intelligence_questions.py
```

## Safety

- No tool execution beyond read-only file/git reads
- No browser, email, calendar, or autonomous dispatch
- Phase 79 shadow router unchanged
