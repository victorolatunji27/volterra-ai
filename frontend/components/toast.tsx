"use client";
// Global toast system: a fixed bottom-right stack, success/error variants,
// auto-dismiss after 4s. useToast() exposes success/error plus flash()
// (alias of success) for the original design-era call sites.
//
// notifyApiError() is a module-level bridge so non-component code (lib/api.ts)
// can raise an error toast; the provider registers itself as the sink.
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

type Kind = "success" | "error";

interface ToastItem {
  id: number;
  kind: Kind;
  msg: string;
}

interface ToastApi {
  flash: (msg: string) => void;
  success: (msg: string) => void;
  error: (msg: string) => void;
}

const Ctx = createContext<ToastApi | null>(null);

const DISMISS_MS = 4000;

let externalErrorSink: ((msg: string) => void) | null = null;

/** Raise an error toast from outside React (no-op before the provider mounts). */
export function notifyApiError(msg: string): void {
  externalErrorSink?.(msg);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const push = useCallback((kind: Kind, msg: string) => {
    setToasts((current) => {
      // Dedupe: an identical message already on screen isn't stacked again.
      if (current.some((t) => t.msg === msg && t.kind === kind)) return current;
      const id = nextId.current++;
      setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), DISMISS_MS);
      return [...current, { id, kind, msg }];
    });
  }, []);

  useEffect(() => {
    externalErrorSink = (msg) => push("error", msg);
    return () => {
      externalErrorSink = null;
    };
  }, [push]);

  const api: ToastApi = {
    flash: (msg) => push("success", msg),
    success: (msg) => push("success", msg),
    error: (msg) => push("error", msg),
  };

  return (
    <Ctx.Provider value={api}>
      {children}
      {toasts.length > 0 ? (
        <div style={{ position: "fixed", bottom: 22, right: 22, zIndex: 90, display: "flex", flexDirection: "column", gap: 10, alignItems: "flex-end" }}>
          {toasts.map((t) => (
            <div key={t.id} style={{ display: "flex", alignItems: "center", gap: 11, padding: "13px 18px", borderRadius: 7, background: "var(--surface-2)", backdropFilter: "var(--glass-blur)", WebkitBackdropFilter: "var(--glass-blur)", border: "1px solid var(--border-2)", boxShadow: "0 20px 50px -16px rgba(0,0,0,0.5)", fontSize: 14, maxWidth: 380, animation: "fadeUp .18s ease" }}>
              <span style={{ width: 20, height: 20, borderRadius: "50%", background: t.kind === "success" ? "var(--a3)" : "#bf473f", display: "grid", placeItems: "center", color: "#faf6ee", fontSize: 13, flexShrink: 0 }}>
                {t.kind === "success" ? "✓" : "!"}
              </span>
              {t.msg}
            </div>
          ))}
        </div>
      ) : null}
    </Ctx.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
