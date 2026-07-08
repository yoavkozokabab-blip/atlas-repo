"use strict";
/* Atlas Admin Workspace — accounts admin + launch analytics (Supabase funnel). */
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c]));
  const toast = (m, k) => { if (typeof window.toast === "function") window.toast(m, k); };

  const STATE = { users: [], pending: [], dashboard: {}, analytics: null, feedback: [], audit: [], loaded: false, current: "overview" };

  async function api(path, method, body) {
    try {
      const r = await fetch(path, {
        method: method || "GET",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
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
    const loaders = { overview: loadOverview, status: loadStatus, users: loadUsers, feedback: loadFeedback, audit: loadAudit };
    if (loaders[name]) loaders[name]();
  }

  function fmtSec(sec) {
    if (sec == null || Number.isNaN(sec)) return "—";
    if (sec < 60) return sec + "s";
    if (sec < 3600) return Math.round(sec / 60) + "m";
    return (sec / 3600).toFixed(1) + "h";
  }

  function renderAnalytics(data) {
    const host = $("admin-analytics-root");
    if (!host) return;
    if (!data || !data.ok) {
      host.innerHTML = `<p class="muted tiny">${esc((data && data.error) || "Launch analytics unavailable.")}</p>`;
      return;
    }
    STATE.analytics = data;
    const funnelRows = (data.funnel || []).map((step) =>
      `<tr><td>${esc(step.label)}</td><td>${esc(step.count)}</td><td>${step.conversionFromPrev == null ? "—" : esc(step.conversionFromPrev) + "%"}</td></tr>`
    ).join("");
    const drop = data.drop_off
      ? `<p class="muted tiny">Biggest drop-off: <b>${esc(data.drop_off.from)} → ${esc(data.drop_off.to)}</b> (${esc(data.drop_off.dropPct)}% lost)</p>`
      : "";
    host.innerHTML = `
      <h3 class="admin-section-title">Launch analytics</h3>
      <p class="muted tiny">From Supabase · ${esc(new Date(data.generated_at || Date.now()).toLocaleString())} · backend ${esc(data.backend || "—")}</p>
      <div class="admin-table-wrap" style="margin-top:10px">
        <table class="admin-table">
          <thead><tr><th>Funnel step</th><th>Count</th><th>Conversion</th></tr></thead>
          <tbody>${funnelRows || "<tr><td colspan='3' class='muted'>No events yet.</td></tr>"}</tbody>
        </table>
      </div>
      ${drop}
      <div class="admin-kpis" style="margin-top:14px">
        ${[
          ["Total TTFV", fmtSec((data.ttfv || {}).total_ttfv_sec)],
          ["Install → Open", fmtSec((data.ttfv || {}).install_to_open_sec)],
          ["Day 1 retention", (data.retention && data.retention.d1 != null) ? data.retention.d1 + "%" : "—"],
          ["Day 7 retention", (data.retention && data.retention.d7 != null) ? data.retention.d7 + "%" : "—"],
          ["Most used agent", (data.agents && data.agents.most_used) || "—"],
          ["Events tracked", data.events_total],
        ].map(([l, v]) => `<div class="admin-kpi"><div class="admin-kpi-v">${esc(v)}</div><div class="admin-kpi-l">${esc(l)}</div></div>`).join("")}
      </div>
      <p class="muted tiny" style="margin-top:10px">
        Agents connected — Cursor: ${esc(((data.agents || {}).connected || {}).cursor || 0)},
        Claude: ${esc(((data.agents || {}).connected || {}).claude || 0)},
        Codex: ${esc(((data.agents || {}).connected || {}).codex || 0)}
        · Used — Cursor: ${esc(((data.agents || {}).used || {}).cursor || 0)},
        Claude: ${esc(((data.agents || {}).used || {}).claude || 0)},
        Codex: ${esc(((data.agents || {}).used || {}).codex || 0)}
      </p>`;
  }

  async function loadOverview() {
    const host = $("admin-kpis");
    const [dash, analytics, svc] = await Promise.all([
      api("/api/accounts/admin/dashboard"),
      api("/api/accounts/admin/analytics-dashboard"),
      api("/api/accounts/service-status"),
    ]);
    const h = $("admin-health");
    if (h) {
      h.innerHTML = svc && svc.running
        ? '<span class="ok">● accounts service healthy</span>'
        : '<span class="bad">● accounts service unreachable</span>';
    }
    if (!dash || !dash.ok) {
      host.innerHTML = `<p class="muted">${esc((dash && dash.error) || "Admin access required.")}</p>`;
      renderAnalytics(analytics);
      return;
    }
    const d = dash.dashboard || {};
    STATE.dashboard = d;
    const badge = $("admin-status-count");
    if (badge) badge.textContent = d.pending_applications ? String(d.pending_applications) : "";
    const kpis = [
      ["Total users", d.total_users],
      ["Pending applications", d.pending_applications],
      ["Users with access", d.beta_users],
      ["Active users", d.active_users],
      ["Suspended", d.suspended_users],
      ["Banned", d.banned_users],
      ["Feedback pending", d.feedback_pending],
      ["Active devices", d.active_devices],
    ];
    host.innerHTML = kpis.map(([l, v]) =>
      `<div class="admin-kpi"><div class="admin-kpi-v">${esc(v == null ? "—" : v)}</div><div class="admin-kpi-l">${esc(l)}</div></div>`
    ).join("");
    renderAnalytics(analytics);
  }

  function profileRows(p) {
    p = p || {};
    const list = (v) => Array.isArray(v) ? v.join(", ") : (v || "—");
    const rows = [
      ["Role", p.primary_role], ["Experience", p.developer_experience],
      ["Currently a developer", p.currently_developer === false ? "No" : (p.currently_developer ? "Yes" : "—")],
      ["Company", p.company_name], ["Company size", p.company_size], ["Intended use", p.project_use],
      ["Repo size", p.repo_size], ["Languages", p.languages_frameworks], ["AI tools", list(p.coding_tools)],
      ["Goals", list(p.atlas_help)], ["Notes", p.notes],
    ];
    return rows.map(([k, v]) => `<div class="admin-kv"><span>${esc(k)}</span><b>${esc(v || "—")}</b></div>`).join("");
  }

  async function loadStatus() {
    const host = $("admin-status-list");
    const r = await api("/api/accounts/admin/applications/pending");
    if (!r || !r.ok) {
      host.innerHTML = `<p class="muted">${esc((r && r.error) || "Admin access required.")}</p>`;
      return;
    }
    STATE.pending = r.applications || [];
    if (!STATE.pending.length) {
      host.innerHTML = '<p class="muted admin-empty">No pending applications.</p>';
      return;
    }
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

  async function loadUsers() {
    const r = await api("/api/accounts/admin/users");
    if (!r || !r.ok) {
      $("admin-users-rows").innerHTML = `<tr><td colspan="8" class="muted" style="padding:16px">${esc((r && r.error) || "Admin access required.")}</td></tr>`;
      return;
    }
    STATE.users = r.users || [];
    renderUsers();
  }

  function renderUsers() {
    const q = ($("admin-user-search") && $("admin-user-search").value || "").toLowerCase().trim();
    const f = ($("admin-user-filter") && $("admin-user-filter").value) || "";
    const rows = STATE.users.filter((u) =>
      (!q || (u.email || "").toLowerCase().includes(q)) && (!f || u.status === f));
    const body = $("admin-users-rows");
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="8" class="muted" style="padding:16px">No matching users.</td></tr>';
      return;
    }
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
        <p class="muted tiny">Manual access management only — no payments.</p>
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

  async function loadFeedback() {
    const r = await api("/api/accounts/admin/feedback?limit=100");
    const body = $("admin-feedback-rows");
    if (!r || !r.ok) {
      const legacy = await api("/api/operations/result-feedback");
      if (!legacy || !legacy.ok) {
        body.innerHTML = `<tr><td colspan="6" class="muted" style="padding:16px">${esc((r && r.error) || "Feedback unavailable.")}</td></tr>`;
        return;
      }
      const items = legacy.items || [];
      body.innerHTML = items.map((it) => `<tr>
        <td>${esc(it.workflow || it.category)}</td><td>—</td><td>—</td>
        <td class="muted">${esc(it.comment || "—")}</td><td>—</td>
        <td class="muted">${esc((it.timestamp || "").slice(0, 16).replace("T", " "))}</td></tr>`).join("")
        || `<tr><td colspan="6" class="muted" style="padding:16px">No feedback yet.</td></tr>`;
      return;
    }
    const items = r.items || [];
    if (!items.length) {
      body.innerHTML = '<tr><td colspan="6" class="muted" style="padding:16px">No feedback yet.</td></tr>';
      return;
    }
    body.innerHTML = items.map((it) => `<tr>
      <td>${esc(it.category || it.workflow || "—")}</td>
      <td>${esc(it.sentiment || (it.useful == null ? "—" : (it.useful ? "yes" : "no")))}</td>
      <td>${esc(it.category || "—")}</td>
      <td class="muted">${esc(it.message_redacted || it.comment || "—")}</td>
      <td>${esc(it.user_email || "—")}</td>
      <td class="muted">${esc((it.created_at || it.timestamp || "").slice(0, 16).replace("T", " "))}</td>
    </tr>`).join("");
  }

  async function loadAudit() {
    const r = await api("/api/accounts/admin/audit-log");
    const body = $("admin-audit-rows");
    if (!r || !r.ok) {
      body.innerHTML = `<tr><td colspan="5" class="muted" style="padding:16px">${esc((r && r.error) || "Admin access required.")}</td></tr>`;
      return;
    }
    STATE.audit = r.entries || [];
    if (!STATE.audit.length) {
      body.innerHTML = '<tr><td colspan="5" class="muted" style="padding:16px">No audit entries.</td></tr>';
      return;
    }
    body.innerHTML = STATE.audit.map((e) => `<tr>
      <td class="muted">${esc((e.created_at || "").slice(0, 16).replace("T", " "))}</td>
      <td><b>${esc(e.action)}</b></td>
      <td>${esc(e.admin_email || "—")}</td>
      <td>${esc(e.target_user_email || e.target_device_id || "—")}</td>
      <td class="muted">${esc(e.action_id ? e.action_id.slice(0, 8) : "")}</td>
    </tr>`).join("");
  }

  async function _post(path, body, okMsg) {
    const r = await api(path, "POST", body);
    if (r && r.ok) {
      toast(okMsg || "Done", "success");
      await loadUsers();
      if (STATE.current === "status") await loadStatus();
      await loadOverview();
    } else toast((r && r.error) || "Action failed", "error");
    return r;
  }

  async function approve(uid, email) {
    await _post("/api/accounts/admin/applications/approve", { user_id: uid }, `Approved ${email}`);
    if (STATE.current === "status") loadStatus();
  }

  async function reject(uid, email) {
    confirmModal("Reject application", `Reject the sign-up application from ${email}?`, async () => {
      await _post("/api/accounts/admin/applications/reject", { user_id: uid }, `Rejected ${email}`);
      loadStatus();
    });
  }

  function note(uid) {
    const text = window.prompt("Internal note for this applicant (operator-only):", "");
    if (text == null) return;
    _post("/api/accounts/admin/users/update", { user_id: uid, admin_notes: text }, "Note saved");
  }

  function act(action, uid, email) {
    const run = () => _post(`/api/accounts/admin/users/${action}`, { user_id: uid }, `${action.replace("-", " ")} — ${email}`);
    if (action === "force-logout") confirmModal("Force logout", `Force logout ${email} from all devices?`, run);
    else run();
  }

  function setStatus(uid, status, email) {
    const danger = { suspended: "Suspend", banned: "Ban" };
    const run = () => _post("/api/accounts/admin/users/update", { user_id: uid, status }, `${email} → ${status}`);
    if (danger[status]) confirmModal(danger[status] + " user", `${danger[status]} ${email}?`, run);
    else run();
  }

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
    STATE.loaded = true;
    tab(STATE.current || "overview");
  }

  document.addEventListener("atlas:viewchange", (e) => {
    if (e.detail && e.detail.view === "admin") enter();
  });

  window.adminConsole = {
    tab, refresh, enter, approve, reject, note, act, setStatus,
    editLicense, saveLicense, renderUsers, closeConfirm,
  };
})();
