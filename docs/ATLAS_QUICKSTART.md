# Atlas — Quick start

**Atlas maps your repository locally and helps you plan changes — it does not write or apply code.**

## Windows (easiest)

1. Install **Python 3.10+** from [python.org](https://www.python.org/downloads/) (check “Add python.exe to PATH”).
2. Double-click **`Launch Atlas.bat`** in this folder (or use **Launch Atlas** from the installer).
3. In the browser, click **Load Sample Repository** (fastest path to your first Build Plan).
4. Open **Build Plan**, keep the example text, click **Generate Change Plan**.

## Platform support

Atlas is currently packaged for Windows. macOS and Linux installers are not supported in
this release.

## Do not do this

- **Do not** install Python packages to run Atlas. The installed app is self-contained and the
  desktop runs on the **Python standard library** only — you do not need Python, Node, or any
  developer toolchain on your machine.
- **Do not** scan `node_modules`, `.git`, or `.venv` — use **Scan scope** on Home if your repo is large.

## If something fails

- Open **Support** in the app (or `support.html`) → **Download support bundle (.zip)** and send it to Atlas support.
- Check Python: `py -3 --version` (Windows) or `python3 --version` (Mac/Linux).

## What to do with Export

Copy the packet and **paste it into Claude, Codex, or Cursor** as context before you ask the assistant to implement a change.
