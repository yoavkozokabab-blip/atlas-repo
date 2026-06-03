/* Phase 137A — billing-ready UI (local/mock, no payments). */
(function () {
  "use strict";
  var page = document.body.getAttribute("data-billing-page");

  function getJSON(url) {
    return fetch(url).then(function (r) { return r.json(); }).catch(function () { return { ok: false }; });
  }
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]; }); }
  function cap(v) { return v === "unlimited" || v === -1 ? "Unlimited" : v; }

  function flagNote(enabled, enforcement) {
    var n = document.getElementById("flagNote");
    if (!n) return;
    if (enabled) {
      n.textContent = "Billing UI enabled (ATLAS_BILLING_UI_ENABLED=true). Enforcement: " + (enforcement ? "on" : "off") + " · Payments: disabled · No Stripe.";
    } else {
      n.textContent = "Preview only — billing UI is gated off (ATLAS_BILLING_UI_ENABLED=false). No enforcement, no payments.";
    }
  }

  function renderPricing(data) {
    var grid = document.getElementById("planGrid");
    grid.innerHTML = "";
    (data.plans || []).forEach(function (p) {
      var card = el("div", "plan-card" + (p.id === "PRO" ? " featured" : ""));
      card.appendChild(el("h3", null, esc(p.name)));
      card.appendChild(el("div", "plan-price", esc(p.price_display)));
      card.appendChild(el("div", "plan-tag", esc(p.tagline)));
      card.appendChild(el("div", "plan-avail", esc(p.availability)));
      var ul = el("ul", "plan-feat");
      (p.features || []).forEach(function (f) { ul.appendChild(el("li", null, esc(f))); });
      card.appendChild(ul);
      var btn = el("a", "btn primary");
      btn.textContent = p.cta || "Join beta";
      btn.href = "contact.html";
      card.appendChild(btn);
      grid.appendChild(card);
    });
  }

  function renderUsage(d) {
    if (!d || !d.ok) { document.getElementById("usageCards").innerHTML = "<p class='muted'>Usage unavailable.</p>"; return; }
    var plan = d.plan || {};
    var usage = d.usage || {};
    document.getElementById("planLine").textContent =
      "Plan: " + (plan.name || "Free") + " — " + (plan.availability || d.upgrade_note || "");
    var cards = document.getElementById("usageCards");
    cards.innerHTML = "";
    var stats = [
      ["Repositories", usage.repositories_used || 0],
      ["Scans this month", usage.scans_used || 0],
      ["Exports this month", usage.exports_used || 0],
      ["Build plans", usage.build_plans || 0],
      ["Investigations", usage.investigations || 0],
      ["Atlas compute units", usage.token_equivalent_total || 0]
    ];
    stats.forEach(function (s) {
      var c = el("div", "ucard");
      c.appendChild(el("div", "num", esc(s[1])));
      c.appendChild(el("div", "lbl", esc(s[0])));
      cards.appendChild(c);
    });
    var lim = document.getElementById("limits");
    lim.innerHTML = "";
    var checks = d.limit_checks || {};
    Object.keys(checks).forEach(function (k) {
      var row = checks[k] || {};
      var used = row.used || 0;
      var limit = row.limit;
      var div = el("div", "limit-row");
      div.appendChild(el("span", null, esc(k)));
      div.appendChild(el("span", null, esc(used) + " / " + esc(cap(limit))));
      lim.appendChild(div);
      if (typeof limit === "number" && limit > 0) {
        var bar = el("div", "bar");
        var span = el("span");
        span.style.width = Math.min(100, Math.round((used / limit) * 100)) + "%";
        bar.appendChild(span);
        lim.appendChild(bar);
      }
    });
    if ((d.largest_repos || []).length) {
      lim.appendChild(el("h3", null, "Largest repos"));
      (d.largest_repos || []).slice(0, 5).forEach(function (r) {
        lim.appendChild(el("div", "limit-row", esc(r.repo_name || r.repo_path) + " · " + (r.files_count || 0) + " files"));
      });
    }
    var up = document.getElementById("upgrade");
    up.innerHTML = "";
    var box = el("div", "upgrade");
    box.appendChild(el("strong", null, "Need more?"));
    box.appendChild(el("p", "muted", esc(d.upgrade_note || "Plans are in private beta — no checkout yet.")));
    var a = el("a", "btn primary");
    a.textContent = "See plans";
    a.href = "pricing.html";
    box.appendChild(a);
    up.appendChild(box);
  }

  function tbl(headers, rows) {
    var t = el("table", "admin");
    var thead = el("thead"), tr = el("tr");
    headers.forEach(function (h) { tr.appendChild(el("th", null, esc(h))); });
    thead.appendChild(tr); t.appendChild(thead);
    var tb = el("tbody");
    rows.forEach(function (r) {
      var row = el("tr");
      r.forEach(function (c) { row.appendChild(el("td", null, esc(c))); });
      tb.appendChild(row);
    });
    t.appendChild(tb); return t;
  }

  function renderAdmin(d) {
    var body = document.getElementById("adminBody");
    body.innerHTML = "";
    if (!d || !d.ok) {
      body.appendChild(el("div", "deny", "<strong>Admin only.</strong> " + esc((d && d.error) || "This dashboard requires an admin user.")));
      return;
    }
    document.getElementById("genLine").textContent = "";
    var grid = el("div", "stat-grid");
    [
      ["Mock users", d.mock_users || 1],
      ["Total scans", d.total_scans || 0],
      ["Failed scans", d.failed_scans || 0],
      ["Total exports", d.total_exports || 0],
      ["Total events", d.total_events || 0],
      ["Atlas compute units", d.token_equivalent_total || 0]
    ].forEach(function (s) {
      var c = el("div", "scard");
      c.appendChild(el("div", "num", esc(s[1])));
      c.appendChild(el("div", "lbl", esc(s[0])));
      grid.appendChild(c);
    });
    body.appendChild(grid);

    body.appendChild(el("h2", null, "Largest repositories"));
    body.appendChild(tbl(["Repository", "Files", "Modules", "Events"],
      (d.largest_repos || []).map(function (r) {
        return [r.repo_name || r.repo_path, r.files_count, r.modules_count, r.events];
      })));

    body.appendChild(el("h2", null, "Slowest scans"));
    body.appendChild(tbl(["Repository", "Seconds", "Files", "OK"],
      (d.slowest_scans || []).map(function (r) {
        return [r.repo_name || r.repo_path, r.duration_sec, r.files_count, r.ok];
      })));

    body.appendChild(el("h2", null, "Highest usage repos"));
    body.appendChild(tbl(["Repository", "Atlas compute units"],
      (d.highest_usage_repos || []).map(function (r) {
        return [r.repo_name || r.repo_path, r.token_equivalent];
      })));

    body.appendChild(el("h2", null, "Usage by plan"));
    body.appendChild(tbl(["Plan", "Users"], Object.keys(d.usage_by_plan || {}).map(function (k) {
      return [k, d.usage_by_plan[k]];
    })));

    body.appendChild(el("h2", null, "Event counts"));
    body.appendChild(tbl(["Event", "Count"], Object.keys(d.event_counts || {}).map(function (k) {
      return [k, d.event_counts[k]];
    })));
  }

  getJSON("/api/health").then(function (health) {
    flagNote(!!health.billing_ui_enabled, !!health.usage_enforcement_enabled);
    if (page === "pricing") getJSON("/api/pricing").then(renderPricing);
    else if (page === "usage") getJSON("/api/usage/me").then(renderUsage);
    else if (page === "admin") getJSON("/api/usage/admin").then(renderAdmin);
  });
})();
