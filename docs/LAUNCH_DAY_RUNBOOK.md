# Atlas v1.0 — Launch Day Runbook (Tuesday)

Owner: Yoav · Support inbox: yoavkozokabab@gmail.com
Final build: commit `5b83d57d` (guest mode), installer SHA256 `23E882490013F5745BB9156FBD6269B3646E470D0065E4705E6D41699AA08554`.

## Pre-launch checklist (run the morning of)

- [ ] `https://<prod-url>/api/health` returns ok, `backend: supabase`
- [ ] `/`, `/hn`, `/download`, `/pricing`, `/faq`, `/changelog` all 200 in a logged-out incognito window
- [ ] `/download/atlas` downloads the installer while logged out; hash matches the published SHA256
- [ ] GitHub Release v1.0.0 is public; asset downloads logged-out; release notes render
- [ ] Every GitHub link on the site points at `yoavkozokabab-blip/atlas-repo`
- [ ] Pricing shows Pro **Coming soon** (checkout disabled) unless Paddle was verified end-to-end
- [ ] Fresh installed-app smoke: install → sample repo → Ask Atlas cites files → MCP test PASS
- [ ] Support inbox open; SUPPORT_RUNBOOK.md at hand

## Publish steps

1. Post from `docs/SHOW_HN_POST.md` (title + URL `https://<prod-url>/hn`).
2. Immediately add the prepared first founder comment.
3. Pin the tab; respond from `docs/HN_RESPONSE_SHEET.md`.

## Monitoring (hourly)

- Vercel deployment status + function errors (`vercel logs`)
- `/api/health` (Supabase reachability)
- GitHub release download count (`gh release view v1.0.0`)
- Support inbox
- HN thread — every top-level comment gets a reply

## HN response rules

- Reply honestly; never argue. Concede real limitations immediately (unsigned installer, Windows-only, deterministic-not-LLM answers, Python/TS depth).
- Never invent numbers. The only measured claim is the 27-file-repo restore benchmark, scoped as written on /hn.
- Security claims: point at /security#data-flow rather than paraphrasing from memory.
- Bugs reported in-thread: acknowledge, ask for launcher.log, fix on `hotfix/v1.0.x`, note the fix in the thread.

## Rollback

| What broke | Action |
|---|---|
| Website deploy bad | `vercel rollback` to the previous production deployment (or redeploy previous commit) |
| Installer bad | Edit the GitHub release: re-upload previous known-good asset (`packaging/installer/output/` history in git: commit `cf47c9c1` = faf7e6dc build, SHA `53DD…371B` — note it predates guest mode, so the sign-in wall returns) and update the SHA in the notes + `NEXT_PUBLIC_INSTALLER_SHA256` |
| Download path broken | Point `ATLAS_INSTALLER_URL` / `NEXT_PUBLIC_DOWNLOAD_URL` env at the GitHub asset URL directly and redeploy (env change only) |
| Checkout misbehaving | It ships disabled. If it was enabled: unset `PADDLE_API_KEY`/`PADDLE_PRO_PRICE_ID` and redeploy — pricing reverts to "Coming soon" automatically |
| Emergency notice | Prepend a banner in `app/layout.tsx` (single div, no dependency) and redeploy |

## Hotfix

Branch `hotfix/v1.0.x` from `c243cdd5` → fix → full pytest suite + `verify_installed_launch.py` → rebuild installer (`installer_build.ps1`, SHA sidecar auto-regenerates) → replace release asset + update SHA everywhere it is printed (release notes, /hn env var).

## Post-launch metrics (48h)

- Release download count vs website `download_click` (if analytics endpoint enabled)
- HN thread: top objections → feed FAQ
- Support emails by category (install / SmartScreen / MCP / scan)
- Crash reports in launcher.log samples users send
