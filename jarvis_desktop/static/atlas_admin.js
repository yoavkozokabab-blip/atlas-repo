"use strict";
/* Atlas Admin Console.
   In-app admin/superadmin control center: overview, pending applications,
   users, manual license/access, feedback inbox, audit log.
   All actions go through the existing backend authorization (the signed-in
   account's admin token, proxied via /api/accounts/admin/*). */
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c]));
  const toast = (m, k) => { if (typeof window.toast === "function") window.toast(m, k); };

  const STATE = { users: [], pending: [], dashboard: {}, feedback: [], audit: [], loaded: false, current: "overview" };

  async function api(path, method, body) {
    try {
      const r = await fetch(path, {
        method: method || "GET",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      return await r.json();
    } catch (e) {
      return { ok: false, error: "Network error" };
    }
  }

  function tab(name) {
    STATE.current = name;
    document.querySelectorAll("#view-admin .admin-tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
    document.querySelectorAll("#view-admin .admin-pane").forEach((p) => { p.hidden = (p.id !== "admin-pane-" + name); });
    const loaders = { overview: loadOverview, launch: loadLaunch, pending: loadPending, users: loadUsers, feedback: loadFeedback, audit: loadAudit };
    if (loaders[name]) loaders[name]();
  }

  // ── Overview ───────────────────────────────────────────────────────────────
  async function loadOverview() {
    const host = $("admin-kpis");
    const r = await api("/api/accounts/admin/dashboard");
    const svc = await api("/api/accounts/service-status");
    const h = $("admin-health");
    if (h) h.innerHTML = svc && svc.running ? '<span class="ok">● accounts service healthy</span>' : '<span class="bad">● accounts service unreachable</span>';
    if (!r || !r.ok) { host.innerHTML = `<p class="muted">${esc((r && r.error) || "Admin access required.")}</p>`; return; }
    const d = r.dashboard || {};
    STATE.dashboard = d;
    const badge = $("admin-pending-count");
    if (badge) badge.textContent = d.pending_applications ? String(d.pending_applications) : "";
    const kpis = [
      ["Total users", d.total_users], ["Pending applications", d.pending_applications],
      ["Users with access", d.beta_users], ["Active users", d.active_users],
      ["Suspended", d.suspended_users], ["Banned", d.banned_users],
      ["Feedback pending", d.feedback_pending], ["Active devices", d.active_devices],
    ];
    host.innerHTML = kpis.map(([l, v]) => `<div class="admin-kpi"><div class="admin-kpi-v">${esc(v == null ? "—" : v)}</div><div class="admin-kpi-l">${esc(l)}</div></div>`).join("");
  }

  // ── Pending applications ─────────────────────────────────────────────────────
  function profileRows(p) {
    p = p || {};
    const list = (v) => Array.isArray(v) ? v.join(", ") : (v || "—");
    const rows = [
      ["Role", p.primary_role], ["Experience", p.developer_experience], ["Currently a developer", p.currently_developer === false ? "No" : (p.currently_developer ? "Yes" : "—")],
      ["Company", p.company_name], ["Company size", p.company_size], ["Intended use", p.project_use],
      ["Repo size", p.repo_size], ["Languages", p.languages_frameworks], ["AI tools", list(p.coding_tools)],
      ["Goals", list(p.atlas_help)], ["Notes", p.notes],
    ];
    return rows.map(([k, v]) => `<div class="admin-kv"><span>${esc(k)}</span><b>${esc(v || "—")}</b></div>`).join("");
  }

  async function loadPending() {
    const host = $("admin-pending-list");
    const r = await api("/api/accounts/admin/applications/pending");
    if (!r || !r.ok) { host.innerHTML = `<p class="muted">${esc((r && r.error) || "Admin access required.")}</p>`; return; }
    STATE.pending = r.applications || [];
    if (!STATE.pending.length) { host.innerHTML = '<p class="muted admin-empty">No pending applications. 🎉</p>'; return; }
    host.innerHTML = STATE.pending.map((a) => `
      <div class="admin-app-card glass" data-uid="${esc(a.user_id)}">
        <div class="admin-app-head">
          <div><b>${esc(a.email)}</b><span class="admin-app-time">${esc((a.created_at || "").slice(0, 16).replace("T", " "))}</span></div>
          <div class="admin-app-actions">
            <button class="btn primary small" onclick="adminConsole.approve('${esc(a.user_id)}','${esc(a.email)}')">Approve access</button>
            <button class="btn danger small" onclick="adminConsole.reject('${esc(a.user_id)}','${esc(a.email)}')">Reject</button>
            <button class="btn ghost small" onclick="adminConsole.note('${esc(a.user_id)}')">Add note</button>
          </div>
        </div>
        <div class="admin-app-grid">${profileRows(a.beta_profile)}</div>
      </div>`).join("");
  }

  // ── Users ────────────────────────────────────────────────────────────────────
  async function loadUsers() {
    const r = await api("/api/accounts/admin/users");
    if (!r || !r.ok) { $("admin-users-rows").innerHTML = `<tr><td colspan="8" class="muted" style="padding:16px">${esc((r && r.error) || "Admin access required.")}</td></tr>`; return; }
    STATE.users = r.users || [];
    renderUsers();
  }

  function renderUsers() {
    const q = ($("admin-user-search") && $("admin-user-search").value || "").toLowerCase().trim();
    const f = ($("admin-user-filter") && $("admin-user-filter").value) || "";
    const rows = STATE.users.filter((u) =>
      (!q || (u.email || "").toLowerCase().includes(q)) && (!f || u.status === f));
    const body = $("admin-users-rows");
    if (!rows.length) { body.innerHTML = '<tr><td colspan="8" class="muted" style="padding:16px">No matching users.</td></tr>'; return; }
    body.innerHTML = rows.map((u) => {
      const lic = u.license || {};
      const license = [lic.plan, lic.status].filter(Boolean).join(" / ") || "—";
      const last = (u.last_seen_at || "").slice(0, 10) || "—";
      return `<tr>
        <td>${esc(u.email)}</td>
        <td><span class="admin-pill s-${esc(u.status)}">${esc(u.status)}</span></td>
        <td>${esc(u.role)}</td>
        <td>${esc(license)}</td>
        <td>${u.beta_flag ? "Yes" : "No"}</td>
        <td>${esc(u.device_count || 0)}</td>
        <td class="muted">${esc(last)}</td>
        <td class="admin-row-actions">
          ${u.status === "pending" || !u.beta_flag ? `<button class="btn ghost small" onclick="adminConsole.act('grant-beta','${esc(u.user_id)}','${esc(u.email)}')">Enable access</button>` : `<button class="btn ghost small" onclick="adminConsole.act('revoke-beta','${esc(u.user_id)}','${esc(u.email)}')">Disable access</button>`}
          <button class="btn ghost small" onclick="adminConsole.editLicense('${esc(u.user_id)}')">License</button>
          ${u.status === "suspended" || u.status === "banned" ? `<button class="btn ghost small" onclick="adminConsole.setStatus('${esc(u.user_id)}','active','${esc(u.email)}')">Reinstate</button>` : `<button class="btn ghost small" onclick="adminConsole.setStatus('${esc(u.user_id)}','suspended','${esc(u.email)}')">Suspend</button>`}
          <button class="btn ghost small danger-text" onclick="adminConsole.setStatus('${esc(u.user_id)}','banned','${esc(u.email)}')">Ban</button>
          <button class="btn ghost small" onclick="adminConsole.act('force-logout','${esc(u.user_id)}','${esc(u.email)}')">Force logout</button>
        </td>
      </tr>`;
    }).join("");
  }

  // ── License / access editor ───────────────────────────────────────────────────
  function editLicense(uid) {
    const u = STATE.users.find((x) => x.user_id === uid);
    if (!u) return;
    tab("access");
    const lic = u.license || {};
    const sel = (id, val, opts) => `<select id="${id}">${opts.map((o) => `<option value="${o[0]}"${o[0] === val ? " selected" : ""}>${o[1]}</option>`).join("")}</select>`;
    $("admin-access-editor").innerHTML = `
      <div class="admin-access-card glass">
        <h3>License &amp; access — ${esc(u.email)}</h3>
        <div class="admin-form-grid">
          <label>Plan ${sel("acc-edit-plan", lic.plan || "free", [["free", "free"], ["beta", "standard"], ["pro", "pro"], ["enterprise", "enterprise (manual)"]])}</label>
          <label>Status ${sel("acc-edit-status", u.status, [["pending", "pending"], ["active", "active"], ["beta", "standard"], ["suspended", "suspended"], ["banned", "banned"], ["expired", "expired"]])}</label>
          <label>Role ${sel("acc-edit-role", u.role, [["user", "user"], ["admin", "admin"], ["superadmin", "superadmin"]])}</label>
          <label>Max devices <input id="acc-edit-devices" type="number" min="1" max="20" value="${esc((lic.max_devices) || 1)}" /></label>
          <label>Expiry (YYYY-MM-DD) <input id="acc-edit-expiry" type="text" placeholder="none" value="${esc((lic.expires_at || "").slice(0, 10))}" /></label>
          <label class="admin-check"><input id="acc-edit-beta" type="checkbox" ${u.beta_flag ? "checked" : ""}/> Access flag</label>
        </div>
        <div class="admin-modal-actions">
          <button class="btn ghost" onclick="adminConsole.tab('users')">Back to users</button>
          <button class="btn primary" onclick="adminConsole.saveLicense('${esc(uid)}')">Save changes</button>
        </div>
        <p class="muted tiny">Manual access management only — no payments. Role changes require superadmin.</p>
      </div>`;
  }

  async function saveLicense(uid) {
    const payload = {
      user_id: uid,
      plan: $("acc-edit-plan").value,
      status: $("acc-edit-status").value,
      role: $("acc-edit-role").value,
      max_devices: parseInt($("acc-edit-devices").value, 10) || 1,
      beta_flag: $("acc-edit-beta").checked,
    };
    const exp = $("acc-edit-expiry").value.trim();
    if (exp) payload.expires_at = exp;
    const r = await api("/api/accounts/admin/users/update", "POST", payload);
    if (r && r.ok) { toast("Saved", "success"); await loadUsers(); tab("users"); }
    else toast((r && r.error) || "Update failed", "error");
  }

  // ── Launch readiness ───────────────────────────────────────────────────────
  function pct(v) {
    if (v == null || Number.isNaN(v)) return "—";
    return Math.round(v * 100) + "%";
  }

  async function loadLaunch() {
    const host = $("admin-launch-root");
    const [lr, local] = await Promise.all([
      api("/api/accounts/admin/launch-readiness"),
      api("/api/analytics/summary"),
    ]);
    if (!lr || !lr.ok) {
      host.innerHTML = `<p class="muted">${esc((lr && lr.error) || "Admin access required.")}</p>`;
      return;
    }
    const d = lr.readiness || {};
    const v = d.launch_verdict || {};
    const nps = d.nps || {};
    const ret = d.weekly_retention || {};
    const funnel = d.funnel_counts || {};
    const conv = d.funnel_conversion || {};
    const localCounts = (local && local.counts) || {};

    host.innerHTML = `
      <div class="admin-verdict ${esc(v.verdict || "mixed_signal")}">
        <h2>Do users actually want Atlas?</h2>
        <p class="muted">${esc(v.headline || "")}</p>
        <p class="tiny muted">Adoption target: ${esc(d.active_beta_users || 0)} / ${esc(v.beta_target || 25)} users · progress ${esc(Math.round((v.beta_target_progress || 0) * 100))}%</p>
      </div>
      <div class="admin-kpis">
        ${[
          ["Sign-ups", d.waitlist_count],
          ["Active accounts", d.active_beta_users],
          ["Weekly retention", pct(ret.weekly_retention_rate)],
          ["NPS", nps.nps_score == null ? "—" : nps.nps_score],
          ["Critical bugs", d.critical_bugs],
          ["Feature requests", d.open_feature_requests],
          ["Local installs", localCounts.app_started || funnel.app_installed || 0],
        ].map(([l, val]) => `<div class="admin-kpi"><div class="admin-kpi-v">${esc(val == null ? "—" : val)}</div><div class="admin-kpi-l">${esc(l)}</div></div>`).join("")}
      </div>
      <h3 class="admin-section-title">Acquisition funnel</h3>
      <div class="admin-funnel">
        ${["landing_visit", "waitlist_signup", "app_installed", "registered", "approved", "first_scan", "weekly_active"].map((s) =>
          `<div class="admin-funnel-step"><b>${esc(funnel[s] || 0)}</b><span>${esc(s.replace(/_/g, " "))}</span></div>`
        ).join("")}
      </div>
      <p class="muted tiny">Registered→approved: ${pct(conv.registered_to_approved)} · Approved→first scan: ${pct(conv.approved_to_first_scan)}</p>
      <div class="admin-launch-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px">
        <div class="glass" style="padding:14px;border-radius:12px">
          <h4>Top feature requests</h4>
          <ul class="admin-rank-list">${(d.top_feature_requests || []).map((x) => `<li>${esc(x.message)} <span class="muted">(${esc(x.count)})</span></li>`).join("") || "<li class='muted'>None yet</li>"}</ul>
        </div>
        <div class="glass" style="padding:14px;border-radius:12px">
          <h4>Top complaints</h4>
          <ul class="admin-rank-list">${(d.top_complaints || []).map((x) => `<li><b>${esc(x.category)}</b> — ${esc(x.message)} <span class="muted">(${esc(x.count)})</span></li>`).join("") || "<li class='muted'>None yet</li>"}</ul>
        </div>
      </div>
      <div class="admin-toolbar" style="margin-top:16px">
        <button class="btn primary small" type="button" onclick="adminConsole.exportBetaUsers()">Export users</button>
        <button class="btn ghost small" type="button" onclick="adminConsole.loadInterviewSummary()">Feedback summary</button>
        <button class="btn ghost small" type="button" onclick="adminConsole.createInvite()">Create access code</button>
      </div>
      <div id="admin-launch-extra" class="muted tiny" style="margin-top:10px"></div>
      <div id="admin-invites-list" style="margin-top:12px"></div>`;
    loadInvites();
  }

  async function loadInvites() {
    const host = $("admin-invites-list");
    if (!host) return;
    const r = await api("/api/accounts/admin/invites");
    if (!r || !r.ok) { host.innerHTML = ""; return; }
    const items = r.invites || [];
    if (!items.length) { host.innerHTML = "<p class='muted tiny'>No access codes yet.</p>"; return; }
    host.innerHTML = `<table class="admin-table"><thead><tr><th>Code</th><th>Email</th><th>Uses</th><th>Status</th><th>Expires</th></tr></thead><tbody>${
      items.map((i) => `<tr><td><code>${esc(i.code)}</code></td><td>${esc(i.email || "—")}</td><td>${esc(i.use_count)}/${esc(i.max_uses)}</td><td>${esc(i.status)}</td><td class="muted">${esc((i.expires_at || "").slice(0, 10) || "—")}</td></tr>`).join("")
    }</tbody></table>`;
  }

  async function exportBetaUsers() {
    const r = await api("/api/accounts/admin/export/beta-users");
    if (!r || !r.ok) { toast((r && r.error) || "Export failed", "error"); return; }
    const blob = new Blob([JSON.stringify(r.users || [], null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "atlas-users.json";
    a.click();
    toast("Exported users", "success");
  }

  async function loadInterviewSummary() {
    const r = await api("/api/accounts/admin/interview-summary");
    const extra = $("admin-launch-extra");
    if (!extra) return;
    if (!r || !r.ok) { toast((r && r.error) || "Summary failed", "error"); return; }
    const s = r.summary || {};
    extra.innerHTML = `<pre style="white-space:pre-wrap;font-size:12px">${esc(JSON.stringify(s, null, 2))}</pre>`;
  }

  async function createInvite() {
    const email = window.prompt("Reserve for email (optional — leave blank for an open code):", "") || "";
    const r = await api("/api/accounts/admin/invites", "POST", { email: email.trim() || undefined, max_uses: 1, expires_days: 30 });
    if (r && r.ok && r.invite) {
      toast(`Access code created: ${r.invite.code}`, "success");
      loadInvites();
    } else toast((r && r.error) || "Create failed", "error");
  }

  // ── Feedback inbox ─────────────────────────────────────────────────────────────
  async function loadFeedback() {
    const r = await api("/api/accounts/admin/feedback?limit=100");
    const body = $("admin-feedback-rows");
    if (!r || !r.ok) {
      const legacy = await api("/api/operations/result-feedback");
      if (!legacy || !legacy.ok) { body.innerHTML = `<tr><td colspan="7" class="muted" style="padding:16px">${esc((r && r.error) || "Feedback unavailable.")}</td></tr>`; return; }
      const items = legacy.items || [];
      body.innerHTML = items.map((it) => `<tr>
        <td>${esc(it.workflow || it.category)}</td><td>—</td><td>—</td>
        <td class="muted">${esc(it.comment || "—")}</td><td>—</td>
        <td class="muted">${esc((it.timestamp || "").slice(0, 16).replace("T", " "))}</td><td></td></tr>`).join("") || `<tr><td colspan="7" class="muted" style="padding:16px">No feedback yet.</td></tr>`;
      return;
    }
    const items = r.items || [];
    if (!items.length) { body.innerHTML = '<tr><td colspan="7" class="muted" style="padding:16px">No feedback yet.</td></tr>'; return; }
    body.innerHTML = items.map((it) => `<tr>
      <td>${esc(it.category)}</td>
      <td>${esc(it.sentiment || "—")}</td>
      <td>${it.nps_score == null ? "—" : esc(it.nps_score)}</td>
      <td class="muted">${esc(it.message_redacted || "—")}</td>
      <td><span class="admin-pill s-${esc(it.status)}">${esc(it.status)}</span></td>
      <td class="muted">${esc((it.created_at || "").slice(0, 16).replace("T", " "))}</td>
      <td>${it.status === "pending" ? `<button class="btn ghost small" onclick="adminConsole.markFeedback('${esc(it.feedback_id)}','reviewed')">Review</button>` : ""}</td>
    </tr>`).join("");
  }

  async function markFeedback(fid, status) {
    const r = await api("/api/accounts/admin/feedback/update", "POST", { feedback_id: fid, status });
    if (r && r.ok) { toast("Updated", "success"); loadFeedback(); loadLaunch(); }
    else toast((r && r.error) || "Update failed", "error");
  }

  // ── Audit log ──────────────────────────────────────────────────────────────────
  async function loadAudit() {
    const r = await api("/api/accounts/admin/audit-log");
    const body = $("admin-audit-rows");
    if (!r || !r.ok) { body.innerHTML = `<tr><td colspan="5" class="muted" style="padding:16px">${esc((r && r.error) || "Admin access required.")}</td></tr>`; return; }
    STATE.audit = r.entries || [];
    if (!STATE.audit.length) { body.innerHTML = '<tr><td colspan="5" class="muted" style="padding:16px">No audit entries.</td></tr>'; return; }
    body.innerHTML = STATE.audit.map((e) => `<tr>
      <td class="muted">${esc((e.created_at || "").slice(0, 16).replace("T", " "))}</td>
      <td><b>${esc(e.action)}</b></td>
      <td>${esc(e.admin_email || "—")}</td>
      <td>${esc(e.target_user_email || e.target_device_id || "—")}</td>
      <td class="muted">${esc(e.action_id ? e.action_id.slice(0, 8) : "")}</td>
    </tr>`).join("");
  }

  // ── Actions ─────────────────────────────────────────────────────────────────────
  async function _post(path, body, okMsg) {
    const r = await api(path, "POST", body);
    if (r && r.ok) { toast(okMsg || "Done", "success"); await loadUsers(); if (STATE.current === "pending") await loadPending(); await loadOverview(); }
    else toast((r && r.error) || "Action failed", "error");
    return r;
  }

  async function approve(uid, email) { await _post("/api/accounts/admin/applications/approve", { user_id: uid }, `Approved ${email}`); if (STATE.current === "pending") loadPending(); }
  async function reject(uid, email) { confirmModal("Reject application", `Reject the sign-up application from ${email}? They will not get access.`, async () => { await _post("/api/accounts/admin/applications/reject", { user_id: uid }, `Rejected ${email}`); loadPending(); }); }
  function note(uid) {
    const text = window.prompt("Internal note for this applicant (operator-only):", "");
    if (text == null) return;
    _post("/api/accounts/admin/users/update", { user_id: uid, admin_notes: text }, "Note saved");
  }
  function act(action, uid, email) {
    const dangerous = action === "force-logout";
    const run = () => _post(`/api/accounts/admin/users/${action}`, { user_id: uid }, `${action.replace("-", " ")} — ${email}`);
    if (dangerous) confirmModal("Force logout", `Force logout ${email} from all devices?`, run);
    else run();
  }
  function setStatus(uid, status, email) {
    const danger = { suspended: "Suspend", banned: "Ban" };
    const run = () => _post("/api/accounts/admin/users/update", { user_id: uid, status }, `${email} → ${status}`);
    if (danger[status]) confirmModal(danger[status] + " user", `${danger[status]} ${email}? This blocks their access${status === "banned" ? " permanently (until reinstated)" : ""}.`, run);
    else run();
  }

  // ── Confirm modal ────────────────────────────────────────────────────────────────
  function confirmModal(title, body, onOk) {
    $("admin-confirm-title").textContent = title;
    $("admin-confirm-body").textContent = body;
    const ok = $("admin-confirm-ok");
    ok.onclick = () => { closeConfirm(); onOk(); };
    $("admin-confirm").style.display = "grid";
  }
  function closeConfirm() { $("admin-confirm").style.display = "none"; }

  function refresh() { tab(STATE.current); }

  function enter() {
    if (!STATE.loaded) { STATE.loaded = true; }
    tab(STATE.current || "overview");
  }

  // Load when the admin view is shown.
  document.addEventListener("atlas:viewchange", (e) => {
    if (e.detail && e.detail.view === "admin") enter();
  });

  window.adminConsole = {
    tab, refresh, enter, approve, reject, note, act, setStatus,
    editLicense, saveLicense, renderUsers, closeConfirm,
    exportBetaUsers, loadInterviewSummary, createInvite, markFeedback,
  };
})();
