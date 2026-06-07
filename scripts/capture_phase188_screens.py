"""Phase 188 - capture auth UX screenshots from the live Atlas desktop app.

Drives the auth state machine in jarvis_desktop/static and saves PNGs under
reports/phase188_auth_ux/. The Atlas desktop server must be running on
127.0.0.1:8802 (py -c "from jarvis_desktop import server; server.run(port=8802, open_browser=False)").

The admin/profile-review screenshot uses the page's own row template with
representative sample applicants because no live accounts service is running in
this verification environment. No product code is modified.
"""
from __future__ import annotations

import os
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8802"
OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "phase188_auth_ux")
os.makedirs(OUT, exist_ok=True)

# Skip the one-time unsigned-beta SmartScreen modal.
ACK_KEY = "atlas_unsigned_beta_ack_v157"

# Representative sample applicants for the admin table (sample data, no live backend).
SAMPLE_USERS = [
    {
        "email": "dana.architect@example.com", "status": "pending", "role": "user",
        "license": {"plan": "free", "status": "inactive"}, "device_count": 1,
        "beta_profile": {
            "project_use": "both", "company_size": "2_10", "developer_experience": "3_5",
            "primary_role": "full_stack", "coding_tools": ["claude", "cursor"],
            "notes": "Wants safer change planning before edits.",
        },
    },
    {
        "email": "sam.lead@example.com", "status": "beta", "role": "user",
        "license": {"plan": "beta", "status": "active"}, "device_count": 2,
        "beta_profile": {
            "project_use": "work", "company_size": "11_50", "developer_experience": "6_10",
            "primary_role": "backend", "coding_tools": ["codex", "github_copilot"],
            "notes": "Large monorepo; needs impact analysis.",
        },
    },
    {
        "email": "operator@useatlas.dev", "status": "active", "role": "superadmin",
        "license": {"plan": "pro", "status": "active"}, "device_count": 1,
        "beta_profile": {},
    },
]


def _save(page, name):
    path = os.path.join(OUT, name)
    page.screenshot(path=path, full_page=False)
    print(f"  saved {name} ({os.path.getsize(path):,} bytes)")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 960}, device_scale_factor=2)

        # 1. LOGIN -----------------------------------------------------------
        page.goto(BASE, wait_until="domcontentloaded")
        page.evaluate("k => localStorage.setItem(k, '1')", ACK_KEY)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(800)
        page.evaluate(
            """() => {
                document.body.classList.remove('auth-loading');
                document.body.classList.add('auth-mode');
                const m = document.getElementById('unsignedBetaModal'); if (m) m.style.display='none';
                if (typeof window.showAccPanel === 'function') window.showAccPanel('login');
            }"""
        )
        page.wait_for_timeout(400)
        _save(page, "01_login_signed_out.png")

        # 2. CREATE ACCOUNT / BETA PROFILE FORM ------------------------------
        page.evaluate("() => { if (typeof window.showAccPanel==='function') window.showAccPanel('register'); }")
        page.wait_for_timeout(300)
        # Fill a few representative fields for a realistic form screenshot.
        page.evaluate(
            """() => {
                const set = (id,v)=>{const e=document.getElementById(id); if(e){e.value=v; e.dispatchEvent(new Event('input',{bubbles:true}));}};
                set('acc-reg-email','dana.architect@example.com');
                set('acc-reg-password','SecurePass1!');
                const cp=document.getElementById('acc-reg-confirm')||document.getElementById('acc-reg-confirm-password'); if(cp){cp.value='SecurePass1!';}
                const dev=document.getElementById('acc-current-dev-yes'); if(dev){dev.checked=true; dev.dispatchEvent(new Event('change',{bubbles:true}));}
                set('acc-languages','Python, TypeScript');
                set('acc-notes','Looking for safer change planning before Claude writes code.');
                const t=document.querySelector('input[name="acc-tools"][value="claude"]'); if(t){t.checked=true;}
                const h=document.querySelector('input[name="acc-help"][value="planning_changes"]'); if(h){h.checked=true;}
            }"""
        )
        page.wait_for_timeout(300)
        _save(page, "02_create_account_beta_profile.png")

        # 3. PENDING APPROVAL ------------------------------------------------
        page.evaluate(
            """() => {
                ['acc-panel-login','acc-panel-register'].forEach(id=>{const e=document.getElementById(id); if(e)e.style.display='none';});
                const panel=document.getElementById('acc-panel-state'); if(panel)panel.style.display='';
                const set=(id,v)=>{const e=document.getElementById(id); if(e)e.textContent=v;};
                set('acc-state-icon','\\u23F3');
                set('acc-state-title','Beta access pending');
                set('acc-state-message','Your account was created and is waiting for beta approval.');
                set('acc-state-action','Atlas beta access is manually approved. Your code stays local.');
                const so=document.getElementById('acc-state-signout-btn'); if(so)so.style.display='';
                document.body.classList.add('auth-mode'); document.body.classList.remove('auth-loading');
            }"""
        )
        page.wait_for_timeout(300)
        _save(page, "03_pending_approval.png")

        # 4. ACCESS DENIED / NO BETA ACCESS (suspended) ----------------------
        page.evaluate(
            """() => {
                const set=(id,v)=>{const e=document.getElementById(id); if(e)e.textContent=v;};
                set('acc-state-icon','\\u23F8');
                set('acc-state-title','Account suspended');
                set('acc-state-message','This account is suspended. Contact the Atlas operator.');
                set('acc-state-action','Atlas workflows are unavailable for this account.');
            }"""
        )
        page.wait_for_timeout(300)
        _save(page, "04_access_denied_no_beta.png")

        # 5. ADMIN USER / PROFILE REVIEW -------------------------------------
        page.goto(BASE + "/admin.html", wait_until="domcontentloaded")
        page.wait_for_timeout(800)
        page.evaluate(
            """(users) => {
                const esc=s=>String(s||'').replace(/[<>&]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));
                const fmtList=v=>Array.isArray(v)?v.join(', '):(v||'');
                const lic=u=>{const l=u.license||{};return [l.plan,l.status].filter(Boolean).join(' / ')||'-';};
                const rows=document.getElementById('accountApplicantRows');
                rows.innerHTML=users.map(u=>{const p=u.beta_profile||{};return `<tr>
                  <td>${esc(u.email)}</td><td>${esc(u.status)}</td><td>${esc(u.role)}</td>
                  <td>${esc(lic(u))}</td><td>${esc(String(u.device_count||0))}</td>
                  <td>${esc(p.project_use||'-')}</td><td>${esc(p.company_size||'-')}</td>
                  <td>${esc(p.developer_experience||'-')}</td><td>${esc(p.primary_role||'-')}</td>
                  <td>${esc(fmtList(p.coding_tools)||'-')}</td><td class="muted">${esc(p.notes||'-')}</td></tr>`;}).join('');
                const sec=document.querySelector('#accountApplicantRows'); if(sec){sec.scrollIntoView();}
            }""",
            SAMPLE_USERS,
        )
        page.wait_for_timeout(400)
        # Screenshot the Beta applicants section specifically.
        section = page.query_selector("#accountApplicantRows")
        page.evaluate("() => { const t=document.querySelector('#accountApplicantRows').closest('div[style*=\"border\"]'); if(t) t.scrollIntoView({block:'center'}); }")
        page.wait_for_timeout(300)
        _save(page, "05_admin_profile_review.png")

        browser.close()
    print("DONE: 5 screenshots saved to", OUT)


if __name__ == "__main__":
    main()
