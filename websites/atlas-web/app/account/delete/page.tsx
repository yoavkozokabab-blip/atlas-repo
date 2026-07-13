import { currentUser } from "../../_lib/auth";
import { DeleteAccountForm } from "../../_components/client";

export const dynamic = "force-dynamic";

export default async function DeleteAccountPage() {
  const user = await currentUser();
  if (!user) return null;
  return (
    <div style={{ maxWidth: 520 }}>
      <div className="card" style={{ borderColor: "var(--risk)" }}>
        <h3 style={{ marginBottom: 10 }}>Delete your account</h3>
        <p>This permanently deletes your Atlas account ({user.email}), license and billing
          association. This cannot be undone. Your local Atlas data on your machine is not
          affected and can be removed from the desktop app.</p>
        <div style={{ marginTop: 18 }}>
          <DeleteAccountForm />
        </div>
      </div>
    </div>
  );
}
