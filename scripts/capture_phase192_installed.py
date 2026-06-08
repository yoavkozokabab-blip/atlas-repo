"""Capture the installed product's create-account screen (proves the frozen
accounts service is reachable from a clean install)."""
from __future__ import annotations
import os, subprocess, time, urllib.request, json
from playwright.sync_api import sync_playwright

INSTALL = os.path.join(os.environ["TEMP"], "atlas_fresh192", "App", "Atlas.exe")
DATA = os.path.join(os.environ["TEMP"], "atlas_fresh192", "Data")
OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "phase192_polish")
os.makedirs(OUT, exist_ok=True)
ACK = "atlas_unsigned_beta_ack_v157"


def _up(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def main():
    env = dict(os.environ, ATLAS_DESKTOP_DATA=DATA)
    proc = subprocess.Popen([INSTALL, "--no-browser"], env=env, cwd=os.path.dirname(INSTALL))
    try:
        # Wait for desktop (8777) and accounts service (8788).
        for _ in range(40):
            if _up("http://127.0.0.1:8777/") and _up("http://127.0.0.1:8788/health"):
                break
            time.sleep(0.5)
        print("desktop_up:", _up("http://127.0.0.1:8777/"), "accounts_up:", _up("http://127.0.0.1:8788/health"))
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            page = b.new_page(viewport={"width": 1180, "height": 900}, device_scale_factor=2)
            page.goto("http://127.0.0.1:8777/", wait_until="domcontentloaded")
            page.evaluate("k => localStorage.setItem(k,'1')", ACK)
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            page.evaluate("""() => { document.body.classList.remove('auth-loading');
                const m=document.getElementById('unsignedBetaModal'); if(m)m.style.display='none';
                if (window.showAccPanel) window.showAccPanel('login'); }""")
            page.wait_for_timeout(400)
            p = os.path.join(OUT, "installed_01_sign_in.png")
            page.screenshot(path=p)
            print("saved", p)
            page.evaluate("() => { if (window.showAccPanel) window.showAccPanel('register'); }")
            page.wait_for_timeout(400)
            p2 = os.path.join(OUT, "installed_02_create_account.png")
            page.screenshot(path=p2)
            print("saved", p2)
            b.close()
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        subprocess.run(["taskkill", "/F", "/IM", "AtlasAccounts.exe", "/T"], capture_output=True)
        subprocess.run(["taskkill", "/F", "/IM", "Atlas.exe", "/T"], capture_output=True)
    print("DONE")


if __name__ == "__main__":
    main()
