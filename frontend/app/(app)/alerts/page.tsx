"use client";
// Alerts — email preference toggles + strategy preference chips, with a
// one-time first-run prompt when the user has no saved strategy_tags yet.
import React, { useEffect, useState } from "react";
import PaywallGate from "@/components/PaywallGate";
import { useToast } from "@/components/toast";
import { fetchMe, saveStrategyPrefs } from "@/lib/api";
import { track } from "@/lib/posthog";
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

// API tag -> display label, in the first-run prompt's order.
const FIRST_RUN_TAGS: [string, string][] = [
  ["momentum", "Momentum"],
  ["earnings_play", "Earnings Play"],
  ["iv_crush", "IV Crush"],
  ["breakout", "Breakout"],
  ["hedge", "Hedge"],
  ["contrarian", "Contrarian"],
  ["neutral", "Neutral"],
];
const API_TO_LABEL = Object.fromEntries(FIRST_RUN_TAGS);

export default function AlertsPage() {
  const { flash } = useToast();
  const w = useWidth();
  const narrow = w < 900;
  const [settings, setSettings] = useState<Record<string, boolean>>({ digest: true, alerts: true, weekly: true });
  const [strategies, setStrategies] = useState<string[]>(["Momentum", "Breakout", "IV Crush"]);
  // 'loading' until /api/users/me answers; 'firstRun' only when the user has
  // no saved strategy_tags yet. Demo mode (me === null) goes straight to
  // 'normal' with the illustrative defaults.
  const [phase, setPhase] = useState<"loading" | "firstRun" | "normal">("loading");
  const [firstRunSelected, setFirstRunSelected] = useState<string[]>([]);

  useEffect(() => {
    let alive = true;
    fetchMe().then((me) => {
      if (!alive) return;
      if (me && (!me.strategy_tags || me.strategy_tags.length === 0)) {
        setPhase("firstRun");
        return;
      }
      if (me?.strategy_tags?.length) {
        // Once tags are non-empty, always the normal layout — seeded from them.
        setStrategies(me.strategy_tags.map((t) => API_TO_LABEL[t]).filter(Boolean));
      }
      setPhase("normal");
    });
    return () => { alive = false; };
  }, []);

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

  const saveFirstRun = () => {
    // Best-effort in demo mode; the UI transitions either way.
    saveStrategyPrefs(firstRunSelected);
    track("strategy_preferences_saved", { tags: firstRunSelected });
    setStrategies(firstRunSelected);
    setPhase("normal");
    flash("Preferences saved");
  };

  const skipFirstRun = () => {
    setStrategies([]);
    setPhase("normal");
  };

  return (
    <PaywallGate feature="alerts center">
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 30, fontWeight: 600, lineHeight: 1.12, letterSpacing: "-0.03em", margin: "0 0 6px", whiteSpace: "nowrap" }}>Alerts</h1>
        <p style={{ fontSize: 15.5, color: "var(--text-2)", margin: 0 }}>Decide when VolterraAI reaches out — and about what.</p>
      </div>

      {phase === "loading" ? null : phase === "firstRun" ? (
        /* First-run prompt — shown once, until strategy_tags is non-empty. */
        <div style={{ ...card, maxWidth: 560, margin: "36px auto 0", textAlign: "center", padding: "40px 36px" }}>
          <h2 style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em", margin: "0 0 10px" }}>Which setups do you trade?</h2>
          <p style={{ fontSize: 14.5, lineHeight: 1.55, color: "var(--text-2)", margin: "0 0 26px" }}>
            Pick the strategies you want to be alerted on. You can change this any time.
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "center", marginBottom: 28 }}>
            {FIRST_RUN_TAGS.map(([, labelText]) => {
              const on = firstRunSelected.includes(labelText);
              return (
                <button
                  key={labelText}
                  onClick={() => setFirstRunSelected((prev) => (prev.includes(labelText) ? prev.filter((x) => x !== labelText) : [...prev, labelText]))}
                  style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 13.5, fontWeight: 500, padding: "9px 15px", borderRadius: 10, transition: "all .15s", color: on ? "var(--a1)" : "var(--text-2)", background: on ? "var(--a1-soft)" : "var(--surface-2)", border: "1px solid " + (on ? "var(--a1)" : "var(--border-2)") }}
                >
                  {(on ? "✓ " : "") + labelText}
                </button>
              );
            })}
          </div>
          <button onClick={saveFirstRun} style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 13.5, fontWeight: 600, color: "#faf6ee", background: "linear-gradient(135deg,var(--a1),var(--a2))", border: "none", padding: "11px 22px", borderRadius: 7 }}>
            Save preferences
          </button>
          <div style={{ marginTop: 14 }}>
            <button onClick={skipFirstRun} style={{ cursor: "pointer", background: "none", border: "none", fontFamily: "inherit", fontSize: 12.5, fontWeight: 500, color: "var(--text-3)", padding: 0 }}>
              Skip for now
            </button>
          </div>
        </div>
      ) : (
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
      )}
    </PaywallGate>
  );
}
