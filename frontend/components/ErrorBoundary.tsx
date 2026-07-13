"use client";
// Class-based render-error boundary. Catches errors below it, reports to
// Sentry, and shows a token-styled fallback card instead of a white screen.
import React from "react";
import * as Sentry from "@sentry/nextjs";

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
}

export default class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    Sentry.captureException(error, { contexts: { react: { componentStack: errorInfo.componentStack } } });
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div style={{ display: "grid", placeItems: "center", padding: "72px 24px" }}>
        <div style={{ maxWidth: 400, width: "100%", textAlign: "center", padding: "32px 28px", borderRadius: 9, border: "1px solid var(--border-2)", background: "var(--surface)", boxShadow: "var(--shadow)" }}>
          <h3 style={{ fontFamily: "var(--serif)", fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em", margin: "0 0 8px", color: "var(--text)" }}>
            Something went wrong
          </h3>
          <p style={{ fontSize: 14, lineHeight: 1.55, color: "var(--text-2)", margin: "0 0 20px" }}>
            This section failed to load. Try refreshing.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 13.5, fontWeight: 600, color: "#faf6ee", background: "linear-gradient(135deg,var(--a1),var(--a2))", border: "none", padding: "11px 22px", borderRadius: 7 }}
          >
            Refresh
          </button>
        </div>
      </div>
    );
  }
}
