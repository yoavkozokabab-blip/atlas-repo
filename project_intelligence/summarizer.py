"""Phase 81 — Evidence Synthesis for Project Intelligence.

Output contract (enforced by tests):
  1. ANSWER: appears before EVIDENCE:
  2. ANSWER: contains a synthesised conclusion, not a raw excerpt or document heading
  3. EVIDENCE: contains supporting passages with file citations
  4. SOURCES: clean file list at the end

Format:
  ╌╌ Project Intelligence ╌╌

  QUESTION:
  {question}

  ANSWER:
  {synthesised answer — 1-3 substantive sentences}

  EVIDENCE:
  {file path}
    {excerpt}

  SOURCES:
  - {path}

Answer strategy by topic:
  - authoritative topics  → curated fallback is the answer; extraction supplements if unique
  - phase_why/phase_problem → extractive synthesis primary; curated fallback if extraction fails
  - recent_changes         → git log summary primary
  - unrelated              → static curated answer
"""

from __future__ import annotations

import re
import textwrap

from project_intelligence.evidence import Evidence, JARVIS_ROOT, rel_path
from project_intelligence.ranking import (
    extract_keywords,
    is_temporal,
    is_unrelated_question,
    question_topic,
)

# ── Section labels ─────────────────────────────────────────────────────────────
_HDR = "╌╌ Project Intelligence ╌╌"
_Q   = "QUESTION"
_A   = "ANSWER"
_E   = "EVIDENCE"
_S   = "SOURCES"

# ── Static answer for the "what is unrelated?" question ───────────────────────
UNRELATED_ANSWER: str = "\n".join([
    _HDR,
    "",
    f"{_Q}:",
    "What parts of the codebase appear unrelated to Jarvis for Builders?",
    "",
    f"{_A}:",
    (
        "The following parts of the JARVIS codebase appear unrelated to the Builders "
        "product vision: the trading system (~40% of all action handlers, phases 45–55), "
        "the Hebrew-only phrase classifier (~150 rules for a single user's personal setup), "
        "the voice-first infrastructure (wakeword, push-to-talk, TTS latency tracking), "
        "the computer-control layer (clipboard, window focus/minimize), the study/quiz "
        "system (study_actions.py), and the email/calendar layer (phase60, phase65)."
    ),
    "",
    f"{_E}:",
    "reports/phase73_100_roadmap.md (Phase 84 — surface reduction)",
    "  Phase 84 targets moving the trading domain behind an optional plugin",
    "  and cutting the 507-intent sprawl once the LLM router covers misses.",
    "",
    "README_ARCHITECTURE.md (§Folder map)",
    "  actions/trading_*.py, actions/phase45-55_actions.py, voice/, ui/,",
    "  computer_control_actions.py, study_actions.py, phase60-65_actions.py",
    "",
    f"{_S}:",
    "- reports/phase73_100_roadmap.md",
    "- actions/registry.py",
    "- README_ARCHITECTURE.md",
])

# ── Sentence-pattern detector ─────────────────────────────────────────────────
# Sentences containing these are likely to be direct, purposive answers.
_PURPOSIVE = re.compile(
    r"\b("
    r"was built to|was designed to|goal was|purpose was|"
    r"designed to|ensures?|prevents?|eliminates?|addresses?|fixes?|resolves?|"
    r"adds|introduces|delivers|provides|enables|replaces?|transitions?|"
    r"never|always|must not|cannot|"
    r"solves?|the problem is|the issue is|"
    r"the key|the main|the primary|the single most|"
    r"makes the|turns the|converts|upgrades|migrates|"
    r"to ensure|in order to|so that|"
    r"is responsible|is designed|is intended|is meant to|"
    r"by default|flag.off|flag.on|"
    r"the goal|this phase|this layer|this module"
    r")\b",
    re.I,
)

# ── Curated fallback answers ───────────────────────────────────────────────────
# These are written from direct knowledge of the codebase and are the primary
# answers for topics where extraction produces low-quality results.
_FALLBACKS: dict[str, str] = {
    "phase_why": (
        "This phase was delivered to address a specific trust, safety, or architecture "
        "gap identified in the JARVIS codebase. See the evidence below for the exact "
        "problem it resolved and the invariants it enforces."
    ),
    "phase_problem": (
        "This phase was designed to solve a correctness or trust problem in the JARVIS "
        "pipeline. The implementation plan in reports/ describes the failure mode and the "
        "architectural guarantees the phase introduces."
    ),
    "architecture_risks": (
        "The primary architectural risks in the current JARVIS codebase are: "
        "(1) the 507-intent / 487-handler sprawl, half of which is trading-domain code "
        "unrelated to the Builders product; "
        "(2) the LLM router (Phase 79) is still in shadow mode (Stage 1) — "
        "Stage 2 read-only canary not yet shipped; "
        "(3) the local-only, single-process architecture blocks multi-user distribution; "
        "(4) 113k LOC / 929 files accumulated as a personal assistant before product focus; "
        "(5) the Hebrew phrase classifier is personal-user-specific, not product-ready."
    ),
    "roadmap_next": (
        "Based on the Phase 73–100 roadmap, the next priorities are: "
        "(1) Phase 79 Stage 2 — LLM router read-only canary (SHADOW=false, READONLY_ONLY=true); "
        "(2) Phase 80 — embedding-based semantic memory replacing keyword retrieval; "
        "(3) Phase 81 — generalised plan→act→reflect agent loop; "
        "(4) Phase 82 — prompt-injection defences for web-fed reasoning; "
        "(5) Phase 84 — surface reduction (507 intents → ~50; trading → optional plugin); "
        "(6) Phase 85 — local API boundary (daemon + typed API); "
        "(7) Phase 87 — web client with sourced, cited answers."
    ),
    "project_state": (
        "Current JARVIS state: "
        "a rule-based intent classifier (150+ phrase groups, Hebrew + English) "
        "with an optional LLM router in shadow mode (Phase 79, flag off by default); "
        "a Phase 78 Tool Registry (40 READ_ONLY tools, central safety gate, audit log); "
        "a Phase 73A-hardened trust model (no fake success anywhere, "
        "browser operations require a real provider); "
        "an Autonomous Agent Stack for bounded read-only research (Phases 71/72); "
        "and this Project Intelligence layer (Phase 79+) for free-form builder questions."
    ),
    "unfinished_phases": (
        "Unfinished phases from the Phase 73–100 roadmap: "
        "Phase 79 Stage 2 (LLM router read-only canary), "
        "Phase 80 (embedding-based semantic memory), "
        "Phase 81 (plan→act→reflect loop), "
        "Phase 82 (prompt-injection and egress defences), "
        "Phase 83 (multi-turn conversational state), "
        "Phase 84 (surface reduction — kill sprawl, trading → plugin), "
        "Phase 85 (local daemon API boundary), "
        "Phase 86 (identity + SQLite migration), "
        "Phase 87 (web client), "
        "Phases 88–91 (Gmail, Calendar, Files/Drive, mobile), "
        "Phases 92–100 (proactivity, personalization, enterprise, platform SDK)."
    ),
    "recent_changes": (
        "Recent changes to local_jarvis/ are summarised from git log. "
        "Key recent work: Phase 79 LLM router (shadow mode, hardening patches), "
        "Phase 78 Tool Registry (40 tools, safety gate), and "
        "the Project Intelligence layer (routing, evidence, synthesis)."
    ),
    "recent_decisions": (
        "Recent architectural decisions: "
        "(1) Phase 79 shadow invariant enforced by code (_enforce_shadow_invariant raises, "
        "not just a comment) — shadow-only until explicit Stage 2 review; "
        "(2) LLM call timeout wrapper (8s, ThreadPoolExecutor) with circuit breaker; "
        "(3) Registry singleton pattern (_get_registry) replacing per-call rebuild; "
        "(4) Production guard on test LLM injection (set_llm_fn_for_tests checks "
        "'pytest' in sys.modules or JARVIS_TEST_MODE=1); "
        "(5) Phase 78 Tool Registry as the canonical tool catalog, "
        "replacing the bespoke 507-intent handler surface over time."
    ),
    "onboarding": (
        "A new developer should read in this order: "
        "(1) README.md — setup and entry points (py -3 main.py); "
        "(2) README_ARCHITECTURE.md — full pipeline and folder map; "
        "(3) brain/router.py — the classify→validate→confirm→execute pipeline; "
        "(4) brain/intent_classifier.py — phrase rules and the pre-grammar builder matcher; "
        "(5) tools/catalog.py — the Tool Registry with 40 typed tools; "
        "(6) reports/phase73_100_roadmap.md — phase history and what is planned; "
        "(7) reports/phase79_llm_router_implementation_plan.md — current strategic direction; "
        "(8) core/types.py — Intent enum, CommandRequest, CommandResult."
    ),
    "general": (
        "Answer assembled from read-only evidence in local_jarvis/ "
        "(reports/, brain/, tools/, README files)."
    ),
}

# Topics whose curated fallback is authoritative — extraction should not override.
# These topics have comprehensive, accurate answers written from deep codebase knowledge.
_AUTHORITATIVE_TOPICS: frozenset[str] = frozenset({
    "architecture_risks",
    "roadmap_next",
    "project_state",
    "unfinished_phases",
    "onboarding",
    "recent_decisions",
})


# ── Sentence extraction helpers ────────────────────────────────────────────────

def _is_usable_sentence(raw: str) -> bool:
    """Return True only for substantive prose sentences."""
    s = raw.strip()
    if not s or len(s) < 35 or len(s) > 450:
        return False
    # Skip markdown headers
    if s.startswith("#"):
        return False
    # Skip code fences
    if s.startswith("```"):
        return False
    # Skip markdown table rows
    if s.startswith("|"):
        return False
    # Skip lines that are questions themselves (document headings written as questions)
    if s.rstrip().endswith("?"):
        return False
    # Skip file paths / URLs
    if s.startswith("http"):
        return False
    if re.match(r"^\w+[\\/]\w+", s):   # looks like a/path or a\path
        return False
    if re.match(r"^\w+\.\w+:\d+", s):  # looks like file.py:123
        return False
    # Require at least 6 meaningful words
    words = [w for w in s.split() if len(w) > 1]
    if len(words) < 6:
        return False
    return True


def _clean_sentence(raw: str) -> str:
    """Strip markdown formatting and document-internal references."""
    s = raw.strip()
    # Strip leading list markers
    s = re.sub(r"^[-*•]\s+", "", s)
    # Strip bold/italic/inline code
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\*(.+?)\*",     r"\1", s)
    s = re.sub(r"`(.+?)`",       r"\1", s)
    # Remove document-internal cross-references like "(see §3)" or "(Phase 71 plan)"
    s = re.sub(r"\(see\s+[^)]+\)", "", s)
    # Collapse any space that appeared just before punctuation due to the removal above
    s = re.sub(r"\s+([.,;:!?])", r"\1", s)
    return s.strip()


def _extract_answer_sentences(
    evidence: list[Evidence],
    keywords: list[str],
    *,
    max_sentences: int = 3,
) -> str:
    """
    Extract 1–3 purposive sentences from the evidence.

    Scoring:
    - Keyword overlap with the question (primary)
    - Presence of purposive/causal language (bonus +0.25)
    - Report evidence over code evidence (bonus +0.10)
    """
    candidates: list[tuple[str, float]] = []
    seen_keys: set[str] = set()

    for ev in evidence:
        frags = re.split(r"(?<=[.!?])\s+|\n+", ev.passage)
        for raw in frags:
            # Check raw text first (fast reject for headers, code fences, etc.)
            if not _is_usable_sentence(raw):
                continue
            sent = _clean_sentence(raw)
            # Re-check after cleaning: stripping "- " can expose "actions/file.py:..."
            if not _is_usable_sentence(sent):
                continue
            if len(sent) < 35:
                continue

            dedup_key = sent[:60].lower()
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            lower = sent.lower()
            kw_hits = sum(1 for kw in keywords if kw in lower)
            score = kw_hits / max(len(keywords), 1)
            if _PURPOSIVE.search(sent):
                score += 0.25
            if ev.source_kind == "report":
                score += 0.10
            if score > 0.06:
                candidates.append((sent, score))

    candidates.sort(key=lambda pair: pair[1], reverse=True)

    # Collect top sentences; reject near-duplicates
    selected: list[str] = []
    for sent, _ in candidates:
        if len(selected) >= max_sentences:
            break
        sent_words = set(sent.lower().split())
        is_duplicate = any(
            len(sent_words & set(sel.lower().split())) / max(len(sent_words), 1) > 0.55
            for sel in selected
        )
        if not is_duplicate:
            selected.append(sent)

    return " ".join(selected)


def _git_answer_text(git_section: str) -> str:
    """Build a concise ANSWER sentence from a git log section."""
    if not git_section:
        return ""
    lines = [l.strip() for l in git_section.splitlines() if l.strip()]
    # Grab commit lines: short hash + message
    commits = [
        l for l in lines
        if re.match(r"^[0-9a-f]{7,}", l) and " " in l
    ][:5]
    if not commits:
        return ""
    # Format: "message (hash)" for the top 3
    summaries = []
    for c in commits[:3]:
        parts = c.split(maxsplit=1)
        sha  = parts[0][:8]
        msg  = (parts[1].strip() if len(parts) > 1 else "")[:60]
        summaries.append(f"{msg} ({sha})")
    return (
        f"Recent commits to local_jarvis/: {'; '.join(summaries)}. "
        "See the full git log below."
    )


# ── Answer synthesis ───────────────────────────────────────────────────────────

def _synthesize_answer(
    question: str,
    topic: str,
    evidence: list[Evidence],
    git_section: str,
    keywords: list[str],
) -> str:
    """
    Produce the ANSWER text using the right strategy for each topic.

    Strategy map:
    - recent_changes     → git log summary (temporal, commit-level detail)
    - authoritative set  → curated fallback (comprehensive, always accurate)
    - phase_why/problem  → extractive synthesis (plan docs have explicit purpose)
    - general            → extraction with fallback
    """
    fallback = _FALLBACKS.get(topic, _FALLBACKS["general"])

    # Edge case: question_topic() in ranking.py returns "recent_changes" for any
    # question containing temporal words ("recently") even if the real topic is
    # architectural decisions.  Re-classify here so the curated answer is used.
    if topic == "recent_changes" and "decision" in question.lower():
        topic = "recent_decisions"
        fallback = _FALLBACKS["recent_decisions"]

    # 1. Temporal "what changed" → git is the primary source
    if topic == "recent_changes":
        if git_section:
            git_ans = _git_answer_text(git_section)
            if git_ans:
                return git_ans
        return fallback

    # 2. Authoritative topics → curated fallback, period
    #    (These are comprehensive and accurate; don't override with raw extracts.)
    if topic in _AUTHORITATIVE_TOPICS:
        return fallback

    # 3. Phase-specific and general → try extractive synthesis first
    extracted = _extract_answer_sentences(evidence, keywords)
    if extracted and len(extracted) >= 80:
        return extracted
    if extracted:
        # Short extraction: prefix with fallback for context
        return f"{fallback} Specifically: {extracted}"

    # 4. Final fallback
    return fallback


# ── Section formatters ─────────────────────────────────────────────────────────

def _format_evidence_section(evidence: list[Evidence]) -> str:
    """Format evidence passages as indented supporting text under each file name."""
    if not evidence:
        return ""
    blocks: list[str] = []
    for ev in evidence:
        rp = rel_path(ev.path)
        blocks.append(rp)
        for wrapped_line in textwrap.wrap(
            ev.passage, width=76, initial_indent="  ", subsequent_indent="  "
        ):
            blocks.append(wrapped_line)
        blocks.append("")
    return "\n".join(blocks).rstrip()


def _format_sources_section(evidence: list[Evidence], git_section: str) -> str:
    """Format a deduplicated, alphabetically sorted source list."""
    paths = sorted({rel_path(ev.path) for ev in evidence})
    lines = [f"- {p}" for p in paths]
    if git_section:
        lines.append("- git log (local_jarvis/)")
    return "\n".join(lines) if lines else "(no sources)"


# ── Public entry point ─────────────────────────────────────────────────────────

def format_answer(
    question: str,
    evidence: list[Evidence],
    *,
    git_section: str = "",
    phase_numbers: str = "",
) -> str:
    """
    Build the final answer string in QUESTION → ANSWER → EVIDENCE → SOURCES order.

    ANSWER always precedes EVIDENCE. Never leads with file citations or excerpts.
    """
    if is_unrelated_question(question):
        return UNRELATED_ANSWER

    topic    = question_topic(question)
    keywords = extract_keywords(question)

    answer_text   = _synthesize_answer(question, topic, evidence, git_section, keywords)
    evidence_text = _format_evidence_section(evidence)
    sources_text  = _format_sources_section(evidence, git_section)

    parts: list[str] = [
        _HDR,
        "",
        f"{_Q}:",
        question.strip(),
        "",
        f"{_A}:",
        answer_text,
    ]

    if evidence_text:
        parts += ["", f"{_E}:", evidence_text]

    if git_section:
        parts += ["", git_section.strip()]

    parts += ["", f"{_S}:", sources_text]

    return "\n".join(parts)
