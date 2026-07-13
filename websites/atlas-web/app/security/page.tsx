import { PageShell } from "../_components/site";
import { SECURITY_EMAIL, supportMailto } from "../_config";

export const metadata = { title: "Security — Atlas" };

export default function SecurityPage() {
  return (
    <PageShell eyebrow="Security" title="Security at Atlas" intro="Atlas is built around local-first repository analysis and explicit user-controlled context sharing.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container prose">
          <h2>Local-first architecture</h2>
          <p>Repository indexing runs on your machine. Atlas reads the selected local
            folder, builds a dependency graph and prepares repo-aware answers without
            uploading repository contents during indexing.</p>

          <h2>What stays on-device</h2>
          <ul>
            <li>Repository files read during scanning</li>
            <li>Dependency graph and local repository map</li>
            <li>Ask Atlas, Debug, Impact and change-planning context derived from the scan</li>
            <li>Context packets until you choose to copy or paste them into another tool</li>
          </ul>

          <h2>Authentication</h2>
          <p>Atlas account sessions use signed, httpOnly cookies. Passwords are stored
            as salted hashes, never plaintext. Admin access is role-based and separated
            from normal user account flows.</p>

          <h2>Billing</h2>
          <p>Paid subscription billing is handled by Paddle as Merchant of Record. Atlas
            never stores your payment details.</p>

          <h2 id="data-flow">Data flow, stage by stage</h2>
          <div className="flow" aria-label="Atlas data flow" style={{ margin: "14px 0 18px" }}>
            <div className="row"><span className="tag local">Local</span> 1. Indexing — Atlas reads the selected folder on your machine. Nothing is transmitted.</div>
            <div className="row"><span className="tag local">Local</span> 2. Storage — scans, graphs, and repository memory live in <code>~/.atlas_desktop</code> on your disk.</div>
            <div className="row"><span className="tag local">Local</span> 3. MCP retrieval — your agent queries Atlas over local stdio. Nothing is transmitted off-machine.</div>
            <div className="row"><span className="tag net">Agent&apos;s path</span> 4. Agent → model provider — the agent you connected (Claude, Cursor, Codex) may send retrieved context to its own model provider under that provider&apos;s terms. This is your agent&apos;s existing data path, not a new Atlas connection.</div>
            <div className="row"><span className="tag net">Aggregate</span> 5. Analytics — event names and basic metadata only. Never repository contents, prompts, secrets, or raw file paths.</div>
            <div className="row"><span className="tag net">Paddle</span> 6. Billing — payment details are handled by Paddle as Merchant of Record. Atlas never stores card data.</div>
          </div>
          <p>Atlas does not upload repository contents to Atlas servers during indexing, and Atlas
            never trains AI models on customer repositories.</p>

          <h2>Deleting local Atlas data</h2>
          <p>Everything Atlas knows about your repositories lives in one folder. To delete it
            without uninstalling: close Atlas, then delete <code>%USERPROFILE%\.atlas_desktop</code>{" "}
            (scans, indexes, repository memory, local analytics, and logs). Uninstalling Atlas
            removes both the application and that data directory — a full uninstall leaves no
            repository data behind. MCP config backups are stored next to each agent&apos;s config
            file as <code>*.atlas-backup-&lt;timestamp&gt;</code> and are yours to keep or delete.</p>

          <h2>Responsible disclosure</h2>
          <p>If you believe you found a security issue, email{" "}
            <a href={`mailto:${SECURITY_EMAIL}?subject=Atlas%20Security%20Disclosure`}>
              {SECURITY_EMAIL}
            </a>{" "}
            with a description, reproduction steps and any relevant impact. Please do
            not publicly disclose the issue until we have had a reasonable opportunity
            to investigate and respond.</p>
          <p>We aim to acknowledge security reports within two business days.</p>

          <h2>Security contact</h2>
          <p>For non-sensitive security questions, you can also contact us through{" "}
            <a href={supportMailto("Atlas Security")}>support</a>.</p>
          <p className="note">Last updated: 2026-07-09.</p>
        </div>
      </section>
    </PageShell>
  );
}
