import { appendFile, mkdir } from "node:fs/promises";
import { join } from "node:path";
import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const form = await request.formData();
  const email = String(form.get("email") || "").trim().toLowerCase();
  const role = String(form.get("role") || "").trim().slice(0, 80);

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return NextResponse.json(
      { ok: false, message: "Enter a valid email address." },
      { status: 400 }
    );
  }

  const record = {
    email,
    role,
    createdAt: new Date().toISOString(),
    source: "jarvis-landing"
  };

  try {
    const directory = join(process.cwd(), ".waitlist");
    await mkdir(directory, { recursive: true });
    await appendFile(
      join(directory, "submissions.jsonl"),
      `${JSON.stringify(record)}\n`,
      "utf8"
    );
  } catch {
    return NextResponse.json(
      { ok: false, message: "Waitlist temporarily unavailable." },
      { status: 503 }
    );
  }

  return NextResponse.json({ ok: true });
}
