"use client";

const ANON_KEY = "atlas_anonymous_id";

function anonymousId(): string {
  try {
    let id = localStorage.getItem(ANON_KEY);
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(ANON_KEY, id);
    }
    return id;
  } catch {
    return "anon-unavailable";
  }
}

export async function trackClientEvent(
  event_name: string,
  metadata?: Record<string, unknown>,
  source = "website"
): Promise<void> {
  try {
    await fetch("/api/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_name,
        anonymous_id: anonymousId(),
        source,
        platform: typeof navigator !== "undefined" ? navigator.platform : "web",
        metadata: metadata || {},
      }),
      keepalive: true,
    });
  } catch {
    // analytics must never break UX
  }
}
