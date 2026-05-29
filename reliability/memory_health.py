"""Phase 65 Track B — memory reliability."""

from __future__ import annotations

from datetime import datetime, timezone

from reliability.hardening_core import TrackScore, format_track_report, reports_dir, run_case, write_report


def _diagnostics() -> dict[str, int | list[str]]:
    from memory.store import get_personal_memory

    store = get_personal_memory()
    data = store._load()
    entries = data.get("entries", [])
    visible = store.list_visible(limit=500)
    text_buckets: dict[str, int] = {}
    contradictions: list[str] = []
    stale = 0
    now = datetime.now(timezone.utc)
    for row in entries:
        if row.get("hidden"):
            continue
        t = str(row.get("text") or "").strip().lower()
        if t in text_buckets:
            text_buckets[t] += 1
        else:
            text_buckets[t] = 1
        exp = str(row.get("expires_at") or "").strip()
        if exp:
            try:
                if datetime.fromisoformat(exp) <= now:
                    stale += 1
            except ValueError:
                pass
    dupes = [k for k, v in text_buckets.items() if v > 1]
    try:
        from memory.semantic_runtime import _load

        sem = _load()
        contradictions = [str(x) for x in sem.get("graph", {}).get("contradictions", [])][:10]
    except Exception:
        pass
    return {
        "total": len(entries),
        "visible": len(visible),
        "duplicates": len(dupes),
        "stale": stale,
        "contradictions": contradictions,
    }


def show_memory_ranking_diagnostics() -> str:
    diag = _diagnostics()
    lines = [
        "Memory ranking diagnostics:",
        f"  total_entries: {diag['total']}",
        f"  visible_entries: {diag['visible']}",
        f"  duplicate_text_buckets: {diag['duplicates']}",
        f"  stale_entries: {diag['stale']}",
        f"  contradictions: {len(diag['contradictions'])}",
    ]
    for c in diag["contradictions"][:5]:
        lines.append(f"    - {c[:160]}")
    return "\n".join(lines)


def run_memory_acceptance() -> TrackScore:
    score = TrackScore(track="Memory", current_pct=0.0, target_pct=85.0)
    from memory.store import get_personal_memory

    store = get_personal_memory()
    tag = f"phase65_{int(datetime.now(timezone.utc).timestamp())}"

    def _remember() -> tuple[bool, str]:
        entry = store.remember(f"phase65 test {tag}", category="session", tags=["phase65"], ttl_seconds=3600)
        return bool(entry.entry_id), entry.entry_id

    remembered_id = ""

    def _remember_capture() -> tuple[bool, str]:
        nonlocal remembered_id
        ok, detail = _remember()
        remembered_id = detail
        return ok, detail

    def _retrieve() -> tuple[bool, str]:
        hits = store.search_memory(tag)
        return len(hits) > 0, f"hits={len(hits)}"

    def _semantic() -> tuple[bool, str]:
        # T-5 fix: len() >= 0 is a tautology; require at least one hit.
        hits = store.semantic_search(tag, limit=3)
        return len(hits) > 0, f"semantic_hits={len(hits)}"

    def _update() -> tuple[bool, str]:
        # T-6 fix: verify the update is actually retrievable, not hardcoded True.
        store.remember(
            f"phase65 test {tag} updated",
            category="session",
            tags=["phase65", remembered_id],
        )
        hits = store.search_memory(f"{tag} updated")
        ok = len(hits) > 0
        return ok, f"update_retrievable={ok} hits={len(hits)}"

    def _forget() -> tuple[bool, str]:
        # T-7 fix: n >= 0 is a tautology; require at least one entry was hidden.
        n = store.forget(tag)
        return n > 0, f"hidden={n}"

    def _stale_entries() -> tuple[bool, str]:
        # T-8 fix: check stale (expired) entries count rather than hardcoding True.
        # vacuum() runs at startup; stale should be low after a cold start.
        d = _diagnostics()
        stale = d["stale"]
        ok = stale < 50  # tolerate a small backlog between vacuum runs
        return ok, f"stale_entries={stale} duplicates={d['duplicates']}"

    def _ranking_diagnostics() -> tuple[bool, str]:
        # T-9 fix: actually call diagnostics and verify it returns a non-empty report.
        report = show_memory_ranking_diagnostics()
        return bool(report), report[:120]

    score.cases.extend(
        [
            run_case("remember", _remember_capture),
            run_case("retrieve", _retrieve),
            run_case("semantic_retrieve", _semantic),
            run_case("update", _update),
            run_case("forget", _forget),
            run_case("stale_entries", _stale_entries),
            run_case("ranking_diagnostics", _ranking_diagnostics),
        ]
    )
    score.finalize_score()
    retrieval_cases = [c for c in score.cases if c.name in {"retrieve", "semantic_retrieve"}]
    retrieval_rate = 100.0 * sum(1 for c in retrieval_cases if c.passed) / max(1, len(retrieval_cases))
    if retrieval_rate < 90:
        score.blockers.append("Retrieval pass rate below 90% target.")
        score.recommendations.append("Run repair memory store and re-index semantic vectors.")
    write_report(
        reports_dir() / "memory_reliability_report.md",
        format_track_report(score, extra_sections=[show_memory_ranking_diagnostics()]).splitlines(),
    )
    return score
