# Atlas v1.0.0

Persistent repository memory for Claude Code, Cursor, and Codex — local-first, on Windows.

## What Atlas does

Atlas scans a repository on your machine into a resolved import graph, subsystem map, and
per-file evidence, then serves that context to your coding agent over MCP (18 tools).
Scans persist to disk and are restored in fresh agent sessions after validating a
content signature against the live repository — unchanged repos restore instantly,
changed repos are refused as stale until you rescan. Ask Atlas answers repository
questions with cited files; Impact, Debug, and Plan Change run deterministically on the
dependency graph. No account required.

## Installation

1. Download `Atlas_Setup.exe` below and verify the SHA256.
2. Run the installer (per-user, no admin rights required), then launch Atlas.
3. Load the bundled sample repository or scan your own folder.
4. Click **Connect** for Claude Desktop, Cursor, or Codex — Atlas writes the MCP config
   with a timestamped backup and preserves your other MCP servers. Restart the agent.

**Windows SmartScreen:** this installer is not code-signed yet, so SmartScreen shows a
warning on first run ("More info → Run anyway"). This is expected for a new, unsigned
publisher. Verify your download against the SHA256 below before continuing, and only
install from this release page.

## Supported tools

- Claude Desktop / Claude Code (MCP)
- Cursor (MCP)
- Codex (MCP, `~/.codex/config.toml` or `$CODEX_HOME`)

## Local-first data model

- Indexing runs entirely on your machine; repository contents are never uploaded to
  Atlas servers during indexing (there is no hosted indexing service).
- All scans, graphs, and repository memory live in `%USERPROFILE%\.atlas_desktop`.
  Uninstalling removes both the app and this data directory.
- The only network path for your code remains the one you already have: whatever your
  connected agent sends to its own model provider under that provider's terms.
- Atlas never trains models on customer repositories. Details: the Security page on the
  website (data-flow diagram, deletion instructions).

## Known limitations

- Windows-only installer (macOS/Linux on the roadmap). Unsigned — SmartScreen warns.
- Deep dependency analysis covers Python and JavaScript/TypeScript; Go, Rust, Java, C#,
  and Ruby are scanned at file level.
- Impact analysis covers statically resolved imports; dynamic dispatch and reflection
  are out of scope.
- Very large monorepos index slowly today.
- Pro checkout is disabled at launch ("Coming soon"); the core app is free.

## Checksums

```
Atlas_Setup.exe SHA256:
53DDF70E756A760B7BD55F98AD59492D4FC043D5DAAB8CA827EDF29D3FEC371B
```

Built from commit `faf7e6dc`.

## Contact & changelog

- Support / feedback / security disclosures: **yoavkozokabab@gmail.com**
- Changelog: https://github.com/yoavkozokabab-blip/atlas-repo — see `/changelog` on the
  website for the launch-build notes.
