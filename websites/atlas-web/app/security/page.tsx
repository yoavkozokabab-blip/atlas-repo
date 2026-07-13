import { EvidenceBlock, PageShell, PremiumSection, TechnicalDiagram } from "../_components/site";
import { SECURITY_EMAIL, supportMailto } from "../_config";

export const metadata = { title: "Security - Atlas" };

export default function SecurityPage() {
  return (
    <PageShell eyebrow="Security" title="Security at Atlas" intro="Atlas is built around local-first repository analysis and explicit user-controlled context sharing.">
      <PremiumSection>
        <div className="grid-2">
          <TechnicalDiagram
            title="data flow"
            items={[
              ["Indexing", "Atlas reads the selected folder on your machine. Nothing is transmitted."],
              ["Storage", "Scans, graphs, and repository memory live in ~/.atlas_desktop on your disk."],
              ["MCP retrieval", "Your agent queries Atlas over local stdio. Nothing is transmitted off-machine by Atlas."],
              ["Agent path", "Your connected agent may send retrieved context to its own model provider under that provider's terms."],
              ["Analytics", "Event names and basic metadata only; never repository contents, prompts, secrets, or raw file paths."],
              ["Billing", "Payment details are handled by Paddle as Merchant of Record. Atlas never stores card data."],
            ]}
          />
          <EvidenceBlock
            question="What stays on-device?"
            rows={[
              { path: "repository files", relation: "local", reason: "read during scanning on your machine" },
              { path: "dependency graph", relation: "local", reason: "stored in the Atlas data directory" },
              { path: "context packets", relation: "user-controlled", reason: "leave only when you copy or send them" },
            ]}
          />
        </div>
      </PremiumSection>

      <PremiumSection>
        <div className="container prose" style={{ padding: 0 }}>
          <h2>Local-first architecture</h2>
          <p>Repository indexing runs on your machine. Atlas reads the selected local folder, builds a dependency graph and prepares repo-aware answers without uploading repository contents during indexing.</p>

          <h2>Authentication</h2>
          <p>Atlas account sessions use signed, httpOnly cookies. Passwords are stored as salted hashes, never plaintext. Admin access is role-based and separated from normal user account flows.</p>

          <h2>Billing</h2>
          <p>Paid subscription billing is handled by Paddle as Merchant of Record. Atlas never stores your payment details.</p>

          <h2>Deleting local Atlas data</h2>
          <p>Everything Atlas knows about your repositories lives in one folder. To delete it without uninstalling: close Atlas, then delete <code>%USERPROFILE%\.atlas_desktop</code>{" "}(scans, indexes, repository memory, local analytics, and logs). Uninstalling Atlas removes both the application and that data directory - a full uninstall leaves no repository data behind. MCP config backups are stored next to each agent&apos;s config file as <code>*.atlas-backup-&lt;timestamp&gt;</code> and are yours to keep or delete.</p>

          <h2>Responsible disclosure</h2>
          <p>If you believe you found a security issue, email{" "}
            <a href={`mailto:${SECURITY_EMAIL}?subject=Atlas%20Security%20Disclosure`}>
              {SECURITY_EMAIL}
            </a>{" "}
            with a description, reproduction steps and any relevant impact. Please do not publicly disclose the issue until we have had a reasonable opportunity to investigate and respond.</p>
          <p>We aim to acknowledge security reports within two business days.</p>

          <h2>Security contact</h2>
          <p>For non-sensitive security questions, you can also contact us through{" "}
            <a href={supportMailto("Atlas Security")}>support</a>.</p>
          <p className="note">Last updated: 2026-07-09.</p>
        </div>
      </PremiumSection>
    </PageShell>
  );
}
