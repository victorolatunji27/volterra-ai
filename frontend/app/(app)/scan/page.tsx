"use client";
// Daily scan (dashboard) — greeting, stat cards, ranked setups, scanning skeleton.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useTheme, WIN } from "@/components/theme";
import { Spark } from "@/components/charts";
import { rescanIcon } from "@/components/icons";
import EmptyState, { ClockIcon } from "@/components/EmptyState";
import SetupCard from "@/components/SetupCard";
import { useToast } from "@/components/toast";
import { apiSend, fetchSetups } from "@/lib/api";
import { track } from "@/lib/posthog";
import { DEMO_SETUPS, Setup } from "@/lib/demo";
import { useWidth } from "@/lib/useWidth";

const mono = "var(--mono)";

function StatCards({ topTicker, topScore, bullish, total }: { topTicker: string; topScore: number; bullish: number; total: number }) {
  const { ac } = useTheme();
  const cards = [
    { label: "Top setup", big: topTicker, sub: `unusual score ${topScore}`, spark: [20, 24, 27, 31, 34, 38, 42, 46], col: ac.a1 },
    { label: "Bullish setups", big: String(bullish), sub: `of ${total} scanned`, spark: [3, 4, 4, 5, 6, 6, 7, 7], col: WIN },
    { label: "Saved today", big: "3", sub: "in your journal", spark: [0, 1, 1, 2, 2, 2, 3, 3], col: ac.a2 },
    { label: "Market sentiment", big: "Risk-on", sub: "breadth +0.73%", spark: [44, 45, 46, 45, 47, 48, 49, 51], col: WIN },
  ];
  return (
    <>
      {cards.map((c, i) => (
        <div key={i} style={{ position: "relative", padding: "18px 18px 16px", borderRadius: 9, border: "1px solid var(--border)", background: "var(--surface)", backdropFilter: "var(--glass-blur)", WebkitBackdropFilter: "var(--glass-blur)", boxShadow: "var(--shadow)", overflow: "hidden" }}>
          <div style={{ fontSize: 12.5, color: "var(--text-3)", marginBottom: 8, letterSpacing: "0.01em" }}>{c.label}</div>
          <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 10 }}>
            <div>
              <div style={{ fontFamily: mono, fontSize: c.big.length > 4 ? 21 : 26, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1, whiteSpace: "nowrap" }}>{c.big}</div>
              <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 7 }}>{c.sub}</div>
            </div>
            <div style={{ marginBottom: 2 }}>
              <Spark data={c.spark} color={c.col} w={72} h={30} />
            </div>
          </div>
        </div>
      ))}
    </>
  );
}

function ScanningCards() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {[0, 1, 2].map((i) => (
        <div key={i} style={{ borderRadius: 9, border: "1px solid var(--border)", background: "var(--surface)", padding: 24, position: "relative", overflow: "hidden" }}>
          <div style={{ position: "absolute", inset: 0, background: "linear-gradient(90deg,transparent,var(--surface-2),transparent)", backgroundSize: "460px 100%", animation: "shimmer 1.4s linear infinite" }} />
          {i === 0 ? (
            <div style={{ position: "relative", display: "flex", alignItems: "center", gap: 12, color: "var(--text-2)", fontSize: 14 }}>
              <span style={{ width: 18, height: 18, borderRadius: "50%", border: "2px solid var(--border-2)", borderTopColor: "var(--a1)", display: "inline-block", animation: "spin .8s linear infinite" }} />
              Claude is re-scanning today&apos;s options flow…
            </div>
          ) : (
            <div style={{ height: 54 }} />
          )}
          <div style={{ position: "relative", marginTop: i === 0 ? 18 : 0, display: "flex", gap: 10 }}>
            {[0, 1, 2, 3].map((j) => (
              <div key={j} style={{ height: 38, flex: 1, borderRadius: 10, background: "var(--surface-2)" }} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function ScanPage() {
  const w = useWidth();
  const mid = w < 1180;
  const { flash } = useToast();
  const [setups, setSetups] = useState<Setup[]>(DEMO_SETUPS);
  const [empty, setEmpty] = useState(false);
  const [scanning, setScanning] = useState(false);
  const scanTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const alive = useRef(true);

  const load = useCallback(() => {
    fetchSetups().then((r) => {
      if (!alive.current) return;
      setSetups(r.setups);
      setEmpty(r.empty);
    });
  }, []);

  useEffect(() => {
    alive.current = true;
    load();
    return () => { alive.current = false; };
  }, [load]);

  const rescan = () => {
    if (scanning) return;
    track("rescan_triggered");
    // Kick the real scan off server-side (auth required; best-effort in demo
    // mode), then re-check for results after the skeleton animation.
    apiSend("/api/scans/trigger", "POST").then((ok) => {
      if (ok) flash("Re-scan started — fresh setups in a few minutes");
    });
    setScanning(true);
    if (scanTimer.current) clearTimeout(scanTimer.current);
    scanTimer.current = setTimeout(() => {
      setScanning(false);
      load();
    }, 2100);
  };

  const bullish = setups.filter((s) => s.bull).length;
  const dateStr = new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }).replace(/,/g, " ·") + " · 6:30 AM ET";

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 14, marginBottom: 28 }}>
        <div style={{ flexShrink: 0 }}>
          <h1 style={{ fontSize: 30, fontWeight: 600, lineHeight: 1.12, letterSpacing: "-0.03em", margin: "0 0 6px", whiteSpace: "nowrap" }}>Good morning, Alex.</h1>
          <p style={{ fontSize: 15.5, color: "var(--text-2)", margin: 0 }}>Here are today&apos;s top flow setups.</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ fontFamily: mono, fontSize: 13, color: "var(--text-3)" }}>{dateStr}</div>
          <button onClick={rescan} style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 13.5, fontWeight: 500, color: "var(--text)", background: "var(--surface-2)", border: "1px solid var(--border-2)", padding: "9px 15px", borderRadius: 7, display: "inline-flex", alignItems: "center", gap: 8, whiteSpace: "nowrap", flexShrink: 0 }}>
            {rescanIcon} Re-scan
          </button>
        </div>
      </div>

      {empty && !scanning ? (
        /* Weekend / market closed / scan not yet run. */
        <div style={{ marginTop: 24 }}>
          <EmptyState
            icon={<ClockIcon />}
            heading="No scan today"
            body="The scan runs every weekday at 6:30am ET. Check back then, or trigger a manual re-scan."
            actionLabel="Re-scan"
            onAction={rescan}
          />
        </div>
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: mid ? "repeat(2,1fr)" : "repeat(4,1fr)", gap: 16, marginBottom: 14 }}>
            <StatCards topTicker={setups[0]?.t ?? "—"} topScore={setups[0]?.score ?? 0} bullish={bullish} total={setups.length} />
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "30px 0 16px" }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, lineHeight: 1.2, letterSpacing: "-0.01em", margin: 0, whiteSpace: "nowrap" }}>Today&apos;s ranked setups</h2>
            <span style={{ fontSize: 13, color: "var(--text-3)" }}>Sorted by unusual activity score</span>
          </div>

          {scanning ? (
            <ScanningCards />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {setups.map((s) => (
                <SetupCard key={s.t} s={s} />
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
