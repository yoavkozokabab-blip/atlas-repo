"""Capture the Phase 190 sectioned beta application wizard from the live app."""
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


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        page = b.new_page(viewport={"width": 1180, "height": 900}, device_scale_factor=2)
        page.goto(BASE, wait_until="domcontentloaded")
        page.evaluate("k => localStorage.setItem(k,'1')", ACK)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(800)
        page.evaluate("""() => { document.body.classList.remove('auth-loading');
            const m=document.getElementById('unsignedBetaModal'); if(m)m.style.display='none';
            window.showAccPanel('register'); }""")
        page.wait_for_timeout(400)

        # Step 1 — Account
        _save(page, "form_01_step1_account.png")

        # Fill step 1 and advance
        page.evaluate("""() => {
            const set=(id,v)=>{const e=document.getElementById(id); if(e){e.value=v; e.dispatchEvent(new Event('input',{bubbles:true}));}};
            set('acc-reg-email','beta.user@example.com'); set('acc-reg-pwd','SecurePass1!'); set('acc-reg-pwd2','SecurePass1!');
            atlasAccounts.wizardNext();
        }""")
        page.wait_for_timeout(300)
        # Step 2 — Developer profile
        page.evaluate("""() => {
            const set=(id,v)=>{const e=document.getElementById(id); if(e){e.value=v; e.dispatchEvent(new Event('change',{bubbles:true}));}};
            set('acc-primary-role','full_stack'); set('acc-dev-exp','3_5');
            const d=document.getElementById('acc-current-dev-yes'); d.checked=true; d.dispatchEvent(new Event('change',{bubbles:true}));
        }""")
        page.wait_for_timeout(200)
        _save(page, "form_02_step2_developer.png")
        page.evaluate("() => atlasAccounts.wizardNext()")
        page.wait_for_timeout(300)

        # Step 3 — Projects (company fields VISIBLE: work + full_stack + dev=yes)
        page.evaluate("""() => {
            const set=(id,v)=>{const e=document.getElementById(id); if(e){e.value=v; e.dispatchEvent(new Event('change',{bubbles:true}));}};
            set('acc-project-use','work'); set('acc-company-size','11_50'); set('acc-repo-size','large');
            const t=document.querySelector('input[name="acc-tools"][value="claude"]'); if(t)t.checked=true;
        }""")
        page.wait_for_timeout(250)
        _save(page, "form_03_step3_projects_company_shown.png")

        # Conditional: switch role to Student -> company fields hidden
        page.evaluate("""() => {
            // go back to step 2, set role=student, return to step 3
            atlasAccounts.wizardBack();
            const r=document.getElementById('acc-primary-role'); r.value='student'; r.dispatchEvent(new Event('change',{bubbles:true}));
            atlasAccounts.wizardNext();
        }""")
        page.wait_for_timeout(300)
        cond = page.evaluate("() => { const w=document.getElementById('acc-company-fields'); return getComputedStyle(w).display; }")
        print("  company fields display when role=Student:", cond)
        _save(page, "form_04_step3_company_hidden_conditional.png")

        # Restore role and advance through 4 and 5
        page.evaluate("""() => {
            atlasAccounts.wizardBack();
            const r=document.getElementById('acc-primary-role'); r.value='full_stack'; r.dispatchEvent(new Event('change',{bubbles:true}));
            atlasAccounts.wizardNext();
            const t=document.querySelector('input[name="acc-tools"][value="claude"]'); if(t)t.checked=true;
            atlasAccounts.wizardNext();
        }""")
        page.wait_for_timeout(300)
        # Step 4 — Goals
        page.evaluate("""() => { ['planning_changes','what_breaks'].forEach(v=>{const c=document.querySelector(`input[name="acc-help"][value="${v}"]`); if(c)c.checked=true;}); }""")
        page.wait_for_timeout(150)
        _save(page, "form_05_step4_goals.png")
        page.evaluate("() => atlasAccounts.wizardNext()")
        page.wait_for_timeout(300)
        # Step 5 — Optional notes (submit button visible)
        page.evaluate("""() => { const n=document.getElementById('acc-notes'); if(n){n.value='Looking forward to grounded change planning.';} }""")
        page.wait_for_timeout(150)
        _save(page, "form_06_step5_notes_submit.png")

        # Completion screen
        page.evaluate("() => window.showAccPanel('submitted')")
        page.wait_for_timeout(300)
        _save(page, "form_07_application_submitted.png")

        # Immediate validation demo: bad email + mismatched passwords on step 1
        page.evaluate("""() => {
            window.showAccPanel('register');
            const set=(id,v)=>{const e=document.getElementById(id); if(e){e.value=v; e.dispatchEvent(new Event('input',{bubbles:true}));}};
            set('acc-reg-email','not-an-email'); set('acc-reg-pwd','short'); set('acc-reg-pwd2','different');
        }""")
        page.wait_for_timeout(300)
        _save(page, "form_08_inline_validation.png")

        b.close()
    print("DONE:", OUT)


if __name__ == "__main__":
    main()
