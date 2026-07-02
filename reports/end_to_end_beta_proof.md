# Atlas — End-to-End Beta Proof

**Date:** 2026-06-20 · Evidence: `reports/end_to_end_proof/mcp_transcript.json` + the timed runs below.

## Honesty boundary (read first)
A literal "clean machine → production → Claude Desktop UI → Claude's answer, with screenshots" cannot be produced from this environment, and I will not fake it:
- **No clean VM** — can't perform a fresh OS install.
- **No live production URL / no external egress** — can't exercise the deployed Vercel+Supabase site; auth was proven against a local instance of the same code.
- **I am not Claude Desktop** — I cannot screenshot its tools menu or capture its natural-language answer. Instead I drove the MCP server over stdio **exactly as Claude Desktop does** and captured the real tool calls + responses.
- **No screenshots** — the proof is logs + tool invocations + timings (the JSON transcripts).

Everything below is **really executed**, with timings. The legs I can't run here are listed as owner-verified, each with a runnable script.

---

## PROVEN HERE

### Steps 1–4 + login: account / login / session / logout (timed, real HTTP)
Against a running instance of the deployed website code:
```
1. register (web)      201  0.221s
2. session (cookie)    200  0.212s   (httpOnly cookie persists across tabs)
3. logout              200  0.129s
4. login (web)         200  0.168s
```
Error paths (from prior QA, same code): wrong-pw/unknown → "Invalid email or password." (anti-enumeration); dup → "An account with this email already exists."; weak → "Password must be at least 8 characters." All sub-second. *(Local run uses the file store; production uses Supabase — identical flow, gated only on the owner's env, which `/api/health` now validates and surfaces by hostname.)*

### Step 3 (download) + desktop login: what the installed app actually calls
```
5. desktop/login       ok=true  plan=free  (bearer token issued)
6. desktop/me (Bearer) 200  0.112s   (same identity, returns plan/entitlement)
7. GET /download/atlas 302         (login-gated → redirects to the hosted installer when ATLAS_INSTALLER_URL is set)
```
This is the unified web↔desktop identity: one account, website + desktop. (Full register→token→/me→logout→bad-login round-trip previously: `desktop_web_auth_smoke.py` 13/13.)

### Step 4 (installer artifact)
`packaging/installer/output/Atlas_Setup.exe` · SHA256 `bc2a3e60113e74400d44d99c3548662e94739ec6074860482a116e6edb30cc6e` · `--self-test` → ready:true, frozen:true.

### Steps 5–9: MCP value moment — frozen `Atlas.exe --mcp` answering the question
Drove the **packaged exe** over stdio (the MCP client role Claude plays). Question: **"Where is authentication implemented?"** on the `requests` repo. Real transcript (`mcp_transcript.json`), with timings:
```
[  164 ms] initialize          → serverInfo {name: atlas-local, version: 0.1.0-beta}
[    0 ms] tools/list          → 17 tools (what appears in Claude's tools menu)
[    3 ms] tools/call atlas_health      → ok=true
[ 1494 ms] tools/call atlas_scan_repo   → ok=true, files=125
[   39 ms] tools/call atlas_find_relevant_files(task="Where is authentication implemented?")
              → confidence=HIGH, files=[src/requests/auth.py, utils.py, models.py, status_codes.py, cookies.py, structures.py]
[   37 ms] tools/call atlas_build_context_pack(same task)
              → confidence=HIGH, ~1386 tokens, top file src/requests/auth.py
TOTAL MCP JOURNEY: 1738 ms
```
**The answer is correct:** `requests` implements authentication in `src/requests/auth.py` (HTTPBasicAuth/HTTPDigestAuth/HTTPProxyAuth) — Atlas ranked it **#1, HIGH confidence**, in a 1.4k-token pack, in **under 2 seconds** from a cold MCP start. This is exactly what Claude receives and would summarize as its answer.

> **Note on the shipped exe:** it is commit `f70a4975e` (17 tools, older pack format → no `relevance_score`/symbol-slices/root-cause). The core retrieval is correct (auth.py #1); a rebuild would add the evidence-centric/slicing/root-cause upgrades made later.

---

## NOT PROVEN HERE (owner-verified; de-risked)
| Leg | Why not here | How the owner proves it | De-risk already in hand |
|---|---|---|---|
| Clean-machine install (steps 4–6) | no VM | install on a fresh Windows VM | `--self-test` ready; install proof PASSED |
| Production account/login/download (1–3) | no live URL/egress | `BASE_URL=https://useatlas.dev py -3 scripts/website_smoke_test.py` | identical code proven locally; `/api/health` validates Supabase |
| Claude Desktop UI: tools appear, Claude answers (5–10) | I'm not Claude Desktop | add `Atlas.exe --mcp` to `claude_desktop_config.json`, ask the question | `scripts/mcp_install_proof.py` + this transcript prove the transport + tools + answer-data on the frozen exe |
| Screenshots | can't capture clean machine / Claude UI | screen-record the above | logs/transcripts provided instead |

---

## Timing summary (the parts that exist)
- Auth journey (register→session→logout→login): **~0.7 s** total of HTTP.
- MCP cold-start → correct ranked answer: **~1.7 s**.
- Human steps (download, SmartScreen "Run anyway", paste MCP JSON, restart Claude): the only multi-minute part — comfortably inside 10 minutes for a technical user.

## FINAL VERDICT — Can a real external beta user obtain value within 10 minutes?
**YES — for a technical user, conditional on the owner's production being live.** The value-delivery mechanism is proven and fast: auth is sub-second, and the frozen Atlas.exe answers a real "where is auth?" question correctly in <2 s. The remaining minutes are human (download + SmartScreen + one JSON paste), which fit well within 10. 

**This is a conditional YES, not an unconditional one:** I did **not** run it on a clean machine, against live production, or inside the Claude Desktop UI (those are owner-only and not faked here) — but each is de-risked by the proofs above. The honest blockers are **owner ops** (Supabase migrations + correct Vercel env + `useatlas.dev` DNS + GitHub release + `ATLAS_INSTALLER_URL`) and **one real Claude-Desktop confirmation** — not the product's ability to deliver value in time, which is demonstrated here.
