/** One-click MCP setup for Cursor and Claude Desktop (local only). */
const atlasMcpSetup = (() => {
  let cachedStatus = null;
  let cachedJson = "";

  function outputEl() {
    return document.getElementById("mcpSetupOutput");
  }

  function showOutput(text) {
    const el = outputEl();
    if (!el) return;
    el.style.display = "block";
    el.textContent = text;
  }

  async function loadStatus(force) {
    if (cachedStatus && !force) return cachedStatus;
    cachedStatus = await api("/api/integrations/mcp/status");
    cachedJson =
      cachedStatus.copyable_json ||
      JSON.stringify(cachedStatus.snippet || {}, null, 2);
    return cachedStatus;
  }

  function formatFailure(res) {
    const lines = [
      `Config path: ${res.config_path || "(unknown)"}`,
      `Error: ${res.error || res.code || "Write failed"}`,
      "",
      "Copy this JSON manually:",
      res.fallback_json || cachedJson,
    ];
    return lines.join("\n");
  }

  async function connectCursor() {
    const res = await api("/api/integrations/cursor/write-config", "POST", {
      confirm: true,
    });
    if (res.ok) {
      toast(
        res.message ||
          "Atlas was added to Cursor. Restart Cursor, then open Settings → MCP and confirm Atlas is connected.",
        "success"
      );
      showOutput(
        `${res.message || "Cursor config updated."}\n\nPath: ${res.config_path}\nExecutable: ${res.executable_path || ""}`
      );
      await loadStatus(true);
      return;
    }
    showOutput(formatFailure(res));
    toast(res.error || "Could not write Cursor MCP config", "error");
  }

  async function connectClaude() {
    const res = await api("/api/integrations/claude/write-config", "POST", {
      confirm: true,
    });
    if (res.ok) {
      toast(
        res.message ||
          "Atlas was added to Claude Desktop. Restart Claude Desktop to load Atlas.",
        "success"
      );
      showOutput(
        `${res.message || "Claude config updated."}\n\nPath: ${res.config_path}\nExecutable: ${res.executable_path || ""}`
      );
      await loadStatus(true);
      return;
    }
    showOutput(formatFailure(res));
    toast(res.error || "Could not write Claude Desktop MCP config", "error");
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
    lines.push("");
    lines.push(res.passed ? "Overall: PASS" : "Overall: FAIL");
    showOutput(lines.join("\n"));
    const adv = document.getElementById("mcpAdvanced");
    if (adv) adv.style.display = "flex";  // reveal manual "Copy MCP config" once diagnostics is open
    toast(res.passed ? "MCP diagnostics passed" : "MCP diagnostics found issues", res.passed ? "success" : "error");
  }

  return {
    connectCursor,
    connectClaude,
    copyConfig,
    testMcp,
    showDiagnostics,
    loadStatus,
  };
})();

document.addEventListener("DOMContentLoaded", () => {
  atlasMcpSetup.loadStatus().catch(() => {});
});
