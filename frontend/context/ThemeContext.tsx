"use client";
// Theme (light/dark) + accent (aurora/oceanic/cosmic) context.
//
// document.documentElement carries data-theme / data-accent and is the single
// source of truth for CSS. A pre-paint inline script in app/layout.tsx sets
// the attributes from localStorage before first paint (no flash of the wrong
// theme); this provider keeps them, localStorage, and React state in sync.
//
// localStorage keys: 'vt-theme' and 'vt-accent'.
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

export const THEME_STORAGE_KEY = "vt-theme";
export const ACCENT_STORAGE_KEY = "vt-accent";

interface ThemeCtx {
  theme: ThemeKey;
  accent: AccentKey;
  ac: (typeof ACCENTS)[AccentKey];
  setTheme: (t: ThemeKey) => void;
  setAccent: (a: AccentKey) => void;
}

const Ctx = createContext<ThemeCtx | null>(null);

function applyToDocument(theme: ThemeKey, accent: AccentKey) {
  document.documentElement.setAttribute("data-theme", theme);
  document.documentElement.setAttribute("data-accent", accent);
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeKey>("light");
  const [accent, setAccentState] = useState<AccentKey>("aurora");

  // On mount: read persisted values (defaults light/aurora) and apply them.
  // The pre-paint script already set the same attributes, so this is
  // idempotent — it exists to sync React state and self-heal if the script
  // was somehow skipped.
  useEffect(() => {
    let t: ThemeKey = "light";
    let a: AccentKey = "aurora";
    try {
      const st = localStorage.getItem(THEME_STORAGE_KEY);
      const sa = localStorage.getItem(ACCENT_STORAGE_KEY);
      if (st === "light" || st === "dark") t = st;
      if (sa && sa in ACCENTS) a = sa as AccentKey;
    } catch {
      /* localStorage unavailable — stick with defaults */
    }
    setThemeState(t);
    setAccentState(a);
    applyToDocument(t, a);
  }, []);

  const setTheme = useCallback((t: ThemeKey) => {
    setThemeState(t);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, t);
    } catch {}
    document.documentElement.setAttribute("data-theme", t);
  }, []);

  const setAccent = useCallback((a: AccentKey) => {
    setAccentState(a);
    try {
      localStorage.setItem(ACCENT_STORAGE_KEY, a);
    } catch {}
    document.documentElement.setAttribute("data-accent", a);
  }, []);

  return (
    <Ctx.Provider value={{ theme, accent, ac: ACCENTS[accent], setTheme, setAccent }}>
      {/* data-theme/data-accent live on <html> only — putting them here too
          would override the pre-paint attributes with stale initial state
          for a frame and reintroduce the flash. */}
      <div
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
