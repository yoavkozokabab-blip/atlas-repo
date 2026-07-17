export const MAX_WAITLIST_BODY_BYTES = 8 * 1024;

export function parseWaitlistForm(form: FormData): { email: string; role: string } | null {
  const allowed = new Set(["email", "role"]);
  const keys = [...form.keys()];
  if (keys.some((key) => !allowed.has(key)) || form.getAll("email").length !== 1 || form.getAll("role").length > 1) return null;
  const email = String(form.get("email") || "").trim().toLowerCase();
  const role = String(form.get("role") || "").trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || role.length > 80) return null;
  return { email, role };
}
