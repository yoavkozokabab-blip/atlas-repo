# Claude Desktop + Atlas MCP — public demo script

**Question:** Where is authentication implemented?

## Prerequisites

1. Atlas installed and `run_atlas.py --mcp` configured in Claude Desktop (`claude_desktop_config.json`).
2. Demo repository: `C:\J.A.R.V.I.S\local_atlas\docs\demo\auth_demo_repo`

## Steps (≈2 minutes)

1. **Launch Claude Desktop** and confirm **Atlas** appears under MCP servers.
2. **Open the demo repo** in your editor or file explorer so paths are familiar.
3. In Claude, ask exactly:

   > Where is authentication implemented?

4. **Observe tool calls** — Claude should invoke Atlas tools such as:
   - `atlas_scan_repo`
   - `atlas_find_file` / `atlas_find_relevant_files`
5. **Verify the answer** cites `app/auth.py` as the authentication implementation.

## Recorded evidence

- MCP trace: `reports/phase185_claude_desktop_demo_evidence.json`
- Screenshots: `screenshots/phase185/`
- Marketing GIF: `marketing/phase185/atlas-claude-auth-demo.gif`
- Generated: 2026-06-18T10:46:48Z

## Expected Atlas response (from captured run)

Authentication is implemented in `app/auth.py`. These paths were returned by Atlas MCP tools after scanning the repository.
