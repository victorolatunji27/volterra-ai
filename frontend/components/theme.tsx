"use client";
// Theme (light/dark) + accent (aurora/oceanic/cosmic) context, persisted to
// localStorage and applied as data-theme / data-accent on the app wrapper.
import React, { createContext, useCallback, useContext, useEffect, useState } from "react";

export const ACCENTS = {
  aurora: { a1: "#c0502a", a2: "#d4733b", a3: "#3f7d5c" },
  oceanic: { a1: "#2f6b54", a2: "#3f846a", a3: "#bd7a2c" },
  cosmic: { a1: "#7d3350", a2: "#9c4569", a3: "#c0903a" },
} as const;
export type AccentKey = keyof typeof ACCENTS;
export type ThemeKey = "light" | "dark";

export const WIN = "#3c8a5f";
export const LOSS = "#bf473f";
export const WARN = "#bd8330";

interface ThemeCtx {
  theme: ThemeKey;
  accent: AccentKey;
  ac: (typeof ACCENTS)[AccentKey];
  setTheme: (t: ThemeKey) => void;
  setAccent: (a: AccentKey) => void;
}

const Ctx = createContext<ThemeCtx | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeKey>("light");
  const [accent, setAccentState] = useState<AccentKey>("aurora");

  useEffect(() => {
    const t = localStorage.getItem("volterra-theme") as ThemeKey | null;
    const a = localStorage.getItem("volterra-accent") as AccentKey | null;
    if (t === "light" || t === "dark") setThemeState(t);
    if (a && a in ACCENTS) setAccentState(a);
  }, []);

  // Mirror onto <html> so the body background (overscroll area) matches too.
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.accent = accent;
  }, [theme, accent]);

  const setTheme = useCallback((t: ThemeKey) => {
    setThemeState(t);
    localStorage.setItem("volterra-theme", t);
  }, []);
  const setAccent = useCallback((a: AccentKey) => {
    setAccentState(a);
    localStorage.setItem("volterra-accent", a);
  }, []);

  return (
    <Ctx.Provider value={{ theme, accent, ac: ACCENTS[accent], setTheme, setAccent }}>
      <div
        data-theme={theme}
        data-accent={accent}
        style={{
          minHeight: "100vh",
          background: "var(--bg)",
          backgroundImage: "var(--bg-grad)",
          color: "var(--text)",
          position: "relative",
          overflowX: "hidden",
        }}
      >
        {children}
      </div>
    </Ctx.Provider>
  );
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}

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
