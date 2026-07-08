/** One-click MCP setup for Cursor, Claude Desktop, and Codex (local only). */
const atlasMcpSetup = (() => {
  let cachedStatus = null;
  let cachedJson = "";

  function outputEl() {
    return document.getElementById("mcpSetupOutput");
  }

  function statusEl() {
    return document.getElementById("mcpAgentStatus");
  }

  function showOutput(text) {
    const el = outputEl();
    if (!el) return;
    el.style.display = "block";
    el.textContent = text;
  }

  function availabilityLabel(value) {
    const key = String(value || "available").toLowerCase();
    if (key === "experimental") return "Experimental";
    if (key === "coming_soon") return "Coming soon";
    return "Available";
  }

  function renderAgentCards(status) {
    const el = statusEl();
    if (!el) return;
    const agents = status?.agents || [];
    if (!agents.length) {
      el.innerHTML = "";
      return;
    }
    el.innerHTML = agents
      .map((agent) => {
        const connected = agent.connected ? "Connected" : availabilityLabel(agent.availability);
        const badgeClass = agent.connected
          ? "connected"
          : String(agent.availability || "available").toLowerCase();
        const path = agent.config_path ? `<div class="mcp-agent-path">${agent.config_path}</div>` : "";
        return `<article class="mcp-agent-card">
          <div class="mcp-agent-card-head">
            <div class="mcp-agent-card-title">${agent.label || agent.id}</div>
            <span class="mcp-agent-badge ${badgeClass}">${connected}</span>
          </div>
          <p class="mcp-agent-desc">${agent.description || ""}</p>
          ${path}
        </article>`;
      })
      .join("");
  }

  async function loadStatus(force) {
    if (cachedStatus && !force) return cachedStatus;
    cachedStatus = await api("/api/integrations/mcp/status");
    cachedJson =
      cachedStatus.copyable_json ||
      JSON.stringify(cachedStatus.snippet || {}, null, 2);
    renderAgentCards(cachedStatus);
    return cachedStatus;
  }

  function formatFailure(res, fallbackText) {
    const lines = [
      `Config path: ${res.config_path || "(unknown)"}`,
      `Error: ${res.error || res.code || "Write failed"}`,
      "",
      fallbackText || "Copy this config manually:",
      res.fallback_json || res.fallback_toml || cachedJson,
    ];
    return lines.join("\n");
  }

  async function connectAgent(endpoint, successFallback, errorFallback) {
    const res = await api(endpoint, "POST", { confirm: true });
    if (res.ok) {
      toast(res.message || successFallback, "success");
      showOutput(
        `${res.message || successFallback}\n\nPath: ${res.config_path}\nExecutable: ${res.executable_path || ""}`
      );
      await loadStatus(true);
      return;
    }
    showOutput(formatFailure(res));
    toast(res.error || errorFallback, "error");
  }

  async function connectCursor() {
    return connectAgent(
      "/api/integrations/cursor/write-config",
      "Atlas was added to Cursor. Restart Cursor, then open Settings → MCP and confirm Atlas is connected.",
      "Could not write Cursor MCP config"
    );
  }

  async function connectClaude() {
    return connectAgent(
      "/api/integrations/claude/write-config",
      "Atlas was added to Claude Desktop. Restart Claude Desktop to load Atlas.",
      "Could not write Claude Desktop MCP config"
    );
  }

  async function connectCodex() {
    return connectAgent(
      "/api/integrations/codex/write-config",
      "Atlas was added to Codex. Restart the Codex app or IDE extension.",
      "Could not write Codex MCP config"
    );
  }

  async function copyConfig() {
    await loadStatus(false);
    if (cachedJson) copyText(cachedJson, "MCP config copied");
  }

  async function testMcp() {
    const res = await api("/api/integrations/mcp/test", "POST", {});
    if (!res.ok) {
      showOutput(`FAIL — MCP runtime test\n${res.error || "Unknown error"}`);
      toast(res.error || "MCP test failed", "error");
      return;
    }
    showOutput(
      `PASS — MCP runtime test\nTools: ${res.tool_count}\n${(res.tools || []).join(", ")}`
    );
    toast(`MCP test passed (${res.tool_count} tools)`, "success");
  }

  async function showDiagnostics() {
    const res = await api("/api/integrations/mcp/diagnostics", "POST", {});
    const lines = (res.checks || []).map((item) => {
      const mark = item.ok ? "PASS" : "FAIL";
      const detail = item.detail ? ` — ${item.detail}` : "";
      return `${mark}: ${item.name}${detail}`;
    });
    lines.unshift(`Atlas executable: ${res.executable_path || "(unknown)"}`);
    if (res.codex_config_path) {
      lines.push(`Codex config: ${res.codex_config_path}`);
    }
    lines.push("");
    lines.push(res.passed ? "Overall: PASS" : "Overall: FAIL");
    showOutput(lines.join("\n"));
    const adv = document.getElementById("mcpAdvanced");
    if (adv) adv.style.display = "flex";
    toast(
      res.passed ? "MCP diagnostics passed" : "MCP diagnostics found issues",
      res.passed ? "success" : "error"
    );
  }

  return {
    connectCursor,
    connectClaude,
    connectCodex,
    copyConfig,
    testMcp,
    showDiagnostics,
    loadStatus,
  };
})();

document.addEventListener("DOMContentLoaded", () => {
  atlasMcpSetup.loadStatus().catch(() => {});
});
