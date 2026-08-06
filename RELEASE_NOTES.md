# Atlas v1.0.6-beta.1

Private beta. Persistent repository memory for Claude Code, Cursor, and Codex —
local-first, Windows only, installer not code-signed.

## What Atlas does

Atlas scans a repository on your machine into a resolved import graph, subsystem map, and
per-file evidence, then serves that context to your coding agent over MCP (18 tools).
Scans persist to disk and are restored in fresh agent sessions after validating a
content signature against the live repository — unchanged repos restore instantly,
changed repos are refused as stale until you rescan. Impact, Debug, and Plan Change run
deterministically on the dependency graph and cite the files behind every result.
No account required.

## What is NOT in this beta

Stated plainly so nothing on the website or in the docs promises more than the build does:

- **Ask Atlas** (free-form repository Q&A) is disabled. Impact, Debug, Plan Change,
  the graph and MCP all work.
- **Accounts** are unavailable. Atlas starts in local mode; there is nothing to sign
  in to and nothing to sign up for.
- **Paid plans** are suspended. No checkout exists, and nothing in the app can charge you.
- **macOS and Linux** have no build.
- **The installer is unsigned.** SmartScreen will warn on first run.

## Impact analysis: what the numbers mean

Impact reports **direct dependencies** — the modules that import the file you name,
resolved from real import edges. The response says so itself
(`"impact_scope": "direct_only"`). Transitive blast radius is not computed in this
release. Any precision/recall figure published for Atlas describes that direct-dependency
tier and no broader set.

## Installation

1. Download `Atlas-Setup-1.0.6-beta.1.exe` and verify the SHA-256 against the release page.
2. Run the installer (per-user, no admin rights required), then launch Atlas.
3. Choose **Continue without an account**.
4. Load the bundled sample repository or scan your own folder.
5. Click **Connect** for Claude Desktop, Cursor, or Codex — Atlas writes the MCP config
   with a timestamped backup and preserves your other MCP servers. Restart the agent.

**Windows SmartScreen:** this installer is not code-signed, so SmartScreen shows a
warning on first run ("More info → Run anyway"). This is expected for new, unsigned
software. Verify the SHA-256 before running it — that is the check that actually proves
you have the file we published.

**You do not need Python, Node, or any developer toolchain.** The app is self-contained.

## Your data

Your source code is read and analysed entirely on your device and is never uploaded to
Atlas. Context that Atlas returns to your coding agent is sent to that agent's model
provider, not to us — that is the agent's network call, not Atlas's.

Atlas sends only a small allowlisted set of product-milestone analytics events (no
repository names, paths, file names, source, or prompts), which you can turn off in
Settings. Bug reports you submit are redacted for paths and credentials before sending,
and a copy is always kept on your machine.

## Uninstall

Uninstall from Windows Settings or the Start menu entry. Your scans, memory and settings
are **kept** — uninstalling never deletes your repository memory. To remove it too,
delete `%USERPROFILE%\.atlas_desktop` after uninstalling.

## Reporting problems

In-app: **Report an issue**. It is delivered to Atlas support, and if delivery fails the
app tells you so rather than pretending it succeeded — email the report instead.

Email: yoavkozokabab@gmail.com

## Known limitations

- Large monorepos index more slowly; very large repositories may produce a degraded graph,
  which Atlas labels rather than hides.
- Retrieval quality is not the same as end-to-end task success with a coding agent.
- Measurements published on the website come from one Windows development machine.
