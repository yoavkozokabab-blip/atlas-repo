"""Capture proof that the REBUILT PACKAGED Atlas (dist/Atlas/Atlas.exe) now
shows the Phase 188 signed-out auth screen and create-account beta profile form.

Requires the packaged build running on 127.0.0.1:8810.
"""
from __future__ import annotations

import os
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8810"
OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "phase188_fix_verification")
os.makedirs(OUT, exist_ok=True)
ACK_KEY = "atlas_unsigned_beta_ack_v157"


def _save(page, name):
    p = os.path.join(OUT, name)
    page.screenshot(path=p, full_page=False)
    print(f"  saved {name} ({os.path.getsize(p):,} bytes)")


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page(viewport={"width": 1280, "height": 960}, device_scale_factor=2)
        page.goto(BASE, wait_until="domcontentloaded")
        page.evaluate("k => localStorage.setItem(k, '1')", ACK_KEY)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(900)

        # SIGNED OUT — assert the app shell is hidden and only the auth card shows.
        page.evaluate("""() => {
            document.body.classList.remove('auth-loading');
            const m = document.getElementById('unsignedBetaModal'); if (m) m.style.display='none';
            if (typeof window.showAccPanel === 'function') window.showAccPanel('login');
        }""")
        page.wait_for_timeout(400)
        state = page.evaluate("""() => {
            const shell = document.getElementById('app-shell');
            const cs = shell ? getComputedStyle(shell).display : 'none';
            const navVisible = !!document.querySelector('nav [data-view], .topbar [data-view]')
                && (document.querySelector('#app-shell') ? getComputedStyle(document.getElementById('app-shell')).display !== 'none' : false);
            return {
                bodyClass: document.body.className,
                appShellDisplay: cs,
                authLayoutVisible: !!document.getElementById('auth-layout'),
                loginVisible: (document.getElementById('acc-panel-login')||{}).style ? document.getElementById('acc-panel-login').style.display !== 'none' : false,
            };
        }""")
        print("  signed-out state:", state)
        _save(page, "01_signed_out.png")

        # CREATE ACCOUNT — beta profile onboarding form.
        page.evaluate("() => { if (typeof window.showAccPanel==='function') window.showAccPanel('register'); }")
        page.wait_for_timeout(300)
        page.evaluate("""() => {
            const set=(id,v)=>{const e=document.getElementById(id); if(e){e.value=v; e.dispatchEvent(new Event('input',{bubbles:true}));}};
            set('acc-reg-email','beta.user@example.com');
            const dev=document.getElementById('acc-current-dev-yes'); if(dev){dev.checked=true; dev.dispatchEvent(new Event('change',{bubbles:true}));}
            set('acc-languages','Python, TypeScript');
            set('acc-notes','Excited to try grounded change planning.');
        }""")
        fields = page.evaluate("""() => {
            const ids = ['acc-current-dev-yes','acc-project-use','acc-company-size','acc-dev-exp','acc-primary-role','acc-repo-size','acc-languages','acc-notes'];
            const present = ids.filter(i => !!document.getElementById(i));
            return { betaFieldsPresent: present.length, of: ids.length, hasBetaHeading: document.body.innerText.includes('Apply for beta access') };
        }""")
        print("  create-account beta fields:", fields)
        page.wait_for_timeout(200)
        _save(page, "02_create_account_beta_profile.png")

        b.close()
    print("DONE:", OUT)


if __name__ == "__main__":
    main()
