/** One-click MCP setup for Cursor, Claude Desktop, and Codex (local only). */
const atlasMcpSetup = (() => {
  let cachedStatus = null;
  let cachedJson = "";
  let manualSnippet = "";
  let manualTool = "";

  const CONNECT_LABELS = {
    claude: "Connect to Claude",
    cursor: "Connect to Cursor",
    codex: "Connect to Codex",
  };

  const TOOL_LABELS = {
    claude: "Claude",
    cursor: "Cursor",
    codex: "Codex",
  };

  function toolKey(tool) {
    const key = String(tool || "").toLowerCase();
    return TOOL_LABELS[key] ? key : "";
  }

  function toolId(tool) {
    const key = toolKey(tool);
    return key ? key.charAt(0).toUpperCase() + key.slice(1) : "";
  }

  function setText(id, text, state) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text;
    if (state) el.className = `mcp-tool-card-status ${state}`;
  }

  function setConnectButton(id, connected, manual, tool) {
    const btn = document.getElementById(id);
    if (!btn) return;
    const label = CONNECT_LABELS[tool] || "Connect";
    if (manual) {
      btn.textContent = label;
      btn.classList.remove("primary");
      btn.classList.add("ghost");
      return;
    }
    btn.textContent = connected ? "Review configuration" : label;
    btn.classList.toggle("primary", !connected);
    btn.classList.toggle("ghost", !!connected);
  }

  function mcpVerificationState(key, data) {
    if (!data?.atlas_configured) return "not_configured";
    if (key === "cursor" && (data.client_verified || data.mcp_handshake_ok || data.last_handshake)) return "verified";
    return "configured";
  }

  function renderHomeStatus(status) {
    if (!status) return;
    const claude = status.claude || {};
    const cursor = status.cursor || {};
    const codex = status.codex || {};
    const claudeOn = !!claude.atlas_configured;
    const cursorOn = !!cursor.atlas_configured;
    const codexOn = !!codex.atlas_configured;
    const codexManual = !codexOn && codex.can_auto_write === false;
    const claudeState = mcpVerificationState("claude", claude);
    const cursorState = mcpVerificationState("cursor", cursor);
    const codexState = mcpVerificationState("codex", codex);

    setText(
      "mcpClaudeStatus",
      claudeState === "verified" ? "Verified" : (claudeOn ? "Configured" : "Not configured"),
      claudeState === "verified" ? "verified" : (claudeOn ? "configured" : "disconnected")
    );
    setText(
      "mcpCursorStatus",
      cursorState === "verified" ? "Verified" : (cursorOn ? "Configured" : "Not configured"),
      cursorState === "verified" ? "verified" : (cursorOn ? "configured" : "disconnected")
    );
    setText(
      "mcpCodexStatus",
      codexState === "verified" ? "Verified" : (codexOn ? "Configured" : (codexManual ? "Manual setup required" : "Not configured")),
      codexState === "verified" ? "verified" : (codexOn ? "configured" : (codexManual ? "manual" : "disconnected"))
    );

    setConnectButton("mcpClaudeBtn", claudeOn, false, "claude");
    setConnectButton("mcpCursorBtn", cursorOn, false, "cursor");
    setConnectButton("mcpCodexBtn", codexOn, codexManual, "codex");
    if (typeof window.renderHomeExperience === "function") {
      window.renderHomeExperience({ mcpStatus: status });
    }
  }

  async function loadStatus(force) {
    if (cachedStatus && !force) {
      renderHomeStatus(cachedStatus);
      return cachedStatus;
    }
    cachedStatus = await api("/api/integrations/mcp/status");
    cachedJson =
      cachedStatus.copyable_json ||
      JSON.stringify(cachedStatus.snippet || {}, null, 2);
    renderHomeStatus(cachedStatus);
    return cachedStatus;
  }

  function manualSnippetFor(tool, failureRes) {
    const key = toolKey(tool);
    const agent = (cachedStatus && cachedStatus[key]) || {};
    if (key === "codex") {
      return failureRes?.fallback_toml || agent.copyable_toml || "";
    }
    return failureRes?.fallback_json || agent.copyable_json || cachedJson;
  }

  function manualPathFor(tool, failureRes) {
    const key = toolKey(tool);
    const agent = (cachedStatus && cachedStatus[key]) || {};
    if (failureRes?.config_path) return failureRes.config_path;
    if (agent.config_path) return agent.config_path;
    if (key === "codex") return "~/.codex/config.toml";
    if (key === "cursor") return "~/.cursor/mcp.json";
    return "~/AppData/Roaming/Claude/claude_desktop_config.json";
  }

  function showManualSetup(tool, failureRes) {
    const key = toolKey(tool);
    if (!key) return;
    manualTool = key;
    manualSnippet = manualSnippetFor(key, failureRes);
    const modal = document.getElementById("mcpManualModal");
    const eyebrow = document.getElementById("mcpManualEyebrow");
    const title = document.getElementById("mcpManualTitle");
    const reason = document.getElementById("mcpManualReason");
    const path = document.getElementById("mcpManualPath");
    const snippet = document.getElementById("mcpManualSnippet");
    const label = TOOL_LABELS[key];
    if (eyebrow) eyebrow.textContent = `${label} MCP`;
    if (title) {
      title.textContent =
        failureRes?.error || failureRes?.code ? "Manual setup required" : "Advanced manual setup";
    }
    if (reason) {
      reason.textContent =
        failureRes?.error ||
        failureRes?.code ||
        `Paste this ${key === "codex" ? "TOML" : "JSON"} into your ${label} config if automatic setup is unavailable.`;
    }
    if (path) path.textContent = manualPathFor(key, failureRes);
    if (snippet) snippet.textContent = manualSnippet;
    // A failure opened this modal: surface the likely cause and offer Retry.
    const failed = !!(failureRes && (failureRes.error || failureRes.code));
    const cause = document.getElementById("mcpManualCause");
    const retry = document.getElementById("mcpManualRetryBtn");
    if (cause) cause.style.display = failed ? "block" : "none";
    if (retry) {
      retry.style.display = failed ? "inline-block" : "none";
      retry.textContent = `Retry ${label} connect`;
    }
    if (modal) modal.style.display = "grid";
    if (key === "codex" && (failureRes?.error || failureRes?.code)) {
      setText("mcpCodexStatus", "Manual setup required", "manual");
      setConnectButton("mcpCodexBtn", false, true, "codex");
    }
  }

  function closeManualSetup() {
    const modal = document.getElementById("mcpManualModal");
    if (modal) modal.style.display = "none";
  }

  function copyManualConfig() {
    if (!manualSnippet) return;
    const label = TOOL_LABELS[manualTool] || "MCP";
    copyText(manualSnippet, `${label} manual config copied`);
  }

  async function connectAgent(tool, endpoint, successFallback, errorFallback) {
    const label = TOOL_LABELS[toolKey(tool)] || "Agent";
    window.atlasActivity?.add(`${label} MCP connect clicked`);
    const res = await api(endpoint, "POST", { confirm: true });
    if (res.ok) {
      closeManualSetup();
      toast(res.message || successFallback, "success");
      window.atlasActivity?.add(`${label} configured for MCP`);
      await loadStatus(true);
      return res;
    }
    showManualSetup(tool, res);
    toast(res.error || errorFallback, "error");
    window.atlasActivity?.add(`${label} MCP config write failed`);
    return res;
  }

  function retryConnect() {
    if (manualTool === "cursor") return connectCursor();
    if (manualTool === "codex") return connectCodex();
    return connectClaude();
  }

  async function connectCursor() {
    return connectAgent(
      "cursor",
      "/api/integrations/cursor/write-config",
      "Atlas was added to Cursor. Restart Cursor, then open Settings → MCP and confirm Atlas appears.",
      "Could not write Cursor MCP config"
    );
  }

  async function connectClaude() {
    return connectAgent(
      "claude",
      "/api/integrations/claude/write-config",
      "Atlas was added to Claude Desktop. Restart Claude Desktop to load Atlas.",
      "Could not write Claude Desktop MCP config"
    );
  }

  async function connectCodex() {
    window.atlasActivity?.add("Codex MCP connect clicked");
    const res = await api("/api/integrations/codex/write-config", "POST", { confirm: true });
    if (res.ok) {
      closeManualSetup();
      toast("Configured. Restart Codex to use Atlas.", "success");
      window.atlasActivity?.add("Codex MCP configured");
      await loadStatus(true);
      return res;
    }
    showManualSetup("codex", res);
    toast(res.error || "Automatic Codex connection failed — manual setup required", "error");
    window.atlasActivity?.add("Codex MCP config write failed");
    return res;
  }

  function resetToolDetails(tool) {
    const id = toolId(tool);
    const testEl = document.getElementById(`mcp${id}Test`);
    const summaryEl = document.getElementById(`mcp${id}TestSummary`);
    const detailsBtn = document.getElementById(`mcp${id}DetailsBtn`);
    const toolsList = document.getElementById(`mcp${id}ToolsList`);
    if (testEl) testEl.hidden = true;
    if (summaryEl) summaryEl.textContent = "";
    if (detailsBtn) detailsBtn.hidden = true;
    if (toolsList) {
      toolsList.textContent = "";
      toolsList.hidden = true;
    }
  }

  async function testTool(tool) {
    const key = toolKey(tool);
    if (!key) return;
    const id = toolId(key);
    const label = TOOL_LABELS[key];
    const testEl = document.getElementById(`mcp${id}Test`);
    const summaryEl = document.getElementById(`mcp${id}TestSummary`);
    const detailsBtn = document.getElementById(`mcp${id}DetailsBtn`);
    const toolsList = document.getElementById(`mcp${id}ToolsList`);
    const res = await api("/api/integrations/mcp/test", "POST", {});
    if (testEl) testEl.hidden = false;
    if (!res.ok) {
      if (summaryEl) {
        summaryEl.textContent = `FAIL — ${res.error || "Unknown error"}`;
        summaryEl.className = "mcp-tool-test-summary fail";
      }
      if (detailsBtn) detailsBtn.hidden = true;
      if (toolsList) toolsList.hidden = true;
      toast(res.error || `Test ${label} failed`, "error");
      return res;
    }
    if (summaryEl) {
      summaryEl.textContent = `PASS — ${res.tool_count} tools available`;
      summaryEl.className = "mcp-tool-test-summary pass";
    }
    if (toolsList) {
      toolsList.textContent = (res.tools || []).join("\n");
      toolsList.hidden = true;
    }
    if (detailsBtn) {
      detailsBtn.hidden = !(res.tools || []).length;
      detailsBtn.textContent = "Show details";
    }
    toast(`Test ${label} passed (${res.tool_count} tools)`, "success");
    return res;
  }

  function toggleToolDetails(tool) {
    const key = toolKey(tool);
    if (!key) return;
    const id = toolId(key);
    const list = document.getElementById(`mcp${id}ToolsList`);
    const btn = document.getElementById(`mcp${id}DetailsBtn`);
    if (!list || !btn) return;
    const show = list.hidden;
    list.hidden = !show;
    btn.textContent = show ? "Hide details" : "Show details";
  }

  return {
    connectCursor,
    connectClaude,
    connectCodex,
    retryConnect,
    testTool,
    showManualSetup,
    closeManualSetup,
    copyManualConfig,
    toggleToolDetails,
    loadStatus,
  };
})();

document.addEventListener("DOMContentLoaded", () => {
  atlasMcpSetup.loadStatus().catch(() => {});
});
