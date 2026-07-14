import Link from "next/link";
import InstallerWaitState from "../InstallerWaitState";
import { facts } from "../../lib/content/facts";
import { GITHUB_URL } from "../../_config";

/**
 * The scroll narrative. A tall section whose sticky viewport holds four act
 * panels; ScrollController drives scene progress + panel opacity as you scroll.
 * Content stays honest — every number comes from facts.ts.
 */
export default function Narrative() {
  return (
    <section className="narrative" aria-label="How Atlas turns a repository into memory">
      <div className="narrative-vp">
        {/* 01 — Scan */}
        <div className="nact nact-left" data-act="scan">
          <div className="nact-inner">
            <p className="nact-eyebrow">01 · Scan</p>
            <h2>Atlas maps your repository.</h2>
            <p className="nact-body">
              Files, symbols, imports and callers — resolved into a dependency
              graph and an evidence store. Entirely on your machine.
            </p>
            <ul className="nact-stream mono">
              <li>resolving files</li>
              <li>resolving symbols</li>
              <li>resolving imports</li>
              <li>building relationships</li>
            </ul>
          </div>
        </div>

        {/* 02 — Memory */}
        <div className="nact nact-right" data-act="memory">
          <div className="nact-inner">
            <p className="nact-eyebrow">02 · Memory</p>
            <h2>Memory that survives across sessions.</h2>
            <p className="nact-body">
              The map is written to disk and validated against the live repo
              before reuse. A fresh agent session restores it in milliseconds —
              no re-exploration.
            </p>
            <div className="nact-chips mono">
              <span>restore {facts.restoreMsLabel}</span>
              <span>dependency graph + evidence store</span>
              <span>validated vs live repo</span>
            </div>
          </div>
        </div>

        {/* 03 — Retrieval */}
        <div className="nact nact-left" data-act="retrieval">
          <div className="nact-inner">
            <p className="nact-eyebrow">03 · Retrieval</p>
            <h2>Your agent asks; Atlas answers with citations.</h2>
            <p className="nact-body">
              Claude Code, Cursor and Codex request context over MCP. Atlas
              returns the exact files — cited, ranked, with the reason each was
              selected. No model in the loop; deterministic lookups.
            </p>
            <div className="evidence" role="group" aria-label="Example cited context">
              <div className="evidence-q mono">where is login state handled?</div>
              <div className="evidence-row">
                <span className="mono path">app/_lib/auth.ts</span>
                <span className="mono rel">0.96</span>
                <span className="reason">session read + cookie sign</span>
              </div>
              <div className="evidence-row">
                <span className="mono path">app/api/auth/session/route.ts</span>
                <span className="mono rel">0.91</span>
                <span className="reason">reads the signed cookie</span>
              </div>
              <div className="evidence-row">
                <span className="mono path">atlas_desktop/static/atlas_accounts.js</span>
                <span className="mono rel">0.78</span>
                <span className="reason">same account state</span>
              </div>
            </div>
          </div>
        </div>

        {/* 04 — Converge */}
        <div className="nact nact-center" data-act="converge">
          <div className="nact-inner nact-inner-center">
            <p className="nact-eyebrow">04 · Persistent memory</p>
            <h2>Give your coding agent a persistent<br />understanding of your project.</h2>
            <div className="nact-cta">
              <InstallerWaitState />
              <a className="btn-line" href={GITHUB_URL} target="_blank" rel="noreferrer">
                View on GitHub
              </a>
            </div>
            <p className="nact-note mono">
              {facts.platform} · MCP · {facts.mcpTools} tools · no signup
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
