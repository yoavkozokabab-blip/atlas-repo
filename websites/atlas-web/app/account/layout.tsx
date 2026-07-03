import { redirect } from "next/navigation";
import Link from "next/link";
import { SiteNav, SiteFooter } from "../_components/site";
import { currentUser } from "../_lib/auth";

export const dynamic = "force-dynamic";

export default async function AccountLayout({ children }: { children: React.ReactNode }) {
  const user = await currentUser();
  if (!user) redirect("/login?next=/account");
  return (
    <>
      <SiteNav />
      <main>
        <section className="page-head">
          <div className="container">
            <p className="eyebrow">Account</p>
            <h1 className="page-title">{user.name || user.email}</h1>
          </div>
        </section>
        <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
          <div className="container acct-grid">
            <nav className="acct-nav" aria-label="Account">
              <Link href="/account">Overview</Link>
              <Link href="/account/downloads">Downloads</Link>
              <Link href="/account/billing">Billing</Link>
              <Link href="/account/settings">Settings</Link>
              {user.role === "admin" ? <Link href="/admin">Admin</Link> : null}
              <Link href="/account/delete">Delete account</Link>
            </nav>
            <div>{children}</div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
