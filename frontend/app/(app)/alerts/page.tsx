"use client";
// Alerts — email preference toggles + strategy preference chips.
import React, { useState } from "react";
import PaywallGate from "@/components/PaywallGate";
import { useToast } from "@/components/toast";
import { saveStrategyPrefs } from "@/lib/api";
import { useWidth } from "@/lib/useWidth";

const card: React.CSSProperties = { borderRadius: 9, border: "1px solid var(--border)", background: "var(--surface)", padding: 24, boxShadow: "var(--shadow)" };

function Switch({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{ cursor: "pointer", width: 46, height: 26, borderRadius: 9, border: "1px solid " + (on ? "transparent" : "var(--border-2)"), background: on ? "linear-gradient(135deg,var(--a1),var(--a2))" : "var(--surface-2)", position: "relative", transition: "background .2s", flexShrink: 0, padding: 0 }}>
      <span style={{ position: "absolute", top: 3, left: on ? 23 : 3, width: 18, height: 18, borderRadius: "50%", background: "#fff", transition: "left .2s", boxShadow: "0 2px 5px rgba(0,0,0,0.3)" }} />
    </button>
  );
}

const EMAIL_ROWS: [string, string, string][] = [
  ["digest", "Daily digest", "Your ranked scan, delivered at 7:00 AM ET"],
  ["alerts", "Trade alerts", "Real-time pings when a saved ticker shows fresh flow"],
  ["weekly", "Weekly AI review", "A Claude-written performance recap every Sunday"],
];

const ALL_STRATEGIES = ["Momentum", "Earnings Play", "Breakout", "IV Crush", "Hedge", "Contrarian", "Neutral"];

export default function AlertsPage() {
  const { flash } = useToast();
  const w = useWidth();
  const narrow = w < 900;
  const [settings, setSettings] = useState<Record<string, boolean>>({ digest: true, alerts: true, weekly: true });
  const [strategies, setStrategies] = useState<string[]>(["Momentum", "Breakout", "IV Crush"]);

  const toggle = (k: string) => {
    setSettings((s) => ({ ...s, [k]: !s[k] }));
    flash("Preferences saved");
  };

  const toggleStrategy = (t: string) => {
    setStrategies((prev) => {
      const next = prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t];
      // Best-effort persist to the backend's strategy prefs endpoint.
      saveStrategyPrefs(next);
      return next;
    });
  };

  return (
    <PaywallGate feature="alerts center">
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 30, fontWeight: 600, lineHeight: 1.12, letterSpacing: "-0.03em", margin: "0 0 6px", whiteSpace: "nowrap" }}>Alerts</h1>
        <p style={{ fontSize: 15.5, color: "var(--text-2)", margin: 0 }}>Decide when VolterraAI reaches out — and about what.</p>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: narrow ? "1fr" : "1fr 1fr", gap: 18, alignItems: "start" }}>
        <div style={card}>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>Email preferences</div>
          <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 18 }}>Choose what lands in your inbox.</div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            {EMAIL_ROWS.map((r, i) => {
              const row = (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, padding: "16px 0", borderTop: i > 0 ? "1px solid var(--border)" : "none" }}>
                  <div>
                    <div style={{ fontSize: 14.5, fontWeight: 500, marginBottom: 4 }}>{r[1]}</div>
                    <div style={{ fontSize: 13, color: "var(--text-3)", lineHeight: 1.45 }}>{r[2]}</div>
                  </div>
                  <Switch on={settings[r[0]]} onClick={() => toggle(r[0])} />
                </div>
              );
              // The daily digest is Pro after the trial — gate just this row.
              return r[0] === "digest" ? (
                <PaywallGate key={i} feature="daily digest">{row}</PaywallGate>
              ) : (
                <React.Fragment key={i}>{row}</React.Fragment>
              );
            })}
          </div>
        </div>
        <div style={card}>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>Strategy preferences</div>
          <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 18 }}>Only get alerted on the setups you actually trade.</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
            {ALL_STRATEGIES.map((t) => {
              const on = strategies.includes(t);
              return (
                <button key={t} onClick={() => toggleStrategy(t)} style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 13.5, fontWeight: 500, padding: "9px 15px", borderRadius: 10, transition: "all .15s", color: on ? "#faf6ee" : "var(--text-2)", background: on ? "linear-gradient(135deg,var(--a1),var(--a2))" : "var(--surface-2)", border: "1px solid " + (on ? "transparent" : "var(--border-2)") }}>
                  {(on ? "✓ " : "") + t}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </PaywallGate>
  );
}
