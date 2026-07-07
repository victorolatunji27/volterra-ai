"use client";
// Theme controls UI (accent swatches + light/dark toggle).
//
// The provider/context itself lives in context/ThemeContext.tsx; everything
// is re-exported here so existing `@/components/theme` imports keep working.
import React from "react";
import { ACCENTS, AccentKey, useTheme } from "@/context/ThemeContext";

export {
  ACCENTS,
  LOSS,
  ThemeProvider,
  useTheme,
  WARN,
  WIN,
} from "@/context/ThemeContext";
export type { AccentKey, ThemeKey } from "@/context/ThemeContext";

/** Accent swatch strip + light/dark toggle, as in the design's nav/sidebar. */
export function ThemeControls() {
  const { theme, accent, setTheme, setAccent } = useTheme();
  const isDark = theme === "dark";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 9px", borderRadius: 7, border: "1px solid var(--border-2)", background: "var(--surface-2)" }}>
        {(Object.keys(ACCENTS) as AccentKey[]).map((k) => {
          const a = ACCENTS[k];
          const on = accent === k;
          return (
            <button
              key={k}
              title={k}
              onClick={() => setAccent(k)}
              style={{ cursor: "pointer", width: on ? 22 : 16, height: 16, borderRadius: 8, border: on ? "2px solid var(--text)" : "1px solid var(--border-2)", background: `linear-gradient(135deg,${a.a1},${a.a2})`, padding: 0, transition: "width .15s" }}
            />
          );
        })}
      </div>
      <button
        onClick={() => setTheme(isDark ? "light" : "dark")}
        title="Toggle theme"
        style={{ cursor: "pointer", width: 34, height: 34, borderRadius: 10, border: "1px solid var(--border-2)", background: "var(--surface-2)", color: "var(--text-2)", display: "grid", placeItems: "center", padding: 0 }}
      >
        {isDark ? (
          <svg width={18} height={18} viewBox="0 0 24 24">
            <path d="M12 3v1.5M12 19.5V21M4.2 4.2l1.1 1.1M18.7 18.7l1.1 1.1M3 12h1.5M19.5 12H21M4.2 19.8l1.1-1.1M18.7 5.3l1.1-1.1" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" />
            <circle cx={12} cy={12} r={3.6} fill="none" stroke="currentColor" strokeWidth={1.7} />
          </svg>
        ) : (
          <svg width={18} height={18} viewBox="0 0 24 24">
            <path d="M20 14.5A8 8 0 119.5 4 6.2 6.2 0 0020 14.5z" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </button>
    </div>
  );
}
