"use strict";
/* Atlas marketing layer — updates, counts, reveals, mock screenshots, analytics.
   Stores locally (localStorage) with a backend-ready interface. No external calls. */

const SIGNUP_BASE = 127;
const SIGNUP_KEY = "atlas_updates";
const EV_KEY = "atlas_events";
const ATLAS_LINKS = Object.freeze({
  github: "",
  x: "",
  discord: "",
});
const ATLAS_LINK_UNAVAILABLE = "Coming soon — official Atlas link not configured yet.";

/* ---------- storage (swap these two for a real API later) ---------- */
function getSignups() { try { return JSON.parse(localStorage.getItem(SIGNUP_KEY) || "[]"); } catch (e) { return []; } }
async function persistSignup(entry) {
  // FUTURE BACKEND: replace with an email signup endpoint.
  const list = getSignups(); list.push(entry); localStorage.setItem(SIGNUP_KEY, JSON.stringify(list)); return entry;
}
function signupCount() { return SIGNUP_BASE + getSignups().length; }

/* ---------- analytics (local, best-effort server mirror) ---------- */
function track(event, props) {
  const e = { event, props: props || {}, ts: Date.now() };
  try { const l = JSON.parse(localStorage.getItem(EV_KEY) || "[]"); l.push(e); localStorage.setItem(EV_KEY, JSON.stringify(l.slice(-500))); } catch (x) {}
  try { fetch("/api/analytics/event", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ event, ...props }) }).catch(() => {}); } catch (x) {}
}
function getEvents() { try { return JSON.parse(localStorage.getItem(EV_KEY) || "[]"); } catch (e) { return []; } }

/* ---------- counts ---------- */
function updateCounts() {
  const c = signupCount();
  ["heroCount", "proofCount", "modalCount"].forEach(id => { const el = document.getElementById(id); if (el) el.textContent = c; });
}

/* ---------- updates modal ---------- */
function openUpdates() { const m = document.getElementById("updatesModal"); if (!m) return; updateCounts(); m.classList.add("show"); track("updates_open"); }
function closeUpdates() { const m = document.getElementById("updatesModal"); if (m) m.classList.remove("show"); }
function _err(id, on) { const el = document.getElementById(id); if (el) el.style.display = on ? "block" : "none"; }
async function submitUpdates() {
  const name = (document.getElementById("wlName").value || "").trim();
  const email = (document.getElementById("wlEmail").value || "").trim();
  const valid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email);
  _err("errName", !name); _err("errEmail", !valid);
  if (!name || !valid) return;
  const entry = {
    name, email,
    company: (document.getElementById("wlCompany").value || "").trim(),
    repo_size: document.getElementById("wlSize").value || "",
    ai_tool: document.getElementById("wlTool").value || "",
    ts: new Date().toISOString(),
  };
  await persistSignup(entry);
  track("updates_join", { repo_size: entry.repo_size, ai_tool: entry.ai_tool });
  const pos = document.getElementById("yourPos"); if (pos) pos.textContent = "#" + signupCount();
  document.getElementById("updatesForm").style.display = "none";
  document.getElementById("updatesDone").style.display = "block";
  updateCounts();
}
function mtoast(msg) { const t = document.getElementById("mtoast"); if (!t) return; t.textContent = msg; t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 2200); }
function openAtlasSocial(name) {
  const url = ATLAS_LINKS[name] || "";
  if (!url) { mtoast(ATLAS_LINK_UNAVAILABLE); track("social_link_unavailable", { name }); return; }
  window.open(url, "_blank", "noopener,noreferrer");
}

/* ---------- same-page hash navigation ---------- */
function initHashNavigation() {
  document.addEventListener("click", event => {
    const link = event.target.closest("a[href^='#']");
    if (!link) return;
    const hash = link.getAttribute("href");
    if (!hash || hash === "#") return;
    const target = document.querySelector(hash);
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    history.replaceState(null, "", hash);
  });
}

/* ---------- reveal on scroll ---------- */
function initReveals() {
  const els = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window)) { els.forEach(e => e.classList.add("in")); return; }
  const io = new IntersectionObserver((entries) => entries.forEach(en => { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } }), { threshold: 0.12 });
  els.forEach(e => io.observe(e));
}

/* ---------- CSS mock screenshots (until real PNGs are dropped in) ---------- */
const COLORS = ["#9a8bff", "#6bd5ff", "#ff6bd0", "#4be0a8", "#ffbe5c"];
function mockGraph(host, n = 26) {
  host.innerHTML = "";
  const W = host.clientWidth || 600, H = host.clientHeight || 340, pts = [];
  for (let i = 0; i < n; i++) { pts.push({ x: 40 + Math.random() * (W - 80), y: 40 + Math.random() * (H - 80), s: 4 + Math.random() * 12, c: COLORS[i % COLORS.length] }); }
  // links
  for (let i = 0; i < n; i++) { const a = pts[i], b = pts[(i * 7 + 3) % n]; const dx = b.x - a.x, dy = b.y - a.y; const len = Math.hypot(dx, dy); const ln = document.createElement("div"); ln.className = "ln"; ln.style.left = a.x + "px"; ln.style.top = a.y + "px"; ln.style.width = len + "px"; ln.style.transform = `rotate(${Math.atan2(dy, dx)}rad)`; host.appendChild(ln); }
  pts.forEach(p => { const d = document.createElement("div"); d.className = "node"; d.style.cssText = `left:${p.x}px;top:${p.y}px;width:${p.s}px;height:${p.s}px;background:${p.c};color:${p.c}`; host.appendChild(d); });
}
function panel(host, x, y, w, h) { const p = document.createElement("div"); p.className = "panel"; p.style.cssText = `left:${x}%;top:${y}%;width:${w}%;height:${h}%`; host.appendChild(p); return p; }
function bar(host, x, y, w, c) { const b = document.createElement("div"); b.className = "bar3"; b.style.cssText = `left:${x}%;top:${y}%;width:${w}%;background:${c || "var(--grad)"}`; host.appendChild(b); }
function label(host, x, y, t) { const l = document.createElement("div"); l.className = "lbl"; l.style.cssText = `left:${x}%;top:${y}%`; l.textContent = t; host.appendChild(l); }

function renderMocks() {
  document.querySelectorAll(".mock").forEach(host => {
    const kind = host.dataset.mock || host.id;
    host.innerHTML = "";
    if (kind === "heroMock" || kind === "graph") {
      mockGraph(host, kind === "heroMock" ? 34 : 22);
      if (kind === "heroMock") { const lp = panel(host, 3, 8, 20, 84); label(host, 5, 12, "Overview"); bar(lp, 0, 0, 0); for (let i = 0; i < 5; i++) bar(host, 5, 24 + i * 9, 13 - i, "rgba(154,139,255,.5)"); const rp = panel(host, 77, 8, 20, 84); label(host, 79, 12, "AI Copilot"); for (let i = 0; i < 4; i++) bar(host, 79, 26 + i * 11, 16, "rgba(107,213,255,.4)"); }
    } else if (kind === "copilot") {
      panel(host, 6, 8, 88, 84); label(host, 10, 13, "AI Copilot — suggested questions");
      for (let i = 0; i < 4; i++) bar(host, 10, 26 + i * 12, 60 + i * 5, "rgba(154,139,255,.45)");
      label(host, 10, 76, "Copy for Claude   ·   Codex   ·   Cursor");
      bar(host, 10, 84, 22, "var(--grad)"); bar(host, 35, 84, 18, "rgba(107,213,255,.4)"); bar(host, 56, 84, 20, "rgba(255,107,208,.4)");
    } else if (kind === "impact") {
      panel(host, 6, 10, 88, 80); label(host, 10, 16, "Impact of changing config.py   ·   HIGH RISK");
      for (let i = 0; i < 6; i++) bar(host, 10 + (i % 3) * 28, 32 + Math.floor(i / 3) * 14, 24, "rgba(255,190,92,.4)");
      label(host, 10, 70, "Affected subsystems · recommended tests");
      bar(host, 10, 80, 30, "rgba(255,107,208,.35)");
    } else if (kind === "risk") {
      panel(host, 6, 10, 88, 80); label(host, 10, 16, "Architectural risk ranking");
      const names = ["config", "core.types", "actions.registry", "brain.router", "core.results"];
      names.forEach((nm, i) => { label(host, 10, 30 + i * 11, nm); bar(host, 32, 30 + i * 11, 50 - i * 8, i < 2 ? "linear-gradient(90deg,#ff6b8a,#ff6bd0)" : "rgba(154,139,255,.5)"); });
    }
  });
}
window.addEventListener("resize", () => { clearTimeout(window._mr); window._mr = setTimeout(renderMocks, 200); });

/* ---------- boot ---------- */
document.addEventListener("DOMContentLoaded", () => {
  updateCounts(); initReveals(); initHashNavigation();
  const m = document.getElementById("updatesModal");
  if (m) m.addEventListener("click", e => { if (e.target === m) closeUpdates(); });
  track("page_view", { page: (location.pathname.split("/").pop() || "landing") });
});
