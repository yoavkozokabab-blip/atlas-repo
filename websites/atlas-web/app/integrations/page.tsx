import type { Metadata } from "next";
import Link from "next/link";
import { PageShell } from "../_components/site";
import { facts } from "../lib/content/facts";

export const metadata: Metadata = {
  title: "Integrations - Atlas",
  description:
    "Atlas connects to Claude Code, Cursor and Codex over MCP. Support levels, install steps, example workflows and current limitations.",
};

const integrations = [
  {
    name: "Claude Code",
    support: "Supported",
    what: "Connect Atlas as an MCP server and ask repo-aware questions from your Claude Code workflow.",
    how: "Add the Atlas MCP server to your Claude Code config; Atlas launches in stdio mode and shares your local index.",
  },
  {
    name: "Cursor",
    support: "Supported",
    what: "Give Cursor cited local context instead of re-explaining the same files each session.",
    how: "Register the Atlas MCP server in Cursor's MCP settings; the same local index is reused.",
  },
  {
    name: "Codex",
    support: "Supported",
    what: "Use Atlas context when planning changes, debugging behavior, or mapping an unfamiliar repo.",
    how: "Point Codex's MCP configuration at the Atlas server; no repository upload is involved.",
  },
  {
    name: "MCP (any compatible client)",
    support: "Experimental",
    what: `Atlas exposes ${facts.mcpTools} MCP tools (scan, ask, impact, root-cause, health and more).`,
    how: "Any MCP-compatible client can connect over stdio. Validate against your client before relying on it.",
  },
];

export default function Integrations() {
  return (
    <PageShell
      eyebrow="Integrations"
      title="Built for the agents you already use."
      intro="Atlas serves cited repository context to coding agents over the Model Context Protocol. Support levels and limitations are stated honestly."
    >
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container">
          <div className="grid-2" style={{ alignItems: "stretch", gap: 22 }}>
            {integrations.map((it) => (
              <div className="card" key={it.name}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                  <h3 style={{ margin: 0 }}>{it.name}</h3>
                  <span className={`badge ${it.support === "Supported" ? "ok" : "warn"}`}>{it.support}</span>
                </div>
                <p style={{ marginBottom: 12 }}>{it.what}</p>
                <p className="mono muted" style={{ fontSize: "0.84rem" }}>{it.how}</p>
              </div>
            ))}
          </div>
          <p style={{ marginTop: 30 }} className="note">
            Every integration reuses the same local index — your source stays on your machine. See the{" "}
            <Link href="/docs">docs</Link> for exact configuration and the{" "}
            <Link href="/security">security page</Link> for what leaves the device.
          </p>
        </div>
      </section>
    </PageShell>
  );
}
