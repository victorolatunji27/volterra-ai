"use client";
// Loading-skeleton primitives + the inline fetch-error card.
// Skeletons use the .shimmer class from globals.css and should roughly match
// the shape (height, row count) of the content they stand in for.
import React from "react";

/** One shimmering block. */
export function Sk({ h, w, r = 7, style }: { h: number; w?: number | string; r?: number; style?: React.CSSProperties }) {
  return <div className="shimmer" style={{ height: h, width: w ?? "100%", borderRadius: r, ...style }} />;
}

/** A card-shaped skeleton with a few content lines. */
export function SkCard({ h = 220, lines = 3 }: { h?: number; lines?: number }) {
  return (
    <div style={{ borderRadius: 9, border: "1px solid var(--border)", background: "var(--surface)", padding: 22, boxShadow: "var(--shadow)", height: h, display: "flex", flexDirection: "column", gap: 14 }}>
      <Sk h={16} w="40%" />
      {Array.from({ length: lines }).map((_, i) => (
        <Sk key={i} h={12} w={`${88 - i * 14}%`} />
      ))}
      <div style={{ marginTop: "auto" }}>
        <Sk h={34} w="100%" r={9} />
      </div>
    </div>
  );
}

/** Inline error card with a Retry button, for failed data fetches. */
export function InlineError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 14, padding: "16px 18px", borderRadius: 9, border: "1px solid rgba(191,71,63,0.35)", background: "rgba(191,71,63,0.08)" }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10, minWidth: 0 }}>
        <span style={{ color: "#bf473f", fontSize: 15, lineHeight: 1.2 }}>⚠</span>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text)", marginBottom: 3 }}>Couldn&apos;t load this section</div>
          <div style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.45, overflowWrap: "anywhere" }}>{message}</div>
        </div>
      </div>
      <button onClick={onRetry} style={{ cursor: "pointer", flexShrink: 0, fontFamily: "inherit", fontSize: 13, fontWeight: 600, color: "var(--text)", background: "var(--surface-2)", border: "1px solid var(--border-2)", padding: "8px 16px", borderRadius: 7 }}>
        Retry
      </button>
    </div>
  );
}
