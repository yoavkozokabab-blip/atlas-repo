import { test, expect } from "playwright/test";
import { POST } from "../app/api/feedback/route";
import { redactFeedbackText } from "../app/_lib/feedback-redaction";

/**
 * The feedback endpoint exists so a beta report actually reaches the owner.
 * It is unauthenticated by design (the desktop has no account in this build),
 * so its safety rests entirely on: rate limiting, a hard size cap, a closed
 * field allowlist, and redaction that runs again server-side regardless of
 * what the client claims to have done.
 */

function request(body: unknown, init: RequestInit = {}): Request {
  return new Request("https://atlas.test/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-forwarded-for": randomIp() },
    body: typeof body === "string" ? body : JSON.stringify(body),
    ...init,
  });
}

/** A fresh bucket per test so the shared limiter cannot cross-contaminate. */
function randomIp(): string {
  const octet = () => Math.floor(Math.random() * 254) + 1;
  return `${octet()}.${octet()}.${octet()}.${octet()}`;
}

const valid = {
  feedback_id: "abc123def456",
  category: "bug",
  message: "Impact missed a dependent module in my project.",
};

test("redaction removes local paths and credentials", () => {
  expect(redactFeedbackText(String.raw`crashed at C:\Users\alice\repo\app.py`))
    .toBe("crashed at [path-redacted]");
  expect(redactFeedbackText("/home/bob/work/secret.py failed")).toBe("[path-redacted] failed");
  expect(redactFeedbackText("token: ghp_ABCDEFghijklmnopqrstuvwxyz1234"))
    .toContain("[credential-redacted]");
  expect(redactFeedbackText("Authorization: Bearer abcdef0123456789"))
    .toContain("[credential-redacted]");
  expect(redactFeedbackText("api_key=SUPERSECRETVALUE")).toBe("[credential-redacted]");
  expect(redactFeedbackText("sb_secret_livekey123")).toContain("[credential-redacted]");
});

test("redaction leaves ordinary prose intact", () => {
  const prose = "Impact said 8 files but I expected 9. The graph view was helpful.";
  expect(redactFeedbackText(prose)).toBe(prose);
});

test("a valid report is accepted", async () => {
  const res = await POST(request(valid));
  expect([201, 200, 503]).toContain(res.status);
  const body = await res.json();
  // 503 only when no store is reachable in this environment; never a false ok.
  if (res.status === 503) expect(body.ok).toBe(false);
  else expect(body.ok).toBe(true);
});

test("an empty message is rejected", async () => {
  const res = await POST(request({ ...valid, message: "   " }));
  expect(res.status).toBe(400);
  expect((await res.json()).error).toBe("empty_message");
});

test("a missing or malformed feedback id is rejected", async () => {
  expect((await POST(request({ category: "bug", message: "hello there" }))).status).toBe(400);
  expect((await POST(request({ ...valid, feedback_id: "a b" }))).status).toBe(400);
});

test("unknown top-level fields are rejected, not silently ignored", async () => {
  const res = await POST(request({ ...valid, repository_path: "C:/secret" }));
  expect(res.status).toBe(400);
  expect((await res.json()).error).toBe("invalid_field");
});

test("an oversized payload is rejected before parsing", async () => {
  const res = await POST(request({ ...valid, message: "x".repeat(20_000) }));
  expect(res.status).toBe(413);
});

test("malformed JSON returns JSON, never HTML or a stack trace", async () => {
  const res = await POST(request("{not json"));
  expect(res.status).toBe(400);
  expect(res.headers.get("content-type")).toContain("application/json");
  const text = JSON.stringify(await res.json());
  expect(text).not.toMatch(/at .*\.ts:\d+/);
});

test("errors never echo the submitted content back", async () => {
  const res = await POST(request({ ...valid, message: "", secret_marker: "CANARY" }));
  const text = JSON.stringify(await res.json());
  expect(text).not.toContain("CANARY");
});

test("the response is never cached", async () => {
  const res = await POST(request(valid));
  expect(res.headers.get("cache-control")).toContain("no-store");
});

test("repeated submissions from one address are rate limited", async () => {
  const ip = randomIp();
  const statuses: number[] = [];
  for (let i = 0; i < 14; i += 1) {
    const res = await POST(
      new Request("https://atlas.test/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-forwarded-for": ip },
        body: JSON.stringify({ ...valid, feedback_id: `abc123def${i}00` }),
      }),
    );
    statuses.push(res.status);
  }
  expect(statuses).toContain(429);
});
