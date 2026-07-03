"use client";

// App Router global error boundary. Replaces the legacy Pages-Router /500 page.
// It must render its own root document shell (the html + body elements below)
// because it substitutes the root layout when a top-level error occurs. This is
// plain React JSX — not an import from the legacy document module.
export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#06070A",
          color: "#e6e8ee",
          fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
        }}
      >
        <div style={{ textAlign: "center", padding: 24, maxWidth: 460 }}>
          <h1 style={{ fontSize: "1.5rem", margin: "0 0 10px" }}>Something went wrong</h1>
          <p style={{ opacity: 0.7, margin: "0 0 22px" }}>
            An unexpected error occurred. Please try again.
          </p>
          <button
            onClick={() => reset()}
            style={{
              padding: "10px 18px",
              borderRadius: 8,
              border: "1px solid #2a2f3a",
              background: "#11141b",
              color: "#e6e8ee",
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
