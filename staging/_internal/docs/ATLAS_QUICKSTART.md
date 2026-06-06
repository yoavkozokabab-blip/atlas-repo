# Atlas — Quick start (beta)

**Atlas maps your repository locally and helps you plan changes — it does not write or apply code.**

## Windows (easiest)

1. Install **Python 3.10+** from [python.org](https://www.python.org/downloads/) (check “Add python.exe to PATH”).
2. Double-click **`Launch Atlas.bat`** in this folder (or use **Launch Atlas** from the installer).
3. In the browser, click **Load Sample Repository** (fastest path to your first Build Plan).
4. Open **Build Plan**, keep the example text, click **Generate Change Plan**.

## macOS / Linux

```bash
cd path/to/local_jarvis
python3 run_atlas.py
```

Then open `http://127.0.0.1:8777/` and use **Load Sample Repository**.

## Do not do this

- **Do not** run `pip install -r requirements.txt` from the full J.A.R.V.I.S monorepo — that installs unrelated heavy packages. Atlas desktop runs on **Python stdlib** only.
- **Do not** scan `node_modules`, `.git`, or `.venv` — use **Scan scope** on Home if your repo is large.

## If something fails

- Open **Support** in the app (or `support.html`) → **Download support bundle (.zip)** and send it to your beta contact.
- Check Python: `py -3 --version` (Windows) or `python3 --version` (Mac/Linux).

## What to do with Export

Copy the packet and **paste it into Claude, Codex, or Cursor** as context before you ask the assistant to implement a change.
