import crypto from "node:crypto";
import { store } from "@/app/_lib/store";
import { validEmail } from "@/app/_lib/auth";
import { rateLimit, clientIp, readJson } from "@/app/_lib/ratelimit";
import { ENV } from "@/app/_lib/config";
import { privateJson, unavailableJson } from "@/app/_lib/http";

export const runtime = "nodejs";

export async function POST(req: Request) {
  try {
    if (!(await rateLimit(`forgot:${clientIp(req)}`, 5, 900_000))) {
      return privateJson({ ok: true, resetAvailable: false });
    }
    const body = await readJson(req);
    const email = String(body.email ?? "").trim().toLowerCase();

    // There is no production email/reset-consumption flow yet. Do not create
    // reset credentials that cannot be delivered, and never log reset tokens.
    if (ENV.isProd) {
      return privateJson({
        ok: true,
        resetAvailable: false,
        message: "Password reset is temporarily unavailable. Contact support for account help.",
      });
    }

    // Always return the same generic response - never reveal whether the email exists.
    if (validEmail(email) && (await store.getByEmail(email))) {
      const token = crypto.randomBytes(24).toString("base64url");
      await store.addResetToken({ token, email, exp: Date.now() + 30 * 60_000 });
      console.warn("[atlas] local password reset stub created");
    }
    return privateJson({
      ok: true,
      resetAvailable: true,
      message: "If an account exists for that email, a local reset stub was created.",
    });
  } catch {
    return unavailableJson();
  }
}
