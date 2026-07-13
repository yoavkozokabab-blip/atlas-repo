import type { Metadata } from "next";
import Link from "next/link";
import { InstallationBlock, PageShell, PremiumSection, TechnicalDiagram } from "../_components/site";
import { facts } from "../lib/content/facts";

export const metadata: Metadata = {
  title: "How it works - Atlas",
  description:
    "The Atlas pipeline: connect a repository, scan files and symbols, build relationships, create persistent memory, connect coding agents, and retrieve cited context during work.",
};

const steps: Array<[string, string]> = [
  ["Open a local repository", "Atlas reads the selected folder on your machine. Repository contents are not uploaded during indexing."],
  ["Parse files and imports", `The built-in ${facts.sampleFiles}-file sample indexes in ${facts.sampleIndexLabel}; larger repos depend on hardware and size.`],
  ["Build graph evidence", "Modules, symbols, import paths and evidence rows become a dependency map the app can validate."],
  ["Persist memory", `Fresh sessions restore the saved scan in ${facts.restoreMsLabel} when the repository signature still matches.`],
  ["Connect agents", `Claude Code, Cursor and Codex use the same ${facts.mcpTools}-tool MCP surface.`],
  ["Return cited context", `Ask Atlas responds in ${facts.askLatencyLabel} after indexing, with cited files rather than model guesses.`],
];

export default function HowItWorks() {
  return (
    <PageShell
      eyebrow="How it works"
      title="From raw repository to persistent memory."
      intro="Atlas turns local source into a validated map that survives fresh agent sessions."
    >
      <PremiumSection>
        <TechnicalDiagram title="local pipeline" items={steps} />
      </PremiumSection>

      <PremiumSection
        eyebrow="Install path"
        title="Start with the Windows app."
        intro="The public site does not change the download architecture: the installer route and GitHub release verification remain the source of truth."
      >
        <InstallationBlock />
      </PremiumSection>

      <PremiumSection
        eyebrow="Next"
        title="Connect the agents you already use."
      >
        <div className="asym">
          <div>
            <p className="lead">
              Atlas writes local MCP config for supported agents only when you explicitly connect from the desktop app.
            </p>
            <div className="page-actions">
              <Link className="btn-mag" href="/integrations">View integrations <span className="arw" aria-hidden>→</span></Link>
              <Link className="btn-line" href="/docs#mcp">MCP docs</Link>
            </div>
          </div>
          <ol className="premium-list">
            <li><span className="num">01</span><div><h3>Claude Code</h3><p>Use Atlas as an MCP server from your Claude workflow.</p></div></li>
            <li><span className="num">02</span><div><h3>Cursor</h3><p>Reuse the same local repository index inside Cursor.</p></div></li>
            <li><span className="num">03</span><div><h3>Codex</h3><p>Give Codex cited repository context for planning and debugging.</p></div></li>
          </ol>
        </div>
      </PremiumSection>
    </PageShell>
  );
}
