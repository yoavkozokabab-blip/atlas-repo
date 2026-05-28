"""Static product audit for the JARVIS marketing site (read-only)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_WEBSITE_ROOT = Path(r"C:\jarvis website")

ROUTE_SPECS: tuple[tuple[str, str, str], ...] = (
    ("/", "src/app/page.tsx", "Marketing home"),
    ("/demo", "src/app/demo/page.tsx", "Live demo console"),
    ("/dashboard", "src/app/dashboard/page.tsx", "Mission control (auth)"),
    ("/voice", "src/app/voice/page.tsx", "Voice runtime (auth)"),
    ("/pricing", "src/app/pricing/page.tsx", "Pricing"),
    ("/login", "src/app/login/page.tsx", "Login"),
    ("/register", "src/app/register/page.tsx", "Register"),
    ("/onboarding", "src/app/onboarding/page.tsx", "Onboarding wizard"),
)


@dataclass(frozen=True)
class AuditFinding:
    severity: str
    category: str
    title: str
    detail: str
    files: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()


@dataclass
class RouteScan:
    route: str
    label: str
    page_path: str
    exists: bool
    notes: list[str] = field(default_factory=list)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def _scan_routes(root: Path) -> list[RouteScan]:
    rows: list[RouteScan] = []
    for route, rel_page, label in ROUTE_SPECS:
        page = root / rel_page
        notes: list[str] = []
        exists = page.is_file()
        if exists:
            text = _read(page)
            if "metadata" in text:
                notes.append("has page metadata")
            if '"use client"' in text or "'use client'" in text:
                notes.append("client component entry")
        rows.append(
            RouteScan(
                route=route,
                label=label,
                page_path=rel_page,
                exists=exists,
                notes=notes,
            )
        )
    return rows


def _extract_hrefs(text: str) -> set[str]:
    return set(re.findall(r'href=["\']([^"\']+)["\']', text))


def _nav_audit(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    header = _read(root / "src/components/layout/site-header.tsx")
    footer = _read(root / "src/components/layout/site-footer.tsx")
    header_hrefs = _extract_hrefs(header)
    footer_hrefs = _extract_hrefs(footer)
    expected_public = {"/", "/demo", "/dashboard", "/voice", "/pricing", "/login", "/register"}

    if "/onboarding" not in header_hrefs and "/onboarding" not in footer_hrefs:
        findings.append(
            AuditFinding(
                severity="high",
                category="navigation",
                title="Onboarding route not linked in global chrome",
                detail=(
                    "Middleware gates /dashboard and /voice on onboarding completion, but "
                    "/onboarding is only reached via redirect — not discoverable from header/footer."
                ),
                files=("src/components/layout/site-header.tsx", "src/components/layout/site-footer.tsx"),
                suggestions=(
                    "Add a post-login onboarding entry or progress chip in header when session exists but onboarding incomplete.",
                    "Document the flow on /register success screen.",
                ),
            )
        )

    if "/voice" not in footer_hrefs:
        findings.append(
            AuditFinding(
                severity="medium",
                category="navigation",
                title="Footer omits Voice route",
                detail="Header includes /voice; footer navigation does not, creating inconsistent IA.",
                files=("src/components/layout/site-footer.tsx",),
                suggestions=("Add Voice to footerLinks alongside Dashboard and Demo.",),
            )
        )

    if "/register" not in footer_hrefs:
        findings.append(
            AuditFinding(
                severity="medium",
                category="navigation",
                title="Footer omits Register route",
                detail="Register is only in header CTA; footer stops at Login.",
                files=("src/components/layout/site-footer.tsx",),
                suggestions=("Add Register to footer for parity with auth funnel.",),
            )
        )

  # Protected-route CTAs from marketing pages
    home = _read(root / "src/components/home/home-sections.tsx")
    if 'href="/dashboard"' in home and "login" not in home.lower():
        findings.append(
            AuditFinding(
                severity="high",
                category="navigation",
                title="Home CTAs deep-link to protected dashboard without auth hint",
                detail=(
                    "Hero and interface preview link to /dashboard. Unauthenticated users hit "
                    "middleware redirect to /login — feels like a broken product link during evaluation."
                ),
                files=("src/components/home/home-sections.tsx", "src/middleware.ts"),
                suggestions=(
                    "Use /demo as primary CTA for anonymous users; gate dashboard CTA behind session or add ?preview=1 public slice.",
                    "Show inline copy: 'Sign in to open mission control'.",
                ),
            )
        )

    if header_hrefs != footer_hrefs and header_hrefs - footer_hrefs:
        diff = sorted(header_hrefs - footer_hrefs)
        findings.append(
            AuditFinding(
                severity="low",
                category="ui_consistency",
                title="Header/footer navigation sets differ",
                detail=f"Routes in header but not footer: {', '.join(diff)}",
                files=("src/components/layout/site-header.tsx", "src/components/layout/site-footer.tsx"),
                suggestions=("Align nav items across header and footer.",),
            )
        )

    return findings


def _reasoning_audit(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    responses = root / "src/lib/reasoning/responses.ts"
    memory = root / "src/lib/reasoning/memory.ts"
    compound = root / "src/lib/reasoning/compound.ts"
    orchestrator = root / "src/lib/reasoning/orchestrator.ts"

    resp_text = _read(responses)
    if "function pick" in resp_text and "seed(command)" in resp_text:
        findings.append(
            AuditFinding(
                severity="high",
                category="mock_reasoning",
                title="Responses are deterministically templated from command hash",
                detail=(
                    "generateResponse uses seed(command) % len(templates) — identical phrasing on repeat, "
                    "no true generative variance. Reads as scripted demo, not live reasoning."
                ),
                files=(_rel(root, responses),),
                suggestions=(
                    "Label UI as 'simulated reasoning' explicitly on /demo.",
                    "Wire to backend LLM for production tier; keep templates as offline fallback only.",
                    "Add response freshness metadata (generatedAt, modelId).",
                ),
            )
        )

    if "Execution trace:" in resp_text:
        findings.append(
            AuditFinding(
                severity="medium",
                category="mock_reasoning",
                title="Synthetic execution trace appended to every response",
                detail=(
                    "formatExecutionAppendix adds 'Execution trace:' steps from execution-sim — "
                    "can feel performative when steps do not map to real tool calls."
                ),
                files=(_rel(root, responses), "src/lib/reasoning/execution-sim.ts"),
                suggestions=(
                    "Show execution trace in collapsible 'Simulation' panel.",
                    "Hide trace for simple intents; show only when plan.tools.length > 0.",
                ),
            )
        )

    orch_text = _read(orchestrator)
    if "STAGE_DELAYS" in orch_text or "wait(STAGE_DELAYS" in orch_text:
        findings.append(
            AuditFinding(
                severity="medium",
                category="mock_reasoning",
                title="Fixed stage delays regardless of command complexity",
                detail="Five pipeline stages always sleep ~1.4s total before responding — predictable cadence undermines 'live' feel.",
                files=(_rel(root, orchestrator),),
                suggestions=(
                    "Scale delays by command length or skip stages for trivial intents.",
                    "Stream partial stage completion from real backend when available.",
                ),
            )
        )

    mem_text = _read(memory)
    if "sessionStorage" in mem_text:
        findings.append(
            AuditFinding(
                severity="high",
                category="memory",
                title="Demo memory is sessionStorage-only (tab-local, ephemeral)",
                detail=(
                    "Memory facts reset per browser tab/session. Marketing claims 'compounds' and "
                    "'warmer each session' but storage does not survive tab close or cross-device."
                ),
                files=(_rel(root, memory), "src/lib/operational/persist.ts"),
                suggestions=(
                    "Persist memory to Supabase profile when authenticated.",
                    "On /demo, badge memory as 'Session memory (this tab only)'.",
                    "Sync operational-provider localStorage separately from reasoning memory — document both layers.",
                ),
            )
        )

    compound_text = _read(compound)
    if "NUTRITION_PATTERNS" in compound_text and "FORGET_PATTERNS" in compound_text:
        findings.append(
            AuditFinding(
                severity="medium",
                category="compound_intent",
                title="Compound intent limited to regex-carved scenarios",
                detail=(
                    "Compound handling covers forget + social + nutrition patterns (exam/hangout/eat). "
                    "Other multi-intent utterances fall back to single intent productivity bucket."
                ),
                files=(_rel(root, compound),),
                suggestions=(
                    "Expand segment detection or use lightweight NLU for conjunctions ('and', 'also').",
                    "Surface 'parsed as N intents' chips in UI when compound detected.",
                    "Add golden utterance tests for compound paths.",
                ),
            )
        )

    return findings


def _ux_performance_audit(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    layout = _read(root / "src/app/layout.tsx")
    transition = _read(root / "src/components/layout/route-transition.tsx")
    demo = _read(root / "src/components/demo/demo-console.tsx")
    conv = _read(root / "src/components/operational/conversation-surface.tsx")

    if "framer-motion" in layout or "framer-motion" in transition:
        findings.append(
            AuditFinding(
                severity="medium",
                category="animation_performance",
                title="Global route transitions animate every navigation",
                detail=(
                    "RouteTransition wraps all pages with AnimatePresence + motion.div (opacity/y). "
                    "On mobile or low-power devices, full-page transition on each nav click adds jank risk."
                ),
                files=("src/components/layout/route-transition.tsx", "src/app/layout.tsx"),
                suggestions=(
                    "Respect prefers-reduced-motion.",
                    "Limit transitions to marketing routes; disable for /demo and /dashboard.",
                ),
            )
        )

    if 'className="hidden' in demo and "lg:block" in demo:
        findings.append(
            AuditFinding(
                severity="medium",
                category="responsiveness",
                title="Demo quick-command sidebar hidden below lg breakpoint",
                detail=(
                    "Primary quick commands and cross-links to /voice and /dashboard are in aside hidden "
                    "until lg — mobile users only get conversation surface without command discovery."
                ),
                files=("src/components/demo/demo-console.tsx",),
                suggestions=(
                    "Expose quick commands as horizontal chips above input on mobile.",
                    "Mirror ConversationSurface showExamples on demo variant for sm screens.",
                ),
            )
        )

    if 'variant !== "voice"' in conv and "OperationalRail" in conv:
        findings.append(
            AuditFinding(
                severity="low",
                category="responsiveness",
                title="Operational pipeline rail hidden on voice route and small screens",
                detail="OperationalRail is hidden for voice variant and only shown lg+ elsewhere — pipeline visibility uneven.",
                files=("src/components/operational/conversation-surface.tsx",),
                suggestions=("Add compact pipeline strip under LivePresenceStrip on mobile.",),
            )
        )

    middleware = _read(root / "src/middleware.ts")
    if 'matcher: ["/dashboard/:path*", "/voice/:path*", "/onboarding/:path*"]' in middleware:
        findings.append(
            AuditFinding(
                severity="low",
                category="onboarding",
                title="/demo and /pricing are public while dashboard/voice are gated",
                detail="Auth middleware is correct but increases importance of clear CTA labeling on marketing pages.",
                files=("src/middleware.ts",),
                suggestions=(
                    "Add auth badge on dashboard/voice nav items when logged out.",
                ),
            )
        )

    return findings


def _product_positioning_audit(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    mock = _read(root / "src/lib/mockData.ts")
    demo_meta = _read(root / "src/app/demo/page.tsx")

    if "Mock" in mock or "mock" in demo_meta.lower():
        findings.append(
            AuditFinding(
                severity="medium",
                category="product_credibility",
                title="Product openly labeled mock in places but hero claims full OS",
                detail=(
                    "Home hero stats include 'Mock demo ready' while headline sells 'AI operating system'. "
                    "Mixed signals between enterprise OS positioning and demo simulation."
                ),
                files=("src/components/home/home-sections.tsx", "src/app/demo/page.tsx"),
                suggestions=(
                    "Unify narrative: 'Operator preview (simulated intelligence)' vs 'Production runtime'.",
                    "Tier pricing should state what is live vs simulated.",
                ),
            )
        )

    if "Supabase" in mock and "architecture ready" in mock:
        findings.append(
            AuditFinding(
                severity="low",
                category="product_credibility",
                title="Home hero advertises Supabase-ready architecture",
                detail="Sets backend expectation — ensure auth/onboarding actually use Supabase in prod path.",
                files=("src/components/home/home-sections.tsx", "src/lib/auth/auth-service.ts"),
                suggestions=("Verify auth-service is not stub-only; document env requirements on /register.",),
            )
        )

    op = _read(root / "src/contexts/operational-provider.tsx")
    if "isProcessingRef" in op and "executeCommand" in op:
        findings.append(
            AuditFinding(
                severity="low",
                category="empty_state",
                title="Concurrent commands guarded but no user-visible queue",
                detail="isProcessingRef blocks overlap; users may tap quick commands while active with only disabled styling (opacity-40).",
                files=("src/contexts/operational-provider.tsx", "src/components/demo/demo-console.tsx"),
                suggestions=("Show 'Processing…' toast or input placeholder when isActive.",),
            )
        )

    return findings


def _visual_hierarchy_audit(root: Path) -> list[AuditFinding]:
    return [
        AuditFinding(
            severity="low",
            category="visual_hierarchy",
            title="Strong luxury brand system but dense operational UI on small viewports",
            detail=(
                "Typography scale (text-6xl–9xl hero, font-display) is cohesive. Operational surfaces pack "
                "LivePresenceStrip + rail + cards — risk of vertical scroll fatigue on mobile voice/demo."
            ),
            files=(
                "src/app/globals.css",
                "src/components/operational/conversation-surface.tsx",
                "src/components/home/home-sections.tsx",
            ),
            suggestions=(
                "Audit spacing tokens at 390px width for /demo and /voice.",
                "Collapse LivePresenceStrip on xs to single-line status.",
            ),
        )
    ]


def _collect_findings(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    routes = _scan_routes(root)
    missing = [r for r in routes if not r.exists]
    if missing:
        findings.append(
            AuditFinding(
                severity="critical",
                category="routes",
                title="Missing expected route page files",
                detail="; ".join(f"{r.route} -> {r.page_path}" for r in missing),
                files=tuple(r.page_path for r in missing),
                suggestions=("Restore page.tsx for each route under src/app.",),
            )
        )

    findings.extend(_nav_audit(root))
    findings.extend(_reasoning_audit(root))
    findings.extend(_ux_performance_audit(root))
    findings.extend(_product_positioning_audit(root))
    findings.extend(_visual_hierarchy_audit(root))
    return findings


def _format_report(root: Path, routes: list[RouteScan], findings: list[AuditFinding]) -> str:
    lines: list[str] = [
        "JARVIS Website — Operational Product Audit (read-only)",
        f"  Target: {root}",
        "",
        "Route scan:",
    ]
    for r in routes:
        status = "ok" if r.exists else "MISSING"
        note = f" ({', '.join(r.notes)})" if r.notes else ""
        lines.append(f"  [{status}] {r.route:14} {r.label:28} {r.page_path}{note}")

    lines.extend(["", "Findings by severity:", ""])
    order = ("critical", "high", "medium", "low")
    for sev in order:
        bucket = [f for f in findings if f.severity == sev]
        if not bucket:
            continue
        lines.append(f"=== {sev.upper()} ({len(bucket)}) ===")
        for i, f in enumerate(bucket, 1):
            lines.append(f"\n{i}. [{f.category}] {f.title}")
            lines.append(f"   {f.detail}")
            if f.files:
                lines.append(f"   Files: {', '.join(f.files)}")
            for s in f.suggestions:
                lines.append(f"   - {s}")
        lines.append("")

    lines.extend(
        [
            "Suggested redesign priorities:",
            "  1. Auth-aware marketing CTAs (demo-first for anonymous; dashboard labeled sign-in).",
            "  2. Honest memory/reasoning labels + persistence story (tab vs account).",
            "  3. Mobile parity for demo quick commands and pipeline visibility.",
            "  4. Navigation IA: onboarding discoverability, footer parity.",
            "  5. Reduce performative execution trace; prefer collapsible simulation panel.",
            "",
            "Recommended next engineering tasks:",
            "  • Add prefers-reduced-motion guard on RouteTransition.",
            "  • Mobile quick-command chips on DemoConsole + ConversationSurface.",
            "  • Supabase-backed memory sync for authenticated routes.",
            "  • Compound-intent test suite (forget+social+nutrition golden paths).",
            "  • Public /demo banner: 'Simulated intelligence — not connected to local JARVIS runtime'.",
            "",
            f"Summary: {sum(1 for f in findings if f.severity == 'critical')} critical, "
            f"{sum(1 for f in findings if f.severity == 'high')} high, "
            f"{sum(1 for f in findings if f.severity == 'medium')} medium, "
            f"{sum(1 for f in findings if f.severity == 'low')} low.",
        ]
    )
    return "\n".join(lines)


def inspect_website_project(root: Path | str | None = None) -> str:
    """
    Audit the JARVIS marketing website product (read-only filesystem scan).
    Does not modify any website files.
    """
    if root is None:
        try:
            import config as cfg

            configured = getattr(cfg, "JARVIS_WEBSITE_PROJECT_ROOT", None)
            root = Path(configured) if configured else DEFAULT_WEBSITE_ROOT
        except Exception:
            root = DEFAULT_WEBSITE_ROOT
    else:
        root = Path(root)

    if not root.is_dir():
        return (
            f"Website project audit failed: path not found\n  {root}\n"
            "Set JARVIS_WEBSITE_PROJECT_ROOT in config or .env to the site repo root."
        )

    src = root / "src"
    if not src.is_dir():
        return f"Website project audit failed: no src/ under\n  {root}"

    routes = _scan_routes(root)
    findings = _collect_findings(root)
    return _format_report(root, routes, findings)
