"""Phase 189 - capture result feedback funnel screenshots.

Renders the real workflowFeedbackHtml() widget (with the shipped styles.css) on
the live Atlas app, and captures the admin result-feedback inbox populated with
real submitted feedback. Requires the desktop server on 127.0.0.1:8803 with
ATLAS_ADMIN=1 and at least one submitted result feedback row.
"""
from __future__ import annotations

import os
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8803"
OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "phase189_feedback_ux")
os.makedirs(OUT, exist_ok=True)
ACK_KEY = "atlas_unsigned_beta_ack_v157"


def _save(page, name):
    path = os.path.join(OUT, name)
    page.screenshot(path=path, full_page=False)
    print(f"  saved {name} ({os.path.getsize(path):,} bytes)")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 640}, device_scale_factor=2)

        # Render the real funnel widget inside a representative result card.
        page.goto(BASE, wait_until="domcontentloaded")
        page.evaluate("k => localStorage.setItem(k, '1')", ACK_KEY)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(700)

        page.evaluate(
            """() => {
                document.body.className = '';
                const host = document.createElement('div');
                host.id = 'p189Demo';
                host.style.cssText = 'position:fixed;inset:0;background:#0b1020;padding:40px;z-index:99999;overflow:auto;font-family:Inter,system-ui,sans-serif';
                host.innerHTML = `
                  <div class="glass ocard" style="max-width:680px;margin:0 auto;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:20px;color:#e8edf7">
                    <h3 style="margin:0 0 6px">Change Plan</h3>
                    <p style="color:#9fb0c8;margin:0 0 8px;font-size:13px">Size: <b>small</b> · Risk: <b>low</b></p>
                    <div style="border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px;color:#aebbd0;font-size:13px">
                      Files to inspect first, implementation order, and tests to run appear here.
                    </div>
                    <div id="p189slot"></div>
                  </div>`;
                document.body.appendChild(host);
                const slot = document.getElementById('p189slot');
                if (typeof workflowFeedbackHtml === 'function') slot.innerHTML = workflowFeedbackHtml('change_plan');
            }"""
        )
        page.wait_for_timeout(300)
        _save(page, "01_funnel_collapsed.png")

        # Expand the funnel: click Yes -> reveals category + comment + Send.
        page.evaluate("() => { if (typeof resultFeedbackVote==='function') resultFeedbackVote('change_plan', true); }")
        page.evaluate(
            """() => {
                const host = document.querySelector('.result-feedback[data-workflow=\"change_plan\"]');
                if (!host) return;
                const cat = host.querySelector('.rf-cat'); if (cat) cat.value = 'saved_time';
                const c = host.querySelector('.rf-comment'); if (c) c.value = 'Clear plan — found the right files fast and the test list was accurate.';
            }"""
        )
        page.wait_for_timeout(300)
        _save(page, "02_funnel_expanded.png")

        # Admin result-feedback inbox with real data.
        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto(BASE + "/admin.html", wait_until="domcontentloaded")
        page.wait_for_timeout(900)
        page.evaluate(
            """() => {
                const t = document.getElementById('resultFeedbackRows');
                if (t) { const card = t.closest('div[style*=\"border\"]'); if (card) card.scrollIntoView({block:'center'}); }
            }"""
        )
        page.wait_for_timeout(400)
        _save(page, "03_admin_result_feedback.png")

        browser.close()
    print("DONE:", OUT)


if __name__ == "__main__":
    main()
