"use client";
// App shell — sidebar navigation + main column, per the design's isApp section.
import React from "react";
import { usePathname, useRouter } from "next/navigation";
import ErrorBoundary from "@/components/ErrorBoundary";
import { ThemeControls, useTheme } from "@/components/theme";
import { ICONS, svgIcon } from "@/components/icons";
import { useWidth } from "@/lib/useWidth";

const NAV_ITEMS: [string, string, keyof typeof ICONS][] = [
  ["/scan", "Daily scan", "scan"],
  ["/journal", "Journal", "journal"],
  ["/analytics", "Analytics", "analytics"],
  ["/alerts", "Alerts", "alerts"],
  ["/settings", "Settings", "settings"],
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { ac } = useTheme();
  const w = useWidth();
  const narrow = w < 900;

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      {/* SIDEBAR */}
      <aside style={{ width: narrow ? 68 : 232, flexShrink: 0, borderRight: "1px solid var(--border)", background: "var(--surface)", backdropFilter: "var(--glass-blur)", WebkitBackdropFilter: "var(--glass-blur)", position: "sticky", top: 0, height: "100vh", display: "flex", flexDirection: "column", padding: "22px 14px", zIndex: 30 }}>
        <div onClick={() => router.push("/scan")} style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 9, padding: "6px 8px", marginBottom: 26 }}>
          {!narrow ? (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img className="vm-light" src="/assets/volterra-logo.png" alt="Volterra" style={{ height: 25, width: "auto", display: "block" }} />
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img className="vm-dark" src="/assets/volterra-logo-reversed.png" alt="Volterra" style={{ height: 25, width: "auto", display: "block" }} />
              <span style={{ fontFamily: "var(--sans)", fontSize: 12.5, fontWeight: 700, letterSpacing: "0.04em", color: "var(--a1)" }}>AI</span>
            </>
          ) : (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img src="/assets/volterra-icon.png" alt="Volterra" style={{ width: 34, height: 34, borderRadius: 9, display: "block" }} />
          )}
        </div>
        <nav style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          {NAV_ITEMS.map(([route, label, ic]) => {
            const active = pathname === route || (route === "/scan" && pathname.startsWith("/ticker"));
            return (
              <div
                key={route}
                onClick={() => router.push(route)}
                title={label}
                style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 12, padding: "10px 11px", borderRadius: 7, transition: "background .15s,color .15s", color: active ? "var(--text)" : "var(--text-2)", background: active ? "var(--a1-soft)" : "transparent", border: "1px solid " + (active ? "var(--border)" : "transparent"), justifyContent: narrow ? "center" : "flex-start" }}
              >
                <span style={{ display: "grid", placeItems: "center", width: 20, height: 20, flexShrink: 0, color: active ? ac.a1 : "var(--text-3)" }}>{svgIcon(ICONS[ic])}</span>
                {narrow ? null : <span style={{ fontSize: 14.5, fontWeight: active ? 600 : 500 }}>{label}</span>}
              </div>
            );
          })}
        </nav>
        <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 12 }}>
          <ThemeControls />
          {!narrow ? (
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: 10, borderRadius: 7, border: "1px solid var(--border)", background: "var(--surface-2)" }}>
              <div style={{ width: 32, height: 32, borderRadius: "50%", background: "linear-gradient(135deg,var(--a1),var(--a3))", display: "grid", placeItems: "center", fontSize: 13, fontWeight: 600, color: "#faf6ee", flexShrink: 0 }}>A</div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>Alex Rivera</div>
                <div style={{ fontSize: 11.5, color: "var(--text-3)" }}>Pro plan</div>
              </div>
            </div>
          ) : null}
        </div>
      </aside>

      {/* MAIN — every app view (/scan, /ticker/*, /journal, /analytics, …)
          renders inside the render-error boundary. */}
      <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <div style={{ maxWidth: 1180, width: "100%", margin: "0 auto", padding: "34px 38px 80px" }}>
          <ErrorBoundary>{children}</ErrorBoundary>
        </div>
      </main>
    </div>
  );
}
