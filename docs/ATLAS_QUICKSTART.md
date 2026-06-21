# Atlas — Quick start (beta)

**Atlas maps your repository locally and helps you plan changes — it does not write or apply code.**

## Installed Atlas — Windows (easiest, no Python needed)

The installer bundles everything; **Python is not required**.

1. Launch **Atlas** from the Start-menu or desktop shortcut created by the installer.
2. In the browser that opens, click **Load Sample Repository** (fastest path to your first Build Plan).
3. Open **Build Plan**, keep the example text, click **Generate Change Plan**.

## Run from source (developers only)

Requires **Python 3.10+**. From your `local_jarvis` checkout:

```bash
python3 run_atlas.py        # Windows: py -3 run_atlas.py
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
