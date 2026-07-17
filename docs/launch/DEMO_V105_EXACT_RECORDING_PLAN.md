# Demo Recording Plan — Atlas v1.0.5 (exact, 45–60 s)

## Fixed parameters

- **Build:** installed v1.0.5 candidate (never a source run — footer must read "Atlas 1.0.5")
- **Demo repository:** bundled **Atlas Demo — Medium** (`medium_repo`, 18 files) — never a private repo
- **Impact target:** `services/billing.py` (8 direct dependents → dramatic, fast)
- **Ask query (if used as filler):** `What breaks if I change services/billing.py?`
- **Cursor query (recorded in Cursor chat):** `Using Atlas, what breaks if I change services/billing.py?`
- **Resolution:** capture at 1920×1080 display, app window sized to **1440×900** centered; record full window only (no desktop). Windows accent: default blue/neutral — never pink/red. Light cursor highlighting on.
- **Crop/export:** crop to the 1440×900 window, export **1080p MP4 (H.264, 30fps)**; also keep a 1440×900 master. Upload: YouTube unlisted + link in the HN post; keep a GIF (first 15 s, ≤10 MB) for the site hero if wanted.

## Preload before recording (do NOT record these)

1. Install candidate, launch once, complete guest entry + unsigned-notice ack.
2. Load Medium demo once so the scan is cached; then **reopen the app** so memory-restore is warm (avoids scan wait on camera). Do not restart *during* recording.
3. Connect Cursor and verify the Agents card shows **Connected** *before* recording; keep Cursor open on a second monitor/space with an empty chat.
4. Open the website homepage in a clean browser window (no other tabs, no bookmarks bar, guest profile).
5. Close: all other browser tabs, terminals, editors with private code, notification apps (Focus Assist on).
6. Reset onboarding via Settings → "Reopen welcome tour" **only if** the flow starts from onboarding; otherwise leave it dismissed.

## Shot list

| Time | Screen | Action (exact) | Caption (on-screen) | Narration | Fallback |
|---|---|---|---|---|---|
| 0–4s | Home (repo loaded) | none — slow cursor move toward sidebar | "Your coding agent can't see what depends on the file it's about to change." | "Coding agents edit confidently — and break things they can't see." | Static title card if Home not ready |
| 4–10s | Repository selector → demo | Click repo chip → click "Atlas Demo — Medium" (already scanned; loads instantly) | "Local scan. Your code never leaves your machine." | "Atlas scans the repo locally into a dependency map." | If already loaded, hover the metrics ribbon instead |
| 10–18s | Graph | Sidebar **Graph**; hover `services` cluster; click `services/billing.py` node | "18 files · 24 dependencies · mapped" | "Every import, resolved into a live structure." | If graph slow: Files screen, click billing.py |
| 18–34s | Impact | Sidebar **Impact**; type `services/billing.py`; click **Analyze impact**; slow-scroll result | "Blast radius: 8 dependents — with evidence" | "Before you change a file — see what may break: direct dependents, affected subsystems, tests, confidence." | Result is cached from preload; if pending >3 s, cut to pre-rendered take |
| 34–44s | Agents + Cursor | Sidebar **Agents** (Cursor card shows **Connected**); cut to Cursor chat; send the Cursor query; show grounded answer citing job workers | "Cursor asks Atlas over MCP — same graph, zero re-explaining" | "Your agent asks Atlas directly over MCP." | If Cursor answer slow: show Agents Connected card only, skip chat cut |
| 44–52s | Memory | Sidebar **Memory**; hover "restored" state | "Persistent memory — survives every session" | "And it remembers — tomorrow's session starts warm." | Home "Memory restored" chip if Memory screen is sparse |
| 52–60s | Website | Cut to homepage; scroll hero → click Download button (do not complete) | "Free · Windows · atlas-repo-wu76.vercel.app" | "Free on Windows. Link below." | End on hero if scroll stutters |

## Rejection criteria (re-record if any appear)

Private paths (`C:\Users\...`) · full commit hashes · account emails · test/QA
wording · pink/red title bar · empty result after a successful action · stale repo
name · error toasts · desktop icons/taskbar · any non-demo repository content.
