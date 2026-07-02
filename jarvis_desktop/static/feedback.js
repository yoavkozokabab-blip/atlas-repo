"use strict";
/* Atlas feedback — local save + optional remote destination (ATLAS_FEEDBACK_URL). */
(function () {
  const KEY = "atlas_feedback";
  const LEGACY_KEY = "\u006a\u0061\u0072\u0076\u0069\u0073_feedback";
  const CATS = [
    { id: "bug", label: "Bug", icon: "🐞" },
    { id: "confusing_ui", label: "Confusing UI", icon: "🧭" },
    { id: "missing_feature", label: "Missing feature", icon: "✨" },
    { id: "general", label: "General feedback", icon: "💬" },
  ];
  let selected = "general";
  let pendingContext = null;
  let productConfig = { feedback_url_configured: false, support_email: "yoavkozokabab@gmail.com" };

  function migrateLegacy() {
    try {
      if (localStorage.getItem(KEY)) return;
      const legacy = localStorage.getItem(LEGACY_KEY);
      if (legacy) localStorage.setItem(KEY, legacy);
    } catch (e) {}
  }

  function list() {
    migrateLegacy();
    try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; }
  }
  function save(entry) {
    const l = list();
    l.push(entry);
    localStorage.setItem(KEY, JSON.stringify(l));
    return l.length;
  }
  function toast(m) {
    let t = document.getElementById("mtoast");
    if (!t) { t = document.createElement("div"); t.id = "mtoast"; t.className = "mtoast"; document.body.appendChild(t); }
    t.textContent = m; t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 2800);
  }

  async function loadConfig() {
    try {
      const r = await fetch("/api/product/config");
      const data = await r.json();
      if (data && data.ok) productConfig = data;
    } catch (e) {}
    return productConfig;
  }

  function submitLabel() {
    return productConfig.feedback_url_configured ? "Submit to Atlas" : "Save locally";
  }

  function submitHint() {
    if (productConfig.feedback_url_configured) {
      return "Sends a redacted summary to Atlas — no source code. Also saved on this device.";
    }
    return "Saved locally — send a support bundle manually if you need help.";
  }

  const css = `
  .fb-btn{position:fixed;right:22px;bottom:22px;z-index:90;display:flex;align-items:center;gap:8px;
    padding:11px 16px;border-radius:30px;border:1px solid rgba(255,255,255,.16);cursor:pointer;
    background:linear-gradient(100deg,#6d6bff,#a06bff);color:#0a0a12;font:700 14px Inter,sans-serif;
    box-shadow:0 12px 34px rgba(120,110,255,.4)}
  .fb-btn:hover{transform:translateY(-1px)}
  .fb-bg{position:fixed;inset:0;z-index:130;background:rgba(5,5,9,.7);backdrop-filter:blur(8px);display:none;place-items:center;padding:20px}
  .fb-bg.on{display:grid}
  .fb-modal{width:100%;max-width:460px;border:1px solid rgba(255,255,255,.14);border-radius:20px;background:#0b0b14;
    color:#f2f2f7;padding:26px;box-shadow:0 40px 110px rgba(0,0,0,.7);font-family:Inter,sans-serif}
  .fb-modal h3{margin:0 0 4px;font-size:21px;letter-spacing:-.02em}
  .fb-modal .s{color:#8b8c9e;font-size:13.5px;margin:0 0 16px}
  .fb-cats{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}
  .fb-cat{display:flex;align-items:center;gap:8px;padding:10px 12px;border-radius:11px;cursor:pointer;font-size:13.5px;
    border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.03);color:#c4c5d4}
  .fb-cat.sel{border-color:#9a8bff;background:rgba(154,139,255,.14);color:#fff}
  .fb-modal textarea,.fb-modal input{width:100%;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.14);
    border-radius:10px;color:#f2f2f7;padding:11px 13px;font:14.5px Inter,sans-serif;outline:none;margin-bottom:12px;resize:vertical}
  .fb-modal textarea:focus,.fb-modal input:focus{border-color:#9a8bff}
  .fb-nps label{display:block;font-size:12.5px;color:#8b8c9e;margin-bottom:6px}
  .fb-nps input[type=range]{width:100%;margin:0 0 4px}
  .fb-nps-val{font-size:13px;color:#c4c5d4;margin-bottom:12px}
  .fb-act{display:flex;gap:10px}
  .fb-act button{flex:1;padding:11px;border-radius:11px;font:700 14px Inter,sans-serif;cursor:pointer;border:1px solid rgba(255,255,255,.16)}
  .fb-primary{background:linear-gradient(100deg,#6d6bff,#a06bff);color:#0a0a12;border:none}
  .fb-ghost{background:transparent;color:#c4c5d4}
  .fb-err{color:#ff7a90;font-size:12.5px;margin:-6px 0 10px;display:none}`;

  function refreshModalCopy() {
    const h = document.querySelector("#fbBg h3");
    const s = document.querySelector("#fbBg .s");
    const btn = document.getElementById("fbSend");
    if (h) h.textContent = productConfig.feedback_url_configured ? "Share feedback with Atlas" : "Save feedback locally";
    if (s) s.textContent = submitHint();
    if (btn) btn.textContent = submitLabel();
  }

  function inject() {
    if (document.getElementById("fb-style")) return;
    const st = document.createElement("style"); st.id = "fb-style"; st.textContent = css; document.head.appendChild(st);
    if (!document.querySelector(".fb-btn") && !document.body.dataset.fbHideButton) {
      const b = document.createElement("button"); b.className = "fb-btn"; b.innerHTML = "💬 Feedback";
      b.onclick = open; document.body.appendChild(b);
    }
    const bg = document.createElement("div"); bg.className = "fb-bg"; bg.id = "fbBg";
    bg.innerHTML = `<div class="fb-modal" onclick="event.stopPropagation()">
      <h3>Save feedback locally</h3><p class="s">Saved on this device only.</p>
      <div class="fb-cats" id="fbCats">${CATS.map(c => `<div class="fb-cat" data-c="${c.id}"><span>${c.icon}</span>${c.label}</div>`).join("")}</div>
      <textarea id="fbMsg" rows="4" placeholder="What happened, or what would make Atlas better?"></textarea>
      <div class="fb-nps"><label for="fbNps">How likely are you to recommend Atlas? (0–10, optional)</label>
      <input id="fbNps" type="range" min="0" max="10" step="1" value="8" />
      <div class="fb-nps-val"><span id="fbNpsVal">8</span> / 10</div></div>
      <div class="fb-err" id="fbErr">Please write a short message.</div>
      <input id="fbEmail" type="email" placeholder="Email (optional)" />
      <div class="fb-act"><button class="fb-primary" id="fbSend">Save locally</button><button class="fb-ghost" id="fbCancel">Cancel</button></div>
    </div>`;
    bg.onclick = close; document.body.appendChild(bg);
    bg.querySelectorAll(".fb-cat").forEach(el => el.onclick = () => {
      selected = el.dataset.c; bg.querySelectorAll(".fb-cat").forEach(x => x.classList.toggle("sel", x === el));
    });
    bg.querySelector(".fb-cat").classList.add("sel");
    document.getElementById("fbSend").onclick = submit;
    document.getElementById("fbCancel").onclick = close;
    const nps = document.getElementById("fbNps");
    const npsVal = document.getElementById("fbNpsVal");
    if (nps && npsVal) nps.oninput = () => { npsVal.textContent = nps.value; };
    loadConfig().then(refreshModalCopy);
  }
  function open(presetCategory, context) {
    inject();
    loadConfig().then(refreshModalCopy);
    if (presetCategory) {
      selected = presetCategory;
      const bg = document.getElementById("fbBg");
      if (bg) bg.querySelectorAll(".fb-cat").forEach(x => x.classList.toggle("sel", x.dataset.c === presetCategory));
    }
    pendingContext = context || null;
    if (context && context.diagnostics) {
      const ta = document.getElementById("fbMsg");
      if (ta && !ta.value.trim()) {
        ta.value = "Describe the issue here. Diagnostics are redacted — no source code is uploaded.";
      }
    }
    document.getElementById("fbBg").classList.add("on");
  }
  async function openReportIssue(context) {
    const ctx = context || {};
    if (!ctx.diagnostics) {
      try {
        if (typeof api === "function") ctx.diagnostics = await api("/api/system/diagnostics");
      } catch (e) {}
    }
    open("bug", ctx);
  }
  function close() { const b = document.getElementById("fbBg"); if (b) b.classList.remove("on"); }
  async function submit() {
    const msg = (document.getElementById("fbMsg").value || "").trim();
    const err = document.getElementById("fbErr");
    if (msg.length < 3) { err.style.display = "block"; return; }
    err.style.display = "none";
    const sendBtn = document.getElementById("fbSend");
    if (sendBtn) { sendBtn.disabled = true; sendBtn.textContent = "Sending…"; }
    const npsEl = document.getElementById("fbNps");
    const npsScore = npsEl && npsEl.value !== "" ? parseInt(npsEl.value, 10) : null;
    const entry = {
      category: selected, message: msg,
      email: (document.getElementById("fbEmail").value || "").trim(),
      nps_score: Number.isFinite(npsScore) ? npsScore : null,
      page: (location.pathname.split("/").pop() || "app"),
      user_agent: navigator.userAgent, ts: new Date().toISOString(),
      context: pendingContext ? { has_diagnostics: !!pendingContext.diagnostics } : undefined,
      destination: productConfig.feedback_url_configured ? "remote_attempt" : "local",
    };
    pendingContext = null;
    save(entry);
    let remoteMsg = "";
    let remoteSent = false;
    try {
      const r = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: selected, message: msg, email: entry.email, page: entry.page, nps_score: entry.nps_score }),
      });
      const data = await r.json();
      if (data && data.message) remoteMsg = data.message;
      if (data && data.remote_sent) remoteSent = true;
    } catch (e) {
      remoteMsg = "Saved on this device.";
    }
    try { if (typeof track === "function") track("feedback_saved", { category: selected }); } catch (e) {}
    // Show inline success state instead of closing immediately
    const modal = document.querySelector("#fbBg .fb-modal");
    if (modal) {
      modal.innerHTML = `<div style="text-align:center;padding:24px 0">
        <div style="font-size:36px;margin-bottom:12px">${remoteSent ? "✓" : "💾"}</div>
        <h3 style="margin:0 0 8px">${remoteSent ? "Sent — thank you!" : "Saved"}</h3>
        <p class="s" style="margin:0 0 16px">${remoteMsg || "Your feedback helps improve Atlas."}</p>
        <button class="fb-primary" style="padding:10px 22px;border-radius:10px;border:none;cursor:pointer;font:700 14px Inter,sans-serif;background:linear-gradient(100deg,#6d6bff,#a06bff);color:#0a0a12" onclick="AtlasFeedback.close()">Done</button>
      </div>`;
    } else {
      close();
    }
    document.getElementById("fbMsg") && (document.getElementById("fbMsg").value = "");
    document.getElementById("fbEmail") && (document.getElementById("fbEmail").value = "");
  }
  function exportJSON() {
    const data = JSON.stringify({ exported_at: new Date().toISOString(), count: list().length, feedback: list() }, null, 2);
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([data], { type: "application/json" }));
    a.download = "atlas_feedback.json"; a.click(); toast("Exported " + list().length + " local notes");
  }

  const apiObj = { open, close, submit, list, exportJSON, openReportIssue, count: () => list().length, categories: CATS, loadConfig };
  window.AtlasFeedback = apiObj;
  if (document.readyState !== "loading") inject(); else document.addEventListener("DOMContentLoaded", inject);
})();
