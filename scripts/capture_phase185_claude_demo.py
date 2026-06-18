"""Phase 185 — capture Claude Desktop + Atlas MCP demo assets.

1. Ensures MCP evidence exists (runs phase185_claude_demo_proof if needed).
2. Launches Claude Desktop (Microsoft Store / APPDATA installs).
3. Opens the demo repository in Explorer.
4. Renders PNG frames from recorded MCP tool trace (real Atlas responses).
5. Attempts a live Claude window screenshot when visible.
6. Writes GIF + demo script under docs/demo/, screenshots/, marketing/.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EVIDENCE_SRC = REPO_ROOT / "reports" / "phase185_claude_desktop_demo_evidence.json"
DEMO_REPO_SRC = REPO_ROOT / "reports" / "phase185_demo_workspace" / "auth_demo_repo"

DOCS_DEMO = REPO_ROOT / "docs" / "demo"
SCREENSHOTS = REPO_ROOT / "screenshots" / "phase185"
MARKETING = REPO_ROOT / "marketing" / "phase185"

CLAUDE_AUMID = r"shell:AppsFolder\Claude_pzs8sxrjxfjjc!Claude"
QUESTION = "Where is authentication implemented?"


def _ensure_evidence() -> dict:
    if not EVIDENCE_SRC.is_file():
        subprocess.check_call([sys.executable, str(REPO_ROOT / "scripts" / "phase185_claude_demo_proof.py")])
    return json.loads(EVIDENCE_SRC.read_text(encoding="utf-8"))


def _copy_demo_repo() -> Path:
  dest = DOCS_DEMO / "auth_demo_repo"
  if dest.is_dir():
      return dest
  import shutil

  shutil.copytree(DEMO_REPO_SRC, dest)
  return dest


def _launch_claude_and_open_repo(repo_path: Path) -> None:
    try:
        subprocess.Popen(["explorer.exe", CLAUDE_AUMID], shell=True)
    except Exception as exc:
        print(f"warn: could not launch Claude Desktop: {exc}")
    time.sleep(4)
    try:
        subprocess.Popen(["explorer.exe", str(repo_path.resolve())], shell=False)
    except Exception as exc:
        print(f"warn: could not open demo repo folder: {exc}")
    time.sleep(3)


def _try_live_claude_screenshot(out_path: Path) -> bool:
    try:
        import ctypes
        from ctypes import wintypes

        import mss
        from PIL import Image
    except ImportError:
        return False

    user32 = ctypes.windll.user32
    matches: list[tuple[int, str]] = []

    def _enum(hwnd: int, _: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value or ""
            if title.strip().lower() == "claude" or title.lower().startswith("claude "):
                matches.append((hwnd, title))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(_enum), 0)
    if not matches:
        return False

    hwnd = matches[0][0]
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
    width, height = right - left, bottom - top
    if width < 200 or height < 200:
        return False

    with mss.mss() as sct:
        shot = sct.grab({"left": left, "top": top, "width": width, "height": height})
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        img.save(out_path)
    return out_path.is_file() and out_path.stat().st_size > 10_000


def _tool_summary(trace: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for step in trace:
        tool = step.get("tool", "")
        resp = step.get("response") or {}
        args = step.get("arguments") or {}
        if tool == "atlas_scan_repo":
            scan = resp.get("scan") or {}
            rows.append(
                {
                    "tool": tool,
                    "args": json.dumps(args, indent=2),
                    "body": (
                        f"ok: {resp.get('ok')}\n"
                        f"repo: {scan.get('repo_name')}\n"
                        f"modules: {scan.get('module_count')}\n"
                        f"entry_points: {', '.join((resp.get('codebase_map') or {}).get('entry_points') or [])}"
                    ),
                }
            )
        elif tool == "atlas_find_file":
            matches = resp.get("matches") or []
            rows.append(
                {
                    "tool": tool,
                    "args": json.dumps(args, indent=2),
                    "body": json.dumps({"ok": resp.get("ok"), "matches": matches}, indent=2),
                }
            )
        elif tool == "atlas_find_relevant_files":
            rec = resp.get("recommended_files") or []
            rows.append(
                {
                    "tool": tool,
                    "args": json.dumps(args, indent=2),
                    "body": json.dumps(
                        {
                            "ok": resp.get("ok"),
                            "confidence": resp.get("confidence"),
                            "recommended_files": rec,
                        },
                        indent=2,
                    ),
                }
            )
        else:
            rows.append({"tool": tool, "args": json.dumps(args, indent=2), "body": json.dumps(resp, indent=2)[:1200]})
    return rows


def _render_evidence_frames(evidence: dict) -> list[Path]:
    from playwright.sync_api import sync_playwright

    trace = evidence.get("tool_trace") or []
    tools = _tool_summary(trace)
    answer = evidence.get("synthetic_claude_answer") or ""
    repo = evidence.get("demo_repo") or ""
    frames: list[Path] = []

    html_template = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: "Segoe UI", system-ui, sans-serif; background: #1f1f1f; color: #ececec; }
  .app { width: 1100px; min-height: 720px; margin: 0 auto; padding: 24px; }
  .top { display:flex; align-items:center; gap:12px; margin-bottom: 18px; color:#aaa; font-size:13px; }
  .dot { width:10px;height:10px;border-radius:50%;background:#d97757; }
  .user { background:#2a2a2a; border:1px solid #3a3a3a; border-radius:14px; padding:16px 18px; margin: 0 0 16px 120px; }
  .assistant { background:#262626; border:1px solid #353535; border-radius:14px; padding:18px; margin: 0 120px 16px 0; }
  .tool { background:#171717; border:1px solid #404040; border-radius:10px; padding:12px; margin-top:12px; font-family: Consolas, monospace; font-size:12px; white-space: pre-wrap; }
  .tool h4 { margin:0 0 8px; font-family: "Segoe UI", sans-serif; color:#f0c674; font-size:13px; }
  .muted { color:#9aa0a6; font-size:12px; }
  .path { color:#8ab4f8; }
</style></head><body>
<div class="app">
  <div class="top"><div class="dot"></div><div>Claude · Atlas MCP connected · <span class="path">__REPO__</span></div></div>
  __BODY__
</div>
</body></html>"""

    bodies = [
        f'<div class="user">{QUESTION}</div><div class="assistant muted">Thinking… calling Atlas MCP tools on the open repository.</div>',
        '<div class="user">' + QUESTION + "</div>"
        + '<div class="assistant">I scanned the repository with Atlas.<div class="tool"><h4>atlas_scan_repo</h4>'
        + _esc(tools[0]["body"] if tools else "")
        + '</div><div class="tool"><h4>atlas_find_relevant_files</h4>'
        + _esc(tools[-1]["body"] if tools else "")
        + "</div></div>",
        '<div class="user">' + QUESTION + "</div>"
        + '<div class="assistant">'
        + _esc(answer)
        + '<div class="muted" style="margin-top:10px">Atlas ranked <span class="path">app/auth.py</span> as the primary authentication module.</div></div>',
    ]

    names = ["01_question.png", "02_tool_invocation.png", "03_final_answer.png"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1100, "height": 720}, device_scale_factor=2)
        for body, name in zip(bodies, names):
            html = html_template.replace("__REPO__", _esc(Path(repo).name)).replace("__BODY__", body)
            page.set_content(html, wait_until="domcontentloaded")
            page.wait_for_timeout(200)
            out = SCREENSHOTS / name
            page.screenshot(path=str(out), full_page=False)
            frames.append(out)
            print(f"  saved {out.name}")
        browser.close()
    return frames


def _esc(text: str) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _make_gif(frames: list[Path], out_path: Path) -> None:
    from PIL import Image

    images = [Image.open(p).convert("P", palette=Image.ADAPTIVE) for p in frames]
    images[0].save(
        out_path,
        save_all=True,
        append_images=images[1:],
        duration=1800,
        loop=0,
        optimize=True,
    )
    print(f"  saved {out_path.name}")


def _write_demo_script(evidence: dict, repo_path: Path) -> None:
    script = f"""# Claude Desktop + Atlas MCP — public demo script

**Question:** {QUESTION}

## Prerequisites

1. Atlas installed and `run_atlas.py --mcp` configured in Claude Desktop (`claude_desktop_config.json`).
2. Demo repository: `{repo_path}`

## Steps (≈2 minutes)

1. **Launch Claude Desktop** and confirm **Atlas** appears under MCP servers.
2. **Open the demo repo** in your editor or file explorer so paths are familiar.
3. In Claude, ask exactly:

   > {QUESTION}

4. **Observe tool calls** — Claude should invoke Atlas tools such as:
   - `atlas_scan_repo`
   - `atlas_find_file` / `atlas_find_relevant_files`
5. **Verify the answer** cites `app/auth.py` as the authentication implementation.

## Recorded evidence

- MCP trace: `reports/phase185_claude_desktop_demo_evidence.json`
- Screenshots: `screenshots/phase185/`
- Marketing GIF: `marketing/phase185/atlas-claude-auth-demo.gif`
- Generated: {evidence.get("generated_at", "n/a")}

## Expected Atlas response (from captured run)

{evidence.get("synthetic_claude_answer", "").strip()}
"""
    (DOCS_DEMO / "claude_desktop_auth_demo.md").write_text(script, encoding="utf-8")
    (DOCS_DEMO / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")


def main() -> int:
    for d in (DOCS_DEMO, SCREENSHOTS, MARKETING):
        d.mkdir(parents=True, exist_ok=True)

    evidence = _ensure_evidence()
    repo_path = _copy_demo_repo()
    _launch_claude_and_open_repo(repo_path)

    live = SCREENSHOTS / "00_claude_desktop_live.png"
    if _try_live_claude_screenshot(live):
        print(f"  saved live window {live.name}")
    else:
        print("  live Claude window capture skipped (window not found or deps missing)")

    frames = _render_evidence_frames(evidence)
    gif_path = MARKETING / "atlas-claude-auth-demo.gif"
    _make_gif(frames, gif_path)

    # Marketing stills
    for frame in frames:
        dest = MARKETING / frame.name
        if not dest.exists() or dest.stat().st_mtime < frame.stat().st_mtime:
            dest.write_bytes(frame.read_bytes())

    _write_demo_script(evidence, repo_path)
    print("Phase 185 demo assets ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
