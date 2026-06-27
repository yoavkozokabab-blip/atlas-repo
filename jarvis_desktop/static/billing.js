/* billing / usage dashboards (local data, no payments). */
(function () {
  "use strict";

  var page = document.body.getAttribute("data-billing-page");
  var ENDPOINTS = {
    health: ["/api/health"],
    usageMe: ["/api/usage/me", "/api/billing/usage"],
    usageAdmin: ["/api/usage/admin", "/api/usage/admin_summary", "/api/billing/admin"],
    plans: ["/api/plans", "/api/billing/plans"],
    pricing: ["/api/pricing"]
  };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = String(text);
    return e;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c];
    });
  }

  function cap(v) {
    if (v === "unlimited" || v === -1 || v === "-1") return "Unlimited";
    if (v === true) return "Yes";
    if (v === false) return "No";
    return v;
  }

  function fmtNum(n) {
    var x = Number(n);
    if (!isFinite(x)) return "0";
    if (x >= 1000000) return (x / 1000000).toFixed(1).replace(/\.0$/, "") + "M";
    if (x >= 1000) return (x / 1000).toFixed(1).replace(/\.0$/, "") + "K";
    if (Math.abs(x - Math.round(x)) < 0.05) return String(Math.round(x));
    return x.toFixed(1);
  }

  function fmtDuration(sec) {
    var s = Number(sec);
    if (!isFinite(s) || s <= 0) return "—";
    if (s < 60) return s.toFixed(1) + "s";
    var m = Math.floor(s / 60);
    var r = Math.round(s % 60);
    return m + "m " + r + "s";
  }

  function fmtFiles(n) {
    return fmtNum(n) + " files";
  }

  function labelMetric(key) {
    var map = {
      scans: "Scans this month",
      exports: "Exports this month",
      repositories: "Repositories",
      max_scans_per_month: "Scans / month",
      max_exports_per_month: "Exports / month",
      max_repositories: "Repositories",
      max_repo_files: "Max repo files",
      max_team_members: "Team members",
      large_repo_allowed: "Large repos",
      admin_dashboard_allowed: "Admin dashboard"
    };
    return map[key] || key.replace(/_/g, " ");
  }

  function labelEvent(t) {
    return String(t || "").replace(/_/g, " ");
  }

  function getJSON(urls) {
    var list = Array.isArray(urls) ? urls : [urls];
    function tryNext(i) {
      if (i >= list.length) return Promise.resolve({ ok: false, _fetch_failed: true });
      return fetch(list[i])
        .then(function (r) {
          return r.json().then(function (data) {
            if (!r.ok && data && data.error && String(data.error).indexOf("Unknown endpoint") >= 0) {
              return tryNext(i + 1);
            }
            if (!r.ok && (!data || data.ok !== true)) {
              if (i + 1 < list.length) return tryNext(i + 1);
            }
            return data || { ok: false };
          });
        })
        .catch(function () { return tryNext(i + 1); });
    }
    return tryNext(0);
  }

  function flagNote(enabled, enforcement) {
    var n = document.getElementById("flagNote");
    if (!n) return;
    n.textContent = "Billing is not enabled in this beta build. Plans and usage are preview-only — no checkout, no payment collection.";
    if (enabled) {
      n.textContent += " (Billing UI visible via ATLAS_BILLING_UI_ENABLED; enforcement: "
        + (enforcement ? "on" : "off") + ".)";
    }
  }

  function planCtaHref(planId) {
    if (planId === "FREE") return "index.html";
    if (planId === "PRO") return "pricing.html";
    return "contact.html";
  }

  function renderPricing(data) {
    var grid = document.getElementById("planGrid");
    if (!grid) return;
    grid.innerHTML = "";
    var plans = (data && data.plans) || [];
    if (!plans.length) {
      grid.appendChild(el("div", "empty-state", "Plan catalogue is loading from your local Atlas instance. Restart the desktop server if this persists."));
      return;
    }
    var note = document.getElementById("pricingNote");
    if (note && data && data.note) note.textContent = data.note;

    plans.forEach(function (p) {
      var lim = p.limits || {};
      var card = el("div", "plan-card" + (p.id === "PRO" ? " featured" : ""));
      card.appendChild(el("h3", null, p.name || p.id));
      card.appendChild(el("div", "plan-price", p.price_display || "Private beta"));
      card.appendChild(el("div", "plan-tag", p.tagline || ""));
      card.appendChild(el("div", "plan-avail", p.availability || "Private beta preview"));
      var limits = el("ul", "plan-limits");
      [
        ["Repositories", cap(lim.max_repositories)],
        ["Scans / month", cap(lim.max_scans_per_month)],
        ["Exports / month", cap(lim.max_exports_per_month)],
        ["Max repo size", cap(lim.max_repo_files) + (lim.max_repo_files > 0 ? " files" : "")],
        ["Team members", cap(lim.max_team_members)],
        ["Large repos", cap(lim.large_repo_allowed)]
      ].forEach(function (row) {
        limits.appendChild(el("li", null, row[0] + ": " + row[1]));
      });
      card.appendChild(limits);
      var ul = el("ul", "plan-feat");
      (p.features || []).forEach(function (f) { ul.appendChild(el("li", null, f)); });
      card.appendChild(ul);
      var isFree = p.id === "FREE";
      var btn = el("a", isFree ? "btn primary" : "btn ghost", isFree ? (p.cta || "Open Atlas") : "Join waitlist");
      btn.href = planCtaHref(p.id);
      if (!isFree) btn.setAttribute("aria-disabled", "true");
      card.appendChild(btn);
      grid.appendChild(card);
    });
  }

  function metricCard(label, value) {
    var c = el("div", "ucard");
    c.appendChild(el("div", "num", fmtNum(value)));
    c.appendChild(el("div", "lbl", label));
    return c;
  }

  function renderUsage(d) {
    var cards = document.getElementById("usageCards");
    var empty = document.getElementById("emptyState");
    var planCard = document.getElementById("planCard");
    var status = document.getElementById("billingStatus");
    if (!cards) return;

    if (!d || d.ok !== true) {
      if (planCard) planCard.innerHTML = "";
      if (status) status.textContent = "Local preview · no payments active";
      cards.innerHTML = "";
      if (empty) {
        empty.style.display = "block";
        empty.textContent = "Usage dashboard will appear after Atlas records local activity. Run a scan or create a Change Plan to populate metrics.";
      }
      return;
    }

    var plan = d.plan || {};
    var usage = d.usage || {};
    var hasData = d.has_usage_data !== false && (
      d.has_usage_data === true ||
      (usage.scans_used || usage.repositories_used || usage.build_plans || usage.investigations || usage.impacts || usage.exports_used)
    );

    if (planCard) {
      planCard.innerHTML = "";
      var hero = el("div", "dash-card plan-hero");
      var main = el("div", "plan-hero-main");
      main.appendChild(el("span", "plan-badge", plan.name || "Free"));
      main.appendChild(el("h2", null, (plan.name || "Free") + " plan"));
      main.appendChild(el("p", null, plan.tagline || d.upgrade_note || ""));
      hero.appendChild(main);
      var side = el("div", null);
      side.appendChild(el("div", "muted", "Billing status"));
      side.appendChild(el("div", null, d.billing_message || "Billing is not enabled in this beta build."));
      hero.appendChild(side);
      planCard.appendChild(hero);
    }

    if (status) {
      status.className = "status-banner";
      status.textContent = d.billing_message || "Billing is not enabled in beta. Usage metrics are stored locally on this machine.";
    }

    cards.innerHTML = "";
    [
      ["Scans this month", usage.scans_used],
      ["Repositories scanned", usage.repositories_used],
      ["Change Plans", usage.build_plans],
      ["Debug", usage.investigations],
      ["What Breaks", usage.impacts],
      ["Exports", usage.exports_used],
      ["Atlas compute units", usage.atlas_compute_units || usage.token_equivalent_total],
      ["Token-equivalent est.", usage.token_equivalent_total]
    ].forEach(function (s) { cards.appendChild(metricCard(s[0], s[1])); });

    if (empty) {
      empty.style.display = hasData ? "none" : "block";
      empty.textContent = d.empty_state_message || "No usage recorded yet. Run a scan or create a Change Plan to populate this dashboard.";
    }

    var lim = document.getElementById("limits");
    if (lim) {
      lim.innerHTML = "";
      var checks = d.limit_checks || {};
      Object.keys(checks).forEach(function (k) {
        var row = checks[k] || {};
        var used = row.used || 0;
        var limit = row.limit;
        lim.appendChild(el("div", "limit-row", labelMetric(k) + " · " + fmtNum(used) + " / " + cap(limit)));
        if (typeof limit === "number" && limit > 0) {
          var bar = el("div", "bar");
          var span = el("span");
          span.style.width = Math.min(100, Math.round((used / limit) * 100)) + "%";
          bar.appendChild(span);
          lim.appendChild(bar);
        }
      });
      var hardLimits = d.limits || {};
      lim.appendChild(el("div", "section-title", "Plan limits"));
      Object.keys(hardLimits).forEach(function (k) {
        lim.appendChild(el("div", "limit-row", labelMetric(k) + " · " + cap(hardLimits[k])));
      });
    }

    var largest = document.getElementById("largestRepos");
    if (largest) {
      largest.innerHTML = "";
      var repos = d.largest_repos || [];
      if (!repos.length) {
        largest.appendChild(el("p", "muted", "No repositories tracked yet."));
      } else {
        repos.slice(0, 8).forEach(function (r) {
          largest.appendChild(el("div", "limit-row", (r.repo_name || r.repo_path || "Repo") + " · " + fmtFiles(r.files_count || 0) + " · " + fmtNum(r.modules_count || 0) + " modules"));
        });
      }
    }

    var recent = document.getElementById("recentEvents");
    if (recent) {
      recent.innerHTML = "";
      var events = d.recent_events || [];
      if (!events.length) {
        recent.appendChild(el("p", "muted", "No recent events."));
      } else {
        events.slice(0, 10).forEach(function (ev) {
          recent.appendChild(el("div", "limit-row", labelEvent(ev.event_type) + " · " + (ev.repo_name || "local") + " · " + (ev.created_at || "")));
        });
      }
    }

    var up = document.getElementById("upgrade");
    if (up) {
      up.innerHTML = "";
      var box = el("div", "upgrade-box");
      box.appendChild(el("strong", null, "Need more capacity?"));
      box.appendChild(el("p", "muted", d.upgrade_note || "Billing is not enabled in beta — join the waitlist for paid plans."));
      var a = el("a", "btn ghost", "Join waitlist");
      a.href = "landing.html#waitlist";
      box.appendChild(a);
      var plans = el("a", "btn ghost", "See plan preview");
      plans.href = "pricing.html";
      box.appendChild(plans);
      up.appendChild(box);
    }
  }

  function tbl(headers, rows) {
    var t = el("table", "admin");
    var thead = el("thead");
    var tr = el("tr");
    headers.forEach(function (h) { tr.appendChild(el("th", null, h)); });
    thead.appendChild(tr);
    t.appendChild(thead);
    var tb = el("tbody");
    (rows || []).forEach(function (r) {
      var row = el("tr");
      r.forEach(function (c) { row.appendChild(el("td", null, c == null ? "—" : c)); });
      tb.appendChild(row);
    });
    if (!rows || !rows.length) {
      var emptyRow = el("tr");
      var td = el("td", "muted", "No data yet");
      td.colSpan = headers.length;
      emptyRow.appendChild(td);
      tb.appendChild(emptyRow);
    }
    t.appendChild(tb);
    return t;
  }

  function renderAdmin(d) {
    var body = document.getElementById("adminBody");
    if (!body) return;
    body.innerHTML = "";

    if (!d || d.ok !== true) {
      var msg = (d && d.code === "admin_disabled")
        ? "Admin dashboard is disabled. Start Atlas with ATLAS_ADMIN=1 to view local usage analytics."
        : "Admin dashboard requires local admin access. Start Atlas with ATLAS_ADMIN=1.";
      body.appendChild(el("div", "deny", msg));
      return;
    }

    var gen = document.getElementById("genLine");
    if (gen) gen.textContent = "Showing " + fmtNum(d.total_events || 0) + " events this month.";

    var grid = el("div", "dash-grid");
    [
      ["Total events", d.total_events],
      ["Total scans", d.total_scans],
      ["Repositories", d.total_repositories],
      ["Change Plans", d.total_build_plans],
      ["Debug", d.total_investigations],
      ["What Breaks", d.total_impacts],
      ["Exports", d.total_exports],
      ["Failed scans", d.failed_scans],
      ["Atlas compute units", d.estimated_atlas_compute_units || d.token_equivalent_total],
      ["Token-equivalent est.", d.estimated_token_equivalent || d.token_equivalent_total],
      ["Mock users", d.mock_users || 1]
    ].forEach(function (s) {
      var c = el("div", "scard");
      c.appendChild(el("div", "num", fmtNum(s[1])));
      c.appendChild(el("div", "lbl", s[0]));
      grid.appendChild(c);
    });
    body.appendChild(grid);

    body.appendChild(el("h2", "section-title", "Largest repositories"));
    var largest = d.largest_repositories || d.largest_repos || [];
    body.appendChild(tbl(["Repository", "Files", "Modules", "Events"],
      largest.map(function (r) {
        return [r.repo_name || r.repo_path, fmtNum(r.files_count), fmtNum(r.modules_count), fmtNum(r.events)];
      })));

    body.appendChild(el("h2", "section-title", "Slowest scans"));
    body.appendChild(tbl(["Repository", "Duration", "Files", "OK"],
      (d.slowest_scans || []).map(function (r) {
        return [r.repo_name || r.repo_path, fmtDuration(r.duration_sec), fmtFiles(r.files_count), r.ok === false ? "Failed" : "OK"];
      })));

    body.appendChild(el("h2", "section-title", "Highest usage users / workspaces"));
    body.appendChild(tbl(["User", "Workspace", "Plan", "Events", "Atlas units"],
      (d.high_usage_users || []).map(function (r) {
        return [r.user_id, r.workspace_id, r.plan, fmtNum(r.events), fmtNum(r.token_equivalent)];
      })));

    body.appendChild(el("h2", "section-title", "Usage by plan"));
    body.appendChild(tbl(["Plan", "Users"], Object.keys(d.usage_by_plan || {}).map(function (k) {
      return [k, d.usage_by_plan[k]];
    })));

    body.appendChild(el("h2", "section-title", "Recent events"));
    body.appendChild(tbl(["Event", "Repository", "When", "Status"],
      (d.recent_events || []).map(function (ev) {
        return [labelEvent(ev.event_type), ev.repo_name || "—", ev.created_at || "—", ev.ok === false ? "Failed" : "OK"];
      })));

    body.appendChild(el("h2", "section-title", "Event counts"));
    body.appendChild(tbl(["Event", "Count"], Object.keys(d.event_counts || {}).map(function (k) {
      return [labelEvent(k), d.event_counts[k]];
    })));
  }

  getJSON(ENDPOINTS.health).then(function (health) {
    flagNote(!!(health && health.billing_ui_enabled), !!(health && health.usage_enforcement_enabled));
  });

  if (page === "pricing") {
    getJSON(ENDPOINTS.pricing.concat(ENDPOINTS.plans)).then(renderPricing);
  } else if (page === "usage") {
    getJSON(ENDPOINTS.usageMe).then(renderUsage);
  } else if (page === "admin") {
    getJSON(ENDPOINTS.usageAdmin).then(renderAdmin);
  }
})();
