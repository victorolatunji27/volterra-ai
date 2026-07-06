"use client";
// Bottom-center toast with the ✓ chip, per the design's TOAST block.
import React, { createContext, useCallback, useContext, useRef, useState } from "react";

const Ctx = createContext<{ flash: (msg: string) => void } | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toast, setToast] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flash = useCallback((msg: string) => {
    if (timer.current) clearTimeout(timer.current);
    setToast(msg);
    timer.current = setTimeout(() => setToast(null), 2600);
  }, []);

  return (
    <Ctx.Provider value={{ flash }}>
      {children}
      {toast ? (
        <div style={{ position: "fixed", bottom: 26, left: "50%", transform: "translateX(-50%)", zIndex: 90, display: "flex", alignItems: "center", gap: 11, padding: "13px 18px", borderRadius: 7, background: "var(--surface-2)", backdropFilter: "var(--glass-blur)", WebkitBackdropFilter: "var(--glass-blur)", border: "1px solid var(--border-2)", boxShadow: "0 20px 50px -16px rgba(0,0,0,0.5)", fontSize: 14 }}>
          <span style={{ width: 20, height: 20, borderRadius: "50%", background: "var(--a3)", display: "grid", placeItems: "center", color: "#faf6ee", fontSize: 13 }}>✓</span>
          {toast}
        </div>
      ) : null}
    </Ctx.Provider>
  );
}

export function useToast() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
