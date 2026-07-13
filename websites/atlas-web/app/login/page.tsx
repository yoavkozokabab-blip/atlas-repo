import { redirect } from "next/navigation";
import { PageShell } from "../_components/site";
import { AuthForm } from "../_components/client";
import { currentUser } from "../_lib/auth";

export const dynamic = "force-dynamic";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const sp = await searchParams;
  const next = typeof sp.next === "string" && sp.next.startsWith("/") ? sp.next : "/account";
  const user = await currentUser();
  if (user) redirect(next);
  return (
    <PageShell
      eyebrow="Account"
      title="Sign in to Atlas"
      intro="Create an account or sign in to manage your plan. The Windows download also supports local guest mode."
    >
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container">
          <AuthForm next={next} />
        </div>
      </section>
    </PageShell>
  );
}
