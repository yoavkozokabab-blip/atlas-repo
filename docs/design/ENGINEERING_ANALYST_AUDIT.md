# Atlas Engineering Analyst Audit

Date: 2026-07-12

Branch: `design/atlas-premium-experience`

## Product standard

Atlas is a software engineering investigation system. The interface should imply that repository evidence was scoped, resolved, ranked, and reviewed before a conclusion appears.

The interaction model is:

1. Define the engineering problem.
2. Resolve repository evidence.
3. Present findings and uncertainty.
4. Recommend a bounded next action.

Conversation is not the organizing metaphor. The product uses briefs, investigations, reports, evidence, findings, hypotheses, impact paths, plans, and handoffs.

## Screen audit

| Screen | Chat-like pattern found | Engineering investigation replacement | Status |
| --- | --- | --- | --- |
| Authentication | None; already an operational access surface | Preserve account and Local-mode hierarchy | Complete |
| Home, no repository | Feature/agent marketing could compete with the next action | Repository evidence preparation: Scan or sample only | Complete |
| Home, repository ready | “Ask Atlas now” implied a chatbot entry point | Open repository analysis; retain measured readiness facts | Complete |
| Home, productive | Conversational headline and Ask input | Start an engineering investigation; engineering question; Run analysis | Complete |
| HN demo | “Ask Atlas” and “See answer” framing | Run analysis and inspect evidence | Complete |
| Repository scan | Onboarding hero and anthropomorphic success language | Repository indexing and evidence preparation | Complete |
| Ask route | Ask/Send/question/follow-up framing | Repository Analysis; investigation brief; Run analysis; Refine analysis | Complete |
| Ask loading | “Understanding” and generic AI-thinking language | Scoping investigation; resolving evidence; assembling report | Complete |
| Ask empty state | Prompt playground and capability chips | Investigation templates organized by engineering job | Complete |
| Ask result | Chat answer with action row | Executive report, verdict, evidence, files, unknowns, recommendation | Complete |
| Architecture Map | “Ask about this repo” side card | Analyze selection using cited architecture evidence | Complete |
| Plan Change | Conversational request field and generic Create plan | Implementation Plan workspace with a change brief | Complete |
| Debug | “What is going wrong?” and Analyze symptom | Failure Investigation with observed failure and ranked hypotheses | Complete |
| Impact | “What breaks?” conversational framing | Change Impact with a concrete target and dependency analysis | Complete |
| Context export | Prompt/export playground | Agent Handoff evidence package | Complete |
| Agent copy panels | “Paste once per new chat” | Bounded engineering handoff for the responsible coding agent | Complete |
| Account status | None; already operational | Preserve status, reason, and actions | Complete |
| Account profile | None; already operational | Preserve account/device management | Complete |
| Admin | None; already resembles an operations console | Preserve tables, filters, audit log, and explicit actions | Complete |

## Visual system changes

- Workspaces use one editorial header, one bounded input tool, and an unframed report area.
- Suggested investigations are rows with explicit Run affordances, not chat chips.
- Plan, failure, and impact outputs share report rhythm: hairline sections, evidence labels, monospace paths, and restrained status color.
- The architecture graph remains the primary canvas; surrounding panels and analysis CTA are quieter.
- Agent handoff remains a real export tool and no longer describes a “new chat.”
- Loading communicates repository work phases rather than simulated human thinking.
- Internal route names, endpoint names, and compatibility IDs remain unchanged.

## Handler and architecture boundary

The redesign preserves:

- `/api/copilot/ask` and the current response shape
- `sendCopilotQuestion()`
- `runChangePlan()`
- `runInvestigationPlan()`
- `runImpact()`
- graph and module-inspector handlers
- repository scan and persistence behavior
- MCP configuration handlers
- account, billing, admin, and release behavior

The terms `copilot` and `ask` may remain in internal IDs and route contracts. They are implementation compatibility names, not visible product metaphors.

## Remaining constraints

- Evidence signals do not always provide structured file/symbol/line fields. The UI shows only fields present in the response.
- “Copy path” remains a clipboard action because Atlas has no editor-open backend contract.
- The 3D graph retains some visual glow because it encodes graph state; surrounding operational chrome does not.
- A later architecture migration may rename internal Copilot symbols, but that is intentionally outside this presentation pass.
