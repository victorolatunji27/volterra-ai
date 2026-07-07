"use client";
// Centered empty state used by the scan and journal pages.
// Token-styled only (--surface/--border/--text); no component library.
import React from "react";

export function ClockIcon() {
  return (
    <svg width={24} height={24} viewBox="0 0 24 24">
      <circle cx={12} cy={12} r={8.5} fill="none" stroke="currentColor" strokeWidth={1.7} />
      <path d="M12 7.5V12l3 2" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function BookmarkIcon() {
  return (
    <svg width={24} height={24} viewBox="0 0 24 24">
      <path d="M7 4h10a1 1 0 011 1v15l-6-4-6 4V5a1 1 0 011-1z" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function EmptyState({
  icon,
  heading,
  body,
  actionLabel,
  onAction,
}: {
  icon: React.ReactNode;
  heading: string;
  body: string;
  actionLabel: string;
  onAction: () => void;
}) {
  return (
    <div style={{ padding: "64px 24px", textAlign: "center", borderRadius: 9, border: "1px dashed var(--border-2)", background: "var(--surface)" }}>
      <div style={{ width: 46, height: 46, borderRadius: 8, background: "var(--surface-2)", border: "1px solid var(--border)", display: "grid", placeItems: "center", margin: "0 auto 18px", color: "var(--text-3)" }}>
        {icon}
      </div>
      <h3 style={{ fontFamily: "var(--serif)", fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em", margin: "0 0 8px", color: "var(--text)" }}>
        {heading}
      </h3>
      <p style={{ fontSize: 14, lineHeight: 1.55, color: "var(--text-2)", maxWidth: 380, margin: "0 auto 22px" }}>{body}</p>
      <button
        onClick={onAction}
        style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 13.5, fontWeight: 600, color: "#faf6ee", background: "linear-gradient(135deg,var(--a1),var(--a2))", border: "none", padding: "11px 20px", borderRadius: 7 }}
      >
        {actionLabel}
      </button>
    </div>
  );
}
