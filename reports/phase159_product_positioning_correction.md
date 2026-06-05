# Phase 159 — Product Positioning Correction

**Date:** 2026-06-05  
**Role:** Strategic product critic  
**Evidence used:** Phase 113, 118, 132, 139, 140, 146B, 147, 152, 152B, 153, 154, 155, 157A, 158, 158A  
**No code changes. No website changes. Planning only.**

---

## 1. What Does Atlas Truly Do Well Today?

### PROVEN (evidence-backed, observable in tests or live runs)

| Capability | Evidence | Metric |
|---|---|---|
| Repository scanning and graph construction (Python, TypeScript) | Phase 152B: 22/23 repos measured | FastAPI: 73 modules / 159 edges in 2.1s; Django: 929/2915 |
| Context compression: reducing AI token usage | Phase 152B: avg 99.89% reduction | 22 repos: ~300–700 token compact vs millions raw |
| Windows installer and packaged .exe | Phase 152, 154: Atlas.exe works without Python | Install validated, server reachable |
| Demo path: scan → change plan → export in < 2 minutes | Phase 155: 20 tests passing | Happy path confirmed on sample repo |
| Dependency edge resolution for Python/TypeScript | Phase 152B: best repos 85–92.5 score | TypeORM: 2735 edges; Airflow: 835 edges |
| EMA/trading concept suppression (Phase 158 fix) | Phase 158: 71 new tests passing | live: domain=messaging for duplicate-events |
| Impact: ok=False on unresolved targets (Phase 158) | Phase 158: target_not_resolved | No more fake ok=True |
| Graph health honest for unsupported languages (Phase 158) | Phase 158: unsupported_language_limited | Kubernetes 24860/3 → not healthy |

### LIKELY (consistent but not externally validated)

| Capability | Evidence |
|---|---|
| Change Plan produces useful starting point for Python/TypeScript changes | Phase 132 benchmark: mean 86.3, phase 158A: ~0 wrong |
| Investigation routes correctly to relevant subsystem area | Phase 147 UX audit: 55–65% success; Phase 158A: no trading leakage |
| Impact analysis identifies direct importers | Phase 132: Impact 94.0 score on benchmark |
| Local-first: no source leaves the machine | Phase 146B: local feedback confirmed; export is user-driven |

### UNPROVEN (claimed but not independently validated)

| Claim | Status | Why it's uncertain |
|---|---|---|
| Change plans are correct (right files, right order) | Unproven | Phase 157A: 0/50 Build Plans classified "correct" |
| Investigation finds the actual root cause | Unproven | Phase 157A: 0/50 Investigations "correct"; 6 misleading |
| Impact analysis is accurate for the specified change | Partial proof | Phase 157A: 12/50 correct; 5 wrong |
| Atlas "understands" the codebase | Misleading framing | Atlas maps structure, not semantics |
| Works well on all Python repos | Overstated | unresolved_import_explosion on 6/23 repos |
| Architecture-aware | Partial | Subsystem detection via path heuristics, not semantic analysis |

---

## 2. What Does Atlas Not Do Well?

### Hard limitations (fundamental, not fixable with a sprint)

- **No semantic understanding.** Atlas reads file paths, import edges, and symbol names. It does not parse logic, understand algorithm intent, or reason about behavior. "Understanding" means "has the file path and knows who imports it."
- **No code execution.** Atlas cannot run the code, reproduce bugs, or verify hypotheses.
- **No automatic fixes.** Atlas produces plans and packets — the user must implement.
- **Investigation: 0 confirmed root causes.** Phase 157A: 0 correct, 44 partial, 6 misleading from 50 investigations. Hypotheses are plausible structural leads, not confirmed defects.
- **Build Plan: 0 confirmed correct implementations.** Phase 157A: 0 correct, 46 partial from 50 build plans. Plans direct you toward the right area; they do not give you the right implementation.

### Language support gaps

| Language | Phase 152B score | Notes |
|---|---|---|
| Python | 78.31 avg, best 92.5 | Strong |
| TypeScript | 85.75 avg | Strong |
| Rust | 81.25 | Partial (qdrant: unresolved explosion) |
| Go | 66.0 avg | Weak; gin/kubernetes empty graphs |
| Java | 61.0 | Very weak; spring_boot: 0 modules |
| C# | 72.25 | Limited; aspnet: language_support_gap |

### Evidence quality gaps

- **Evidence quality dimension: 56.0/100** (Phase 132 benchmark — lowest dimension)
- **Investigation file precision: 0.30** — Atlas surfaces 3x more files than relevant
- **5 feature scenarios miss insertion point** (feat_003/006/011/013/019)
- **unresolved_import_explosion on 6/23 repos** — Django, Airflow, VS Code, Pydantic, LangChain, Kubernetes

### Operational gaps

- Atlas does not find bugs. It finds the structural area where a bug is likely.
- Atlas does not find security vulnerabilities. It flags high fan-in coupling.
- Atlas does not tell you what's wrong with your code. It tells you where to look.

---

## 3. What Must NOT Be Claimed on the Website

These claims are explicitly prohibited by the evidence:

| Banned claim | Why |
|---|---|
| "Understands every codebase" | Phase 152B: 5 repos with empty graphs; language gaps in Go/Java/C# |
| "Finds bugs" | Phase 157A: 0 correct investigations; only structural leads |
| "Replaces architects" | Atlas produces heuristic plans, not architectural judgment |
| "Fully accurate" / "accurate results" | Phase 157A: trust score 45.8/100 before Phase 158 |
| "Works on all languages" | Phase 152B: Go 66, Java 61, C# 72 — explicit gaps |
| "Understands your code" | Atlas understands file paths and import relationships |
| "Knows your codebase" | Same — structural knowledge, not behavioral |
| "AI that helps you implement" | Atlas plans; the developer implements using their AI tool |
| "99.9% token savings" (old claim) | Phase 118 removed this; must stay removed |
| "Always finds the root cause" | 0/50 root causes confirmed in Phase 157A |
| "Automatically fixes code" | Never true; no code execution |
| "Enterprise-ready" | Clean-VM install unproven; no signing at scale |
| "Works with any AI coding tool" | Only Claude/Cursor/Codex have copy-paste export; others untested |

---

## 4. What CAN Be Claimed Safely (Evidence-Backed)

| Safe claim | Evidence | Notes |
|---|---|---|
| "Maps your Python/TypeScript repository structure locally" | Phase 152B: 22/23 repos scanned | Qualify language scope |
| "Generates architecture-aware context prompts for Claude, Cursor, and Codex" | Phase 155: export confirmed | Specific tools only |
| "Reduces the tokens you send to AI by compressing repository context" | Phase 152B: avg 99.89% reduction | Honest caveat: compact packet, not full repo |
| "Shows which files would likely be affected by a change" | Phase 132: Impact 94.0 | Qualify: "likely", not "certain" |
| "Helps plan changes before you ask AI to implement them" | Phase 132, 158A | Change Plan is a starting point |
| "Identifies high-coupling files in your repository" | Phase 132: risk engine | Risk scores are heuristic |
| "Runs locally — your source code never leaves your machine" | Phase 146B, 155 | Confirmed |
| "No Python required to install on Windows" | Phase 152: Atlas.exe | Windows only currently |
| "Works on repositories up to VS Code scale (7,500+ modules)" | Phase 152B | Qualify: TypeScript only at that scale |
| "Scans fast: FastAPI in 2.1s, Django in 14s" | Phase 116G, 152B | Verified benchmarks |
| "Surfaces likely impact areas when changing a file" | Phase 132 Impact 94 | Not guaranteed, not defect-confirmed |
| "Private beta for Windows developers using Python or TypeScript" | Phase 153, 155 | Honest scope |

---

## 5. Who Is the Real ICP Right Now?

**Ranked from best fit to worst:**

### Tier 1 — Best fit (use Atlas today)

1. **Senior engineers working on large Python/TypeScript repositories (>10,000 LOC)**
   - They understand that plans are starting points, not implementations
   - They can evaluate whether a Change Plan makes sense
   - Large repos hurt them most in AI context windows — highest token-savings value
   
2. **AI coding tool power users (Claude/Codex/Cursor daily drivers)**
   - Already understand the paste-context workflow
   - Have a mental model of "Atlas gives me context, AI gives me code"
   - Can detect when a plan is off and know to ask for a narrower scope

### Tier 2 — Good fit with caveats

3. **Startup engineers with growing Python/TypeScript codebases**
   - Value is clear if they already feel the "too large for context window" pain
   - May expect more precision than Atlas delivers — expectation management needed
   
4. **Open-source maintainers (Python/TypeScript)**
   - Single-person codebases; Atlas finds coupling they forgot about
   - Must understand Atlas does not review PRs or find security issues

### Tier 3 — Poor fit (not yet)

5. **Tech leads managing multi-language repos** — Atlas only helps with the Python/TypeScript portions
6. **Students** — benefit is unclear without large complex repos; may expect an AI that writes code
7. **Non-technical users** — Atlas produces technical output (file paths, subsystems); not consumer-friendly
8. **Engineering managers** — Atlas produces developer artifacts, not executive dashboards

---

## 6. Who Should NOT Use Atlas Yet?

**Be direct:**

- **Developers on Go, Java, C#, Rust repos** — Phase 152B: graphs are empty or near-empty for these languages. Atlas will produce weak plans. The honest answer is: not yet.
- **Developers expecting Atlas to find bugs** — Atlas does not. It finds likely structural areas. If you need a bug confirmed, Atlas is a starting point, not an answer.
- **Developers expecting automatic code changes** — Atlas plans. It does not implement.
- **Mac/Linux developers** — Phase 152: Windows installer only. Python launcher path exists but is undocumented for beta.
- **Developers with monorepos >1M LOC without scoped scanning** — Home Assistant at 494s, Atlas self at timeout. Very large repos need manual scope narrowing.
- **Teams that need audit-grade security analysis** — Atlas is not a security tool. High fan-in flags are heuristic coupling warnings, not CVE detection.

---

## 7. How Should Atlas Be Positioned?

### Evaluated options:

| Positioning | Honest? | Compelling? | Verdict |
|---|---|---|---|
| "Repository Intelligence Layer" | Partially (implies more intelligence than exists) | High | Risky |
| "Context Engine for AI Coding Tools" | Yes | Medium-High | Safe |
| "Architecture-Aware Prompt Generator" | Yes (literal) | Low | Too technical |
| "AI Software Architect Assistant" | No (implies judgment Atlas doesn't have) | High | Banned |
| "Repository Map for AI Tools" | Yes | Medium | Safe |

**Recommended positioning: "Context Engine for AI Coding Tools"**

Why this works:
- "Context Engine" is accurate — Atlas compresses repository context
- "for AI Coding Tools" — honest; Atlas serves Claude, Cursor, and Codex
- Does not claim Atlas understands, architects, or implements
- Engineers immediately understand the workflow: map repo → feed context → AI implements

---

## 8. Rewrite: One-Line Pitch

**Current (unsafe):**
> "Give Claude, Codex and Cursor architectural understanding in minutes."

**Why unsafe:** "Architectural understanding" implies Atlas reasons about architecture. It maps structure.

**Recommended:**
> "Stop sending your whole repository to AI. Atlas maps it first."

**Why this works:**
- Opens with the pain (whole-repo context burn)
- States the action (maps it)
- Does not claim to understand, implement, or fix
- Works for Claude, Codex, Cursor, and any future tool

**Alternative (more specific):**
> "Atlas maps your repository and builds the context your AI coding tool actually needs."

---

## 9. Rewrite: Website Hero

**Current hero text (unsafe):**
> "Stop making AI read your entire repository."
> "Give Claude, Codex and Cursor architectural understanding in minutes — without burning tokens on file-by-file context scanning."

**Issue:** "Architectural understanding" overpromises. Also "in minutes" may not hold for large repos.

**Recommended hero:**

```
HEADLINE:
Your AI coding tool reads better with a map.

SUBHEADLINE:
Atlas scans your Python or TypeScript repository locally,
builds a dependency map, and generates a compact context packet
you paste into Claude, Cursor, or Codex before asking it to implement.

Your code never leaves your machine.
```

**Why this is honest and compelling:**
- "reads better with a map" — metaphor, accurate, not a false capability claim
- "scans your Python or TypeScript repository" — explicit language scope
- "builds a dependency map" — accurate, not "understands"
- "compact context packet you paste" — describes the actual workflow
- "Your code never leaves your machine" — the strongest trust claim, verified

**Verified metrics to add below hero (Phase 116G / 152B):**
- FastAPI: 73 modules, 2.1s scan, 325 token export vs 956,323 raw
- Django: 929 modules, 14.3s scan, 385 token export vs 4,842,875 raw
- VS Code: 7,551 modules, 6.4s scan (TypeScript)

Label: *"Internal benchmarks on real open-source repositories."*

---

## 10. Rewrite: Private Beta Disclaimer

**Current (Phase 118/139):**
> "Atlas is entering a limited external beta"
> "Planning only — does not write code"

**Issues:**
- "Planning only" appears too late and reads like a legal disclaimer
- Users may still expect automated suggestions or AI-generated diffs

**Recommended disclaimer (short, honest, first screen):**

```
PRIVATE BETA DISCLAIMER

Atlas is a repository mapping and planning tool.

It does:
- Scan your local Python or TypeScript repository
- Build a dependency and impact map
- Generate a context packet you can paste into Claude, Cursor, or Codex
- Show likely affected files for a planned change

It does NOT:
- Write or apply code on your behalf
- Find or confirm specific bugs
- Guarantee the plan is correct for your change
- Support Go, Java, C#, or Rust with full graph coverage

Start with the sample repository before scanning your own code.
```

---

## Summary: Current Positioning Risk

**Current risk level: HIGH**

The existing website and beta messaging claims language-agnostic support, architectural understanding,
and implicit defect detection. Phase 157A shows trust score 45.8/100 — and Phase 158A estimates
63/100 post-hardening. The gap between what's claimed and what's delivered is a reputational risk
once beta users encounter it.

**Corrected positioning reduces risk by:**

1. Explicitly naming Python and TypeScript as supported languages
2. Removing "understands" in favor of "maps" and "generates context"
3. Making the "plans only, does not implement" message the first thing users see
4. Leading with token compression (proven) over architecture intelligence (partial)
5. Adding honest language support disclaimers before users invest time in the product

**Immediate actions (no code, no redesign):**
- Update `support.html` disclaimer section with the beta disclaimer text above
- Update `quickstart.html` to say "Python and TypeScript repositories" explicitly
- Remove "architectural understanding" from any remaining copy
- Add "Plans only — does not implement" as the first sentence of the Welcome overlay

**Banned phrases in all Atlas copy (effective immediately):**
- "understands your codebase"
- "architectural understanding"
- "finds bugs"
- "works on all languages"
- "fully accurate"
- "knows your code"
- "replaces architects"
- any variant of "automatically fixes"
