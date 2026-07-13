import type { Metadata } from "next";
import Link from "next/link";
import { PageShell, InstallFlow } from "../_components/site";
import { SUPPORT_EMAIL, supportMailto } from "../_config";

export const metadata: Metadata = {
  title: "Docs — Atlas",
  description: "Atlas documentation: install, quickstart, demo mode, MCP setup for Claude, Cursor, and Codex, troubleshooting, privacy, and billing."
};

export default function DocsPage() {
  return (
    <PageShell
      eyebrow="Docs"
      title="Getting started"
      intro="Atlas runs locally and gives your AI tools real context about your codebase. Everything on this page happens on your machine."
    >
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container prose">
          <div style={{ marginBottom: 28 }}>
            <InstallFlow />
          </div>

          <h2 id="install">Install</h2>
          <p>Download <Link href="/download">Atlas for Windows</Link> and run the installer. It&apos;s
            self-contained — no Python required, no admin rights, no account. On first launch Atlas
            starts a local server and opens in your browser. Windows SmartScreen may warn on first
            run because the installer is not yet code-signed; this is expected for new software.</p>

          <h2 id="quickstart">Quickstart</h2>
          <ol className="steps">
            <li>Open Atlas and click <b>Load sample repository</b> (or scan your own project folder).</li>
            <li>Ask a repo-aware question such as <code>Where is authentication implemented?</code> — Atlas answers with cited files.</li>
            <li>Connect Claude, Cursor, or Codex from the home screen so your agent can use the same index.</li>
          </ol>

          <h2 id="demo">Demo mode</h2>
          <p>The <b>HN demo</b> in the app&apos;s navigation is a guided tour: load the bundled sample
            repository, ask a prefilled question, then step through <b>Impact</b>, <b>Debug</b>, and{" "}
            <b>Plan Change</b> on the same sample. Each step is one click and you can skip out at any
            point. Nothing in demo mode touches your own code.</p>

          <h2 id="mcp">MCP setup</h2>
          <p>Atlas ships a local MCP server (18 tools) that Claude Desktop, Cursor, and Codex can call.
            Each integration on the home screen has its own status, <b>Connect</b>, <b>Test</b>, and an{" "}
            <b>Advanced manual setup</b> fallback that shows the exact file path and snippet.</p>
          <h3 id="claude">Claude</h3>
          <p><b>Connect to Claude</b> writes the Atlas entry into{" "}
            <code>%APPDATA%\Claude\claude_desktop_config.json</code>. Restart Claude Desktop, then
            confirm Atlas appears under MCP settings. Use <b>Test</b> in Atlas to verify the server
            responds before restarting.</p>
          <h3 id="cursor">Cursor</h3>
          <p><b>Connect to Cursor</b> writes <code>~/.cursor/mcp.json</code>. Restart Cursor, then open
            Settings → MCP and confirm Atlas is listed and enabled.</p>
          <h3 id="codex">Codex</h3>
          <p><b>Connect to Codex</b> writes an <code>[mcp_servers.atlas]</code> block into{" "}
            <code>~/.codex/config.toml</code> (or <code>$CODEX_HOME/config.toml</code> when set).
            Restart Codex to load Atlas.</p>

          <h2 id="troubleshooting">Troubleshooting</h2>
          <ul>
            <li><b>Connect failed / “Manual setup required”:</b> the config file may be missing or unwritable. The manual setup modal shows the exact path and a snippet to paste yourself.</li>
            <li><b>Agent doesn&apos;t show Atlas after connecting:</b> fully restart the agent (Claude Desktop, Cursor, or Codex) — MCP configs load at startup.</li>
            <li><b>Test fails:</b> make sure Atlas is running; the MCP server is launched from the installed <code>Atlas.exe --mcp</code>.</li>
            <li><b>Answers look stale after editing files:</b> Atlas blocks stale exports by design — rescan the repository to refresh the index.</li>
            <li><b>Anything else:</b> use Support &amp; diagnostics in the app, or email{" "}
              <a href={supportMailto("Atlas Support")}>{SUPPORT_EMAIL}</a>.</li>
          </ul>

          <h2 id="privacy">Privacy &amp; local-first</h2>
          <p>Repository scanning, the index, and answers are computed on your machine. Atlas does not
            upload repository contents during indexing and never trains models on your code. The only
            code-related data that leaves your machine is the context you explicitly copy or send to an
            agent. Details: <Link href="/privacy">Privacy Policy</Link> and{" "}
            <Link href="/security">Security</Link>.</p>

          <h2 id="billing">Billing</h2>
          <p>The core local app is free and does not require an account. Pro is $19/month with a 7-day
            trial, processed by Paddle as Merchant of Record when checkout is enabled — Atlas never
            stores card details. Cancel anytime from the billing portal. See{" "}
            <Link href="/pricing">Pricing</Link> and <Link href="/refund">Refund Policy</Link>.</p>

          <h2 id="faq">FAQ</h2>
          <p>Short, honest answers to the common objections — uploads, offline use, data location,
            deletion, repo size, supported languages — live on the <Link href="/faq">FAQ page</Link>.</p>

          <p className="note" style={{ marginTop: 24 }}>
            Need help? <a href={supportMailto("Atlas Support")} style={{ color: "var(--accent)" }}>{SUPPORT_EMAIL || "contact support"}</a>
          </p>
        </div>
      </section>
    </PageShell>
  );
}
