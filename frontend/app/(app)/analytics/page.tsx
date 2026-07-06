"use client";
// Analytics — overview cards, equity curve, strategy donut, ticker perf, weekly AI review.
import React, { useEffect, useState } from "react";
import { useTheme, WIN, LOSS } from "@/components/theme";
import { Spark, Area, Donut } from "@/components/charts";
import { useToast } from "@/components/toast";
import { fetchAnalytics, AnalyticsData } from "@/lib/api";
import { DEMO_ANALYTICS_OVERVIEW, DEMO_EQUITY, DEMO_STRATEGY_PERF, DEMO_TICKER_PERF } from "@/lib/demo";
import { useWidth } from "@/lib/useWidth";

const mono = "var(--mono)";
const card: React.CSSProperties = { borderRadius: 9, border: "1px solid var(--border)", background: "var(--surface)", padding: 24, boxShadow: "var(--shadow)" };

export default function AnalyticsPage() {
  const { ac } = useTheme();
  const { flash } = useToast();
  const w = useWidth();
  const mid = w < 1180;
  const narrow = w < 900;
  const [data, setData] = useState<AnalyticsData>({
    demo: true,
    overview: DEMO_ANALYTICS_OVERVIEW,
    equity: DEMO_EQUITY,
    strategyPerf: DEMO_STRATEGY_PERF,
    tickerPerf: DEMO_TICKER_PERF,
  });

  useEffect(() => {
    let alive = true;
    fetchAnalytics().then((d) => { if (alive) setData(d); });
    return () => { alive = false; };
  }, []);

  const o = data.overview;
  const overviewCards = [
    { l: "Total trades", v: o.totalTrades, s: o.totalSub, c: "var(--text)", sp: o.totalSpark, sc: ac.a1 },
    { l: "Win rate", v: o.winRate, s: o.winSub, c: WIN, sp: o.winSpark, sc: WIN },
    { l: "Average P&L", v: o.avgPnl, s: o.avgSub, c: WIN, sp: o.avgSpark, sc: WIN },
    { l: "Best setup", v: o.bestSetup, s: o.bestSub, c: WIN, sp: o.bestSpark, sc: WIN },
  ];
  const segs = data.strategyPerf.map((s) => ({ value: s.t, color: s.c }));
  const maxPerf = Math.max(...data.tickerPerf.map((d) => Math.abs(d[1])));
  const bullets = [
    "Momentum setups outperform earnings trades by 18% on realized return.",
    "Your win rate climbs to 74% when IV rank is below 55 at entry.",
    "Trades held past expiry week underperform — consider trimming earlier.",
  ];

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 30, fontWeight: 600, lineHeight: 1.12, letterSpacing: "-0.03em", margin: "0 0 6px", whiteSpace: "nowrap" }}>Analytics</h1>
        <p style={{ fontSize: 15.5, color: "var(--text-2)", margin: 0 }}>How your decisions are actually performing — measured, not guessed.</p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: mid ? "repeat(2,1fr)" : "repeat(4,1fr)", gap: 16, marginBottom: 18 }}>
        {overviewCards.map((c, i) => (
          <div key={i} style={{ padding: "18px 20px", borderRadius: 9, border: "1px solid var(--border)", background: "var(--surface)", backdropFilter: "var(--glass-blur)", WebkitBackdropFilter: "var(--glass-blur)", boxShadow: "var(--shadow)" }}>
            <div style={{ fontSize: 12.5, color: "var(--text-3)", marginBottom: 9 }}>{c.l}</div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 10 }}>
              <div>
                <div style={{ fontFamily: mono, fontSize: 27, fontWeight: 600, letterSpacing: "-0.02em", color: c.c }}>{c.v}</div>
                <div style={{ fontSize: 11.5, color: "var(--text-3)", marginTop: 7 }}>{c.s}</div>
              </div>
              <div style={{ marginBottom: 2 }}>
                <Spark data={c.sp} color={c.sc} w={68} h={30} />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: mid ? "1fr" : "1.5fr 1fr", gap: 18, marginBottom: 18, alignItems: "start" }}>
        {/* Equity curve */}
        <div style={card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18 }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>Equity curve</div>
              <div style={{ fontSize: 12.5, color: "var(--text-3)", marginTop: 3 }}>Hypothetical · $10k base · last 90 days</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontFamily: mono, fontSize: 20, fontWeight: 600, color: WIN }}>{o.equityPct}</div>
              <div style={{ fontSize: 11.5, color: "var(--text-3)", marginTop: 3 }}>{o.equityBalance}</div>
            </div>
          </div>
          <Area data={data.equity} color={ac.a1} w={640} h={210} />
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10, fontSize: 11, fontFamily: mono, color: "var(--text-3)" }}>
            {["Mar", "Apr", "May", "Jun"].map((m) => <span key={m}>{m}</span>)}
          </div>
        </div>

        {/* Win rate by strategy */}
        <div style={card}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 2 }}>Win rate by strategy</div>
          <div style={{ fontSize: 12.5, color: "var(--text-3)", marginBottom: 18 }}>Ring sized by trade count</div>
          <div style={{ display: "flex", alignItems: "center", gap: 22, flexWrap: "wrap" }}>
            <div style={{ position: "relative", width: 148, height: 148, flexShrink: 0 }}>
              <Donut segs={segs} size={148} sw={18} />
              <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                <div style={{ fontFamily: mono, fontSize: 22, fontWeight: 600 }}>{o.overallWin}</div>
                <div style={{ fontSize: 10.5, color: "var(--text-3)" }}>overall</div>
              </div>
            </div>
            <div style={{ flex: 1, minWidth: 170, display: "flex", flexDirection: "column", gap: 13 }}>
              {data.strategyPerf.map((s, i) => (
                <div key={i}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 5 }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--text-2)" }}>
                      <span style={{ width: 8, height: 8, borderRadius: "50%", background: s.c }} />{s.n}
                    </span>
                    <span style={{ fontFamily: mono, fontSize: 13, fontWeight: 600 }}>{s.w}%</span>
                  </div>
                  <div style={{ height: 4, borderRadius: 3, background: "var(--surface-2)", overflow: "hidden" }}>
                    <div style={{ height: "100%", width: s.w + "%", background: s.c, borderRadius: 3 }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: narrow ? "1fr" : "1fr 1fr", gap: 18, alignItems: "start" }}>
        {/* Ticker performance */}
        <div style={card}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 2 }}>Ticker performance</div>
          <div style={{ fontSize: 12.5, color: "var(--text-3)", marginBottom: 20 }}>Realized P&amp;L by symbol</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 15 }}>
            {data.tickerPerf.map((d, i) => {
              const pos = d[1] >= 0;
              return (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "58px 1fr 64px", alignItems: "center", gap: 12 }}>
                  <span style={{ fontSize: 13.5, fontWeight: 600 }}>{d[0]}</span>
                  <div style={{ height: 20, borderRadius: 6, background: "var(--surface-2)", overflow: "hidden" }}>
                    <div style={{ height: "100%", width: (Math.abs(d[1]) / maxPerf) * 100 + "%", borderRadius: 6, background: pos ? `linear-gradient(90deg,${WIN}aa,${WIN})` : `linear-gradient(90deg,${LOSS}aa,${LOSS})` }} />
                  </div>
                  <span style={{ textAlign: "right", fontFamily: mono, fontSize: 13.5, fontWeight: 600, color: pos ? WIN : LOSS }}>{(pos ? "+" : "") + d[1]}%</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Weekly AI review */}
        <div style={{ position: "relative", borderRadius: 9, border: "1px solid var(--border-2)", background: "linear-gradient(160deg,var(--a1-soft),var(--surface))", padding: 24, boxShadow: "var(--shadow)", overflow: "hidden" }}>
          <div style={{ position: "absolute", top: -40, right: -30, width: 160, height: 160, borderRadius: "50%", background: "radial-gradient(closest-side,var(--a1-soft),transparent)", filter: "blur(10px)" }} />
          <div style={{ position: "relative" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
              <div style={{ width: 28, height: 28, borderRadius: 8, background: "linear-gradient(135deg,var(--a1),var(--a2))", display: "grid", placeItems: "center" }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: "#faf6ee" }}>AI</span>
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>Weekly AI review</div>
                <div style={{ fontSize: 11.5, color: "var(--text-3)" }}>Week of Jun 9 · generated by Claude</div>
              </div>
            </div>
            <p style={{ margin: "0 0 18px", fontSize: 17, lineHeight: 1.45, fontWeight: 500, letterSpacing: "-0.01em", textWrap: "pretty" }}>
              Your momentum setups are outperforming your earnings trades by 18%. Lean into what is working.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
              {bullets.map((b, i) => (
                <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                  <span style={{ color: ac.a3, fontSize: 13, marginTop: 1 }}>▸</span>
                  <span style={{ fontSize: 13.5, lineHeight: 1.5, color: "var(--text-2)" }}>{b}</span>
                </div>
              ))}
            </div>
            <button onClick={() => flash("Full weekly review opened")} style={{ cursor: "pointer", marginTop: 20, fontFamily: "inherit", fontSize: 13, fontWeight: 500, color: "var(--text)", background: "var(--surface-2)", border: "1px solid var(--border-2)", padding: "9px 16px", borderRadius: 10 }}>
              View full review →
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
