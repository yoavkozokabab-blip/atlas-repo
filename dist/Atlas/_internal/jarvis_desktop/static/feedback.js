"use strict";
/* Atlas feedback widget — stored locally only (no remote destination unless configured). */
(function () {
  const KEY = "jarvis_feedback";
  const REMOTE_FEEDBACK_URL = ""; // optional future hook; leave empty for local-only beta
  const CATS = [
    { id: "bug", label: "Bug", icon: "🐞" },
    { id: "confusing_ui", label: "Confusing UI", icon: "🧭" },
    { id: "missing_feature", label: "Missing feature", icon: "✨" },
    { id: "general", label: "General feedback", icon: "💬" },
  ];
  let selected = "general";
  let pendingContext = null;

  function list() { try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; } }
  function save(entry) { const l = list(); l.push(entry); localStorage.setItem(KEY, JSON.stringify(l)); return l.length; }
  function toast(m) {
    let t = document.getElementById("mtoast");
    if (!t) { t = document.createElement("div"); t.id = "mtoast"; t.className = "mtoast"; document.body.appendChild(t); }
    t.textContent = m; t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 2400);
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
  .fb-act{display:flex;gap:10px}
  .fb-act button{flex:1;padding:11px;border-radius:11px;font:700 14px Inter,sans-serif;cursor:pointer;border:1px solid rgba(255,255,255,.16)}
  .fb-primary{background:linear-gradient(100deg,#6d6bff,#a06bff);color:#0a0a12;border:none}
  .fb-ghost{background:transparent;color:#c4c5d4}
  .fb-err{color:#ff7a90;font-size:12.5px;margin:-6px 0 10px;display:none}`;

  function inject() {
    if (document.getElementById("fb-style")) return;
    const st = document.createElement("style"); st.id = "fb-style"; st.textContent = css; document.head.appendChild(st);
    if (!document.querySelector(".fb-btn") && !document.body.dataset.fbHideButton) {
      const b = document.createElement("button"); b.className = "fb-btn"; b.innerHTML = "💬 Feedback";
      b.onclick = open; document.body.appendChild(b);
    }
    const bg = document.createElement("div"); bg.className = "fb-bg"; bg.id = "fbBg";
    bg.innerHTML = `<div class="fb-modal" onclick="event.stopPropagation()">
      <h3>Save feedback locally</h3><p class="s">Saved on this device only. Nothing is uploaded unless a support URL is configured.</p>
      <div class="fb-cats" id="fbCats">${CATS.map(c => `<div class="fb-cat" data-c="${c.id}"><span>${c.icon}</span>${c.label}</div>`).join("")}</div>
      <textarea id="fbMsg" rows="4" placeholder="What happened, or what would make Atlas better?"></textarea>
      <div class="fb-err" id="fbErr">Please write a short message.</div>
      <input id="fbEmail" type="email" placeholder="Email (optional — stored locally with your note)" />
      <div class="fb-act"><button class="fb-primary" id="fbSend">Save locally</button><button class="fb-ghost" id="fbCancel">Cancel</button></div>
    </div>`;
    bg.onclick = close; document.body.appendChild(bg);
    bg.querySelectorAll(".fb-cat").forEach(el => el.onclick = () => {
      selected = el.dataset.c; bg.querySelectorAll(".fb-cat").forEach(x => x.classList.toggle("sel", x === el));
    });
    bg.querySelector(".fb-cat").classList.add("sel");
    document.getElementById("fbSend").onclick = submit;
    document.getElementById("fbCancel").onclick = close;
  }
  function open(presetCategory, context) {
    inject();
    if (presetCategory) {
      selected = presetCategory;
      const bg = document.getElementById("fbBg");
      if (bg) bg.querySelectorAll(".fb-cat").forEach(x => x.classList.toggle("sel", x.dataset.c === presetCategory));
    }
    pendingContext = context || null;
    if (context && context.diagnostics) {
      const ta = document.getElementById("fbMsg");
      if (ta && !ta.value.trim()) {
        ta.value = "Describe the issue here. Diagnostics stay on this device unless you export them.";
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
  function submit() {
    const msg = (document.getElementById("fbMsg").value || "").trim();
    const err = document.getElementById("fbErr");
    if (msg.length < 3) { err.style.display = "block"; return; }
    err.style.display = "none";
    const entry = {
      category: selected, message: msg,
      email: (document.getElementById("fbEmail").value || "").trim(),
      page: (location.pathname.split("/").pop() || "app"),
      user_agent: navigator.userAgent, ts: new Date().toISOString(),
      context: pendingContext || undefined,
      destination: REMOTE_FEEDBACK_URL || "local",
    };
    pendingContext = null;
    const n = save(entry);
    try { if (typeof track === "function") track("feedback_saved_local", { category: selected }); } catch (e) {}
    close();
    document.getElementById("fbMsg").value = ""; document.getElementById("fbEmail").value = "";
    toast("Saved locally (" + n + " note" + (n === 1 ? "" : "s") + " on this device).");
  }
  function exportJSON() {
    const data = JSON.stringify({ exported_at: new Date().toISOString(), count: list().length, feedback: list() }, null, 2);
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([data], { type: "application/json" }));
    a.download = "atlas_feedback.json"; a.click(); toast("Exported " + list().length + " local notes");
  }

  window.JarvisFeedback = { open, close, submit, list, exportJSON, openReportIssue, count: () => list().length, categories: CATS };
  if (document.readyState !== "loading") inject(); else document.addEventListener("DOMContentLoaded", inject);
})();
