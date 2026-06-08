"""Capture in-app Atlas screens for the Phase 190 polish review."""
from __future__ import annotations
import os
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8811"
OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "phase190_polish")
os.makedirs(OUT, exist_ok=True)
ACK = "atlas_unsigned_beta_ack_v157"


def _save(page, name):
    p = os.path.join(OUT, name)
    page.screenshot(path=p, full_page=False)
    print(f"  saved {name} ({os.path.getsize(p):,} bytes)")


def _enter_app(page):
    # Reveal the app shell for review (no live account needed).
    page.evaluate("""() => {
        document.body.classList.remove('auth-mode','auth-loading');
        document.body.classList.add('app-authenticated');
        const a=document.getElementById('auth-layout'); if(a)a.style.display='none';
        const s=document.getElementById('app-shell'); if(s)s.style.display='';
    }""")


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        page = b.new_page(viewport={"width": 1366, "height": 900}, device_scale_factor=1.5)
        page.goto(BASE, wait_until="domcontentloaded")
        page.evaluate("k => localStorage.setItem(k,'1')", ACK)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(900)
        _enter_app(page)
        page.wait_for_timeout(400)

        for view, name in [
            ("home", "app_01_home.png"),
            ("build", "app_02_change_plan_empty.png"),
            ("investigate", "app_03_debug_empty.png"),
            ("impact", "app_04_what_breaks_empty.png"),
            ("export", "app_05_export_empty.png"),
        ]:
            try:
                page.evaluate(f"() => {{ if (typeof go==='function') go('{view}'); }}")
                page.wait_for_timeout(500)
                _save(page, name)
            except Exception as e:
                print(f"  {view}: {e}")

        # Admin page (separate route)
        page.goto(BASE + "/admin.html", wait_until="domcontentloaded")
        page.wait_for_timeout(900)
        _save(page, "app_06_admin.png")

        b.close()
    print("DONE:", OUT)


if __name__ == "__main__":
    main()
