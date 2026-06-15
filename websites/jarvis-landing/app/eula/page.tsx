import { PageShell } from "../_components/site";

export const metadata = { title: "EULA — Atlas" };

export default function EulaPage() {
  return (
    <PageShell eyebrow="Legal" title="End-User License Agreement" intro="Draft — full EULA lands in the legal pass.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container prose">
          <p>Atlas grants you a personal, non-exclusive, non-transferable license to install and use
            the Atlas desktop application under your plan. You may not resell, redistribute or
            reverse-engineer the software, or use it to violate the law or third-party rights.</p>
          <p className="note">This is a product/legal draft and will be reviewed by a qualified
            lawyer before public launch. See also Terms, Privacy, Refund and Cancellation.</p>
        </div>
      </section>
    </PageShell>
  );
}
