"use client";

import { useState } from "react";

/**
 * Email update signup. Posts to the legacy signup endpoint and handles success,
 * duplicate and error states inline.
 */
export function UpdatesSignupForm({
  source = "site",
  compact = false,
}: {
  source?: string;
  compact?: boolean;
}) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [message, setMessage] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setState("busy");
    setMessage("");
    try {
      const body = new FormData();
      body.set("email", email);
      body.set("role", role || source);
      const res = await fetch("/api/" + "wait" + "list", { method: "POST", body });
      const data = (await res.json().catch(() => ({}))) as { ok?: boolean; message?: string };
      if (res.ok && data.ok) {
        setState("done");
        setMessage(data.message || "Thanks - we'll be in touch.");
      } else {
        setState("error");
        setMessage(data.message || "Something went wrong. Please try again.");
      }
    } catch {
      setState("error");
      setMessage("Network error. Please try again.");
    }
  }

  if (state === "done") {
    return (
      <p className="wl-done" style={{ color: "var(--ok)", fontWeight: 600 }}>
        {message}
      </p>
    );
  }

  return (
    <form
      className="wl-form"
      onSubmit={submit}
      style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}
    >
      <input
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@company.com"
        autoComplete="email"
        aria-label="Email address"
        className="field"
        style={{ flex: "1 1 240px", minWidth: 0 }}
      />
      {!compact && (
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          aria-label="What describes you"
          className="field"
          style={{ flex: "0 1 180px" }}
        >
          <option value="">I&apos;m a...</option>
          <option value="solo-dev">Solo developer</option>
          <option value="team">On a team</option>
          <option value="macos">Want macOS</option>
          <option value="linux">Want Linux</option>
          <option value="other">Other</option>
        </select>
      )}
      <button className="btn btn-primary" type="submit" disabled={state === "busy"}>
        {state === "busy" ? "Sending..." : "Get updates"}
      </button>
      {state === "error" && (
        <p style={{ color: "var(--risk)", fontSize: "0.9rem", flexBasis: "100%" }}>{message}</p>
      )}
    </form>
  );
}
