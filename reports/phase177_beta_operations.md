# Phase 177 — Beta Operations

**Date:** 2026-06-06  
**Covers:** Feedback system audit, support ops, update flow, onboarding email, beta user management  
**No code changes. Design and audit only.**

---

## 1. Beta Feedback System Audit

### Current State

The feedback system (Phase 175B) stores user feedback locally to `localStorage` and posts to `/api/feedback` → `~/.jarvis_desktop/feedback.jsonl`. Remote routing requires `ATLAS_FEEDBACK_URL` environment variable, which is not configured in any shipped build.

**Result for 5 beta users:** Zero feedback reaches you unless the user manually sends a support bundle.

---

### What Information Must Be Collected

**Required (included in every feedback submission):**

| Field | Why | Sensitivity |
|-------|-----|-------------|
| `category` | bug / confusing_ui / missing_feature / general | None |
| `message` | The actual feedback text | Low |
| `atlas_version` | Which build they're on | None |
| `graph_health` | healthy / watch / partial — critical for bug triage | None |
| `module_count` | Repo size class without exposing paths | None |
| `demo_mode` | Was this on the demo or a real repo? | None |
| `page` | Which screen in Atlas generated the feedback | None |
| `ts` | Timestamp for ordering | None |

**Optional (user provides):**

| Field | Why | Note |
|-------|-----|------|
| `email` | So you can reply | Never required |
| `repo_language` | Python vs TS vs other | From scan metadata, not user-supplied |

---

### What Must NOT Be Collected

| Data | Why not |
|------|---------|
| Repository path (`repo_path`) | Contains absolute filesystem paths; privacy violation |
| File names from the repository | Source code structure; privacy violation |
| Any content from scanned files | Source code; hard never |
| API keys, tokens, auth headers | Redacted by `_redact_support_text` but don't even try to collect them |
| Email without explicit consent | Never auto-capture; always explicit opt-in |
| User's Claude API key | Never, ever |
| Stack traces with file paths | Redact file paths before collecting |

---

### What Must Appear in Support Bundles

The current support bundle (Phase 174F verified) includes:
- `diagnostics.json`: version, scan stats, trust integrity status, memory persistence
- `environment.json`: Python version, platform
- `scan_metadata.json`: modules, edges, graph health, scan duration
- `startup_checks.json`: self-test results
- `logs/launcher.log`: redacted
- `logs/analytics.jsonl`: event types and timestamps only

**Currently missing from support bundles (add before 5 users):**

| Missing | Why it matters |
|---------|---------------|
| `feedback.jsonl` | You need to read the user's reported issues |
| Crash count from `crashes.jsonl` (if it exists) | Correlate support requests with crash events |
| Last 5 workflow operations | What was the user doing before they needed support? |
| `atlas_version` at bundle time | Sometimes users are on old builds |

**Should NOT be in support bundles:**

| Data | Reason |
|------|--------|
| Full repository file listing | Privacy |
| Source code content | Privacy |
| Plan output text (may contain file names) | Borderline; strip if present |

---

### Remote Feedback Routing for Beta

**Minimum viable setup (Day 1):**

Configure `ATLAS_FEEDBACK_URL` in the shipped Atlas binary to point to a Formspree or Typeform endpoint. The `submit_feedback()` function already sends a `POST` request when `ATLAS_FEEDBACK_URL` is set. The payload includes version, graph_health, module_count, demo_mode — all safe.

**Cost:** Formspree free tier handles 50 submissions/month. That covers 5 users × 10 feedback events each.

**Better setup (before 20 users):**

A simple webhook (Zapier, Make, or a 20-line Python Flask endpoint) that:
1. Receives the JSON POST from Atlas
2. Sends a Slack/Discord notification with the message and Atlas version
3. Appends to a shared spreadsheet or Notion database

---

## 2. Support Operations

### Support Channel (Phase 175B: configured)

`support@useatlas.dev` is present on `contact.html` and `support.html`. This is the right channel.

**Required SLAs for 5-user supervised beta:**

| Situation | Response time |
|-----------|--------------|
| Scan fails / app crashes | 4 hours |
| Wrong output / confidence issue | 24 hours |
| Feature question | 48 hours |
| General feedback | 3 days |

**Support bundle collection protocol:**

When a user reports a bug, first reply:
> "Thanks for reporting. Can you click Help → Copy diagnostics and paste the output? Or click Help → Open support bundle and attach the downloaded file? This gives me version, scan stats, and error logs without any source code."

---

### Triage Decision Tree

```
User reports issue
├── "It crashed / won't start"
│   → Request support bundle
│   → Check launcher.log for PermissionError (port conflict)
│   → Check Python version (need 3.10+)
│   → Check SmartScreen (only on first install)
│
├── "The output looks wrong"
│   → Ask: demo repo or real repo?
│   → Ask: which workflow (Change Plan / Impact / Investigate)?
│   → Ask: what did you type?
│   → Check graph_health in their diagnostics (partial = thin edges)
│
├── "I don't understand the output"
│   → Point to Quickstart page
│   → Explain Beginner vs Advanced toggle
│   → Offer 30-minute call
│
└── "The scan is slow"
    → Expected: Django 18s, VS Code 130s
    → If >5x expected: OOM or antivirus scanning
    → Suggest scan scope (Python only vs entire repo)
```

---

## 3. Update Flow

### Current State (Phase 175B)

`check_for_update()` in `product_info.py` reads `ATLAS_UPDATE_CHECK_URL`. If configured, fetches `latest.json`, compares versions, returns `update_available: true/false`. The UI has an `updateBanner` element that renders if `update_available = true`. The banner includes a link to release notes and a dismiss button.

**What's not done:**
- `ATLAS_UPDATE_CHECK_URL` is not configured in any shipped build
- No `latest.json` is hosted anywhere
- The changelog page is empty

### Required Setup Before First User

**Step 1: Host latest.json**

Choose a permanent URL. Options:
- GitHub Gist: `https://gist.githubusercontent.com/.../latest.json`
- GitHub Pages: `https://your-username.github.io/atlas/latest.json`
- Netlify: `https://yourdomain.netlify.app/latest.json`
- S3: `https://your-bucket.s3.amazonaws.com/atlas/latest.json`

Content:
```json
{
  "version": "0.1.0-beta",
  "release_notes_url": "https://yourdomain/changelog",
  "notes": "First external beta release."
}
```

**Step 2: Configure the URL in the shipped binary**

Set `ATLAS_UPDATE_CHECK_URL` in the build environment or hard-code in `product_info.py:update_check_url()` with a fallback:
```python
def update_check_url() -> str:
    env = os.environ.get("ATLAS_UPDATE_CHECK_URL", "").strip()
    return env or "https://your-stable-url.com/atlas/latest.json"
```

**Step 3: Write the changelog entry**

Write the `0.1.0-beta` entry in `changelog.html`. One paragraph. Ship it.

**Step 4: Test the update banner**

Temporarily set `latest.json` to version `"0.1.1-beta"` and verify the banner appears, links to the changelog, and dismisses.

**Effort:** 1–2 hours total.

---

### Update Notification UX

The current update banner (Phase 175B `atlas_product.js`) shows a non-intrusive bar with:
- "Update available: 0.1.1-beta"
- [Release notes] button
- [Dismiss] button

This is correct behavior. Do not add blocking modals or forced restarts. The user dismisses when they're ready and updates manually by downloading the new installer.

---

## 4. Beta User Operations

### Onboarding Email Template

```
Subject: Your Atlas beta access — download inside

Hi [Name],

Here's your direct download link: [DIRECT LINK TO Atlas_Setup.exe]

What to do in the first 5 minutes:
1. Install Atlas — it takes about 2 minutes.
2. When Windows shows a security warning ("Windows protected your PC"), click More info → Run anyway. This is expected for unsigned beta software.
3. Atlas opens your browser automatically. Click "Load Sample Repository."
4. Type something like "add rate limiting" and click Generate Change Plan.
5. Click "Copy for Claude" and paste it into Claude.

That's it. No account. No API key. No internet connection needed.

I'm personally available for a 30-minute call this week if you'd like a walkthrough. 
Book here: [Calendly link]

Any issues: email support@useatlas.dev or reply to this message directly.
I respond within 4 hours on weekdays.

[Your name]
```

---

### 30-Minute Onboarding Call Agenda

| Time | Topic |
|------|-------|
| 0–2 min | Brief: what repo will they scan? What AI tool do they use daily? |
| 2–8 min | Screen share: watch them open Atlas and load the sample (observe without explaining) |
| 8–15 min | Watch them type a change request and generate a plan |
| 15–20 min | Watch them copy to Claude and interact with Claude (observe the output) |
| 20–25 min | Ask: "What surprised you? What was confusing?" (don't lead) |
| 25–30 min | Ask: "If this disappeared tomorrow, what would you miss most?" |

**Key rule:** Observe for the first 15 minutes. Do not explain anything the user doesn't explicitly ask about. What they find without help is the product working. What they miss or skip is a UX failure.

---

### Week 1 Communication Protocol

| Day | Action |
|-----|--------|
| Day 0 | Send onboarding email with download link |
| Day 1 (after install) | Send 3-question install feedback (see Phase 171 framework) |
| Day 2 | Ask: "Did you return to Atlas today? What brought you back?" |
| Day 4 | Send 30-min call invite |
| Day 7 | Send post-first-week survey (disappointment score + top feature request) |
| Day 14 | Optional: send "have you scanned your real repo yet?" prompt |

---

## 5. Beta User Profile Reminder (Phase 171)

Recruit users who match:
- Uses Claude, Cursor, or Codex ≥ 1h/day
- Has a Python or TypeScript repo actively in development
- Repo size: 10k–300k LOC
- Willing to do a 30-minute call after week 1
- **Not** at an enterprise with strict data/security policies

**Fastest recruitment path:**
1. Personal DM to 10 developers you know who use Claude/Cursor — same day
2. Post on X with FastAPI scan speed numbers + DM CTA — 24 hours
3. Post on r/LocalLLaMA — 24 hours

**Accept the first 5 who confirm they have a Python/TS repo in active development.**
