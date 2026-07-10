"use client";
// Root-level React render-error boundary. Replaces the entire root layout
// when it fires, so it renders its own <html>/<body> with inline styles
// (globals.css is not loaded here).
import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="en">
      <body style={{ margin: 0, minHeight: "100vh", display: "grid", placeItems: "center", background: "#e9e1cf", color: "#221e16", fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" }}>
        <div style={{ textAlign: "center", padding: 32, maxWidth: 420 }}>
          <h1 style={{ fontFamily: "Georgia, serif", fontSize: 26, fontWeight: 600, margin: "0 0 10px" }}>Something went wrong</h1>
          <p style={{ fontSize: 14.5, lineHeight: 1.55, color: "#5d5645", margin: "0 0 22px" }}>
            The error has been reported. Try reloading — if it persists, check back shortly.
          </p>
          <button
            onClick={reset}
            style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 14, fontWeight: 600, color: "#faf6ee", background: "linear-gradient(135deg,#c0502a,#d4733b)", border: "none", padding: "11px 22px", borderRadius: 7 }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
