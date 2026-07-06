"use client";
// Ticker detail — breadcrumb, header, 5 tabs (Overview / Flow stats / AI
// analysis / News / History), market data panel, and catalysts teaser.
import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTheme, WIN, LOSS, WARN } from "@/components/theme";
import { Area } from "@/components/charts";
import { useToast } from "@/components/toast";
import { tagFor } from "@/lib/tags";
import { apiSend, fetchTicker, TickerDetail } from "@/lib/api";
import {
  DEMO_AI_BLOCKS, DEMO_NEWS_FULL, DEMO_NEWS_TEASER,
  DEMO_HISTORY_WEEKS, DEMO_HISTORY_ROWS, DEMO_SETUPS, DEMO_TICKER_SERIES,
} from "@/lib/demo";
import { useWidth } from "@/lib/useWidth";

const mono = "var(--mono)";
type Tab = "overview" | "flow" | "ai" | "news" | "history";

const card: React.CSSProperties = { borderRadius: 9, border: "1px solid var(--border)", background: "var(--surface)", backdropFilter: "var(--glass-blur)", WebkitBackdropFilter: "var(--glass-blur)", padding: 22, boxShadow: "var(--shadow)" };

function MarketPanel({ d }: { d: TickerDetail }) {
  const { ac } = useTheme();
  const s = d.setup;
  const rows = [
    { l: "Call / Put ratio", v: s.cp.toFixed(1), sub: s.cp >= 1 ? "calls dominant" : "puts dominant", pct: Math.min(s.cp / 3.8, 1), c: WIN },
    { l: "IV rank", v: String(s.iv), sub: "52-week percentile", pct: s.iv / 100, c: ac.a1 },
    { l: "Volume", v: "48.2M", sub: "vs 31.0M avg", pct: 0.84, c: ac.a2 },
    { l: "Open interest", v: "1.21M", sub: "+4.2% today", pct: 0.55, c: ac.a3 },
  ];
  return (
    <div style={card}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 18, letterSpacing: "-0.01em" }}>Market data</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        {rows.map((r, i) => (
          <div key={i}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 7 }}>
              <span style={{ fontSize: 13, color: "var(--text-2)" }}>{r.l}</span>
              <span style={{ fontFamily: mono, fontSize: 15, fontWeight: 600 }}>{r.v}</span>
            </div>
            <div style={{ height: 5, borderRadius: 4, background: "var(--surface-2)", overflow: "hidden" }}>
              <div style={{ height: "100%", width: r.pct * 100 + "%", borderRadius: 4, background: r.c }} />
            </div>
            <div style={{ fontSize: 11.5, color: "var(--text-3)", marginTop: 6 }}>{r.sub}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function NewsTeaser({ onAll }: { onAll: () => void }) {
  return (
    <div style={card}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>Catalysts</span>
        <span onClick={onAll} style={{ cursor: "pointer", fontSize: 12, color: "var(--a1)" }}>All news →</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {DEMO_NEWS_TEASER.map((it, i) => (
          <div key={i} style={{ display: "flex", gap: 11, paddingBottom: i < 2 ? 14 : 0, borderBottom: i < 2 ? "1px solid var(--border)" : "none" }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: WIN, marginTop: 6, flexShrink: 0 }} />
            <div>
              <div style={{ fontSize: 13, lineHeight: 1.4, color: "var(--text)", marginBottom: 4, textWrap: "pretty" }}>{it[2]}</div>
              <div style={{ fontSize: 11.5, color: "var(--text-3)" }}>{it[0]} · {it[1]} ago</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PriceChartCard({ series }: { series: number[] }) {
  const { ac } = useTheme();
  return (
    <div style={card}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Price · 5D</div>
        <div style={{ display: "flex", gap: 6 }}>
          {["1D", "5D", "1M", "6M"].map((p, i) => (
            <span key={p} style={{ fontSize: 11.5, fontFamily: mono, padding: "4px 9px", borderRadius: 7, color: i === 1 ? "var(--text)" : "var(--text-3)", background: i === 1 ? "var(--surface-2)" : "transparent", border: i === 1 ? "1px solid var(--border-2)" : "1px solid transparent" }}>{p}</span>
          ))}
        </div>
      </div>
      <div style={{ marginTop: 10 }}>
        <Area data={series} color={ac.a1} w={600} h={180} />
      </div>
    </div>
  );
}

function FlowStrikes() {
  const data: [string, number, number][] = [["$200", 14, 9], ["$190", 26, 6], ["$180", 38, 8], ["$170", 22, 5], ["$160", 12, 4]];
  const max = 40;
  return (
    <div style={{ ...card, padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>Volume by strike · Jun 21 expiry</div>
        <div style={{ display: "flex", gap: 14, fontSize: 11.5 }}>
          <span style={{ color: WIN }}>● Calls</span>
          <span style={{ color: LOSS }}>● Puts</span>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 13, marginTop: 18 }}>
        {data.map((r, i) => (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 54px 1fr", alignItems: "center", gap: 10 }}>
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <div style={{ height: 18, width: (r[2] / max) * 100 + "%", borderRadius: "5px 0 0 5px", background: `linear-gradient(90deg,${LOSS}66,${LOSS})` }} />
            </div>
            <div style={{ textAlign: "center", fontFamily: mono, fontSize: 12.5, color: "var(--text-2)" }}>{r[0]}</div>
            <div>
              <div style={{ height: 18, width: (r[1] / max) * 100 + "%", borderRadius: "0 5px 5px 0", background: `linear-gradient(90deg,${WIN},${WIN}66)` }} />
            </div>
          </div>
        ))}
      </div>
      <p style={{ margin: "18px 0 0", fontSize: 13, color: "var(--text-3)", lineHeight: 1.5 }}>
        The $180 call line carries the heaviest volume and the widest call-over-put skew — the core of today&apos;s unusual activity flag.
      </p>
    </div>
  );
}

function AiAnalysis({ blocks }: { blocks: { t: string; b: string; warn?: boolean }[] }) {
  const { ac } = useTheme();
  const [regen, setRegen] = useState(false);
  return (
    <div style={{ ...card, padding: 24, position: "relative", overflow: "hidden" }}>
      {regen ? (
        <div style={{ position: "absolute", inset: 0, zIndex: 5, background: "var(--surface)", backdropFilter: "blur(2px)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 14 }}>
          <div style={{ position: "relative", width: 34, height: 34 }}>
            <span style={{ position: "absolute", inset: 0, borderRadius: "50%", border: "2px solid var(--border-2)", borderTopColor: ac.a1, animation: "spin .8s linear infinite" }} />
          </div>
          <div style={{ fontSize: 13.5, color: "var(--text-2)" }}>Claude is re-reading the tape…</div>
        </div>
      ) : null}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, flexWrap: "wrap", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 26, height: 26, borderRadius: 8, background: "linear-gradient(135deg,var(--a1),var(--a2))", display: "grid", placeItems: "center" }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "#faf6ee" }}>AI</span>
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>Claude analysis</div>
            <div style={{ fontSize: 11.5, color: "var(--text-3)" }}>Generated 6:30 AM ET · model claude</div>
          </div>
        </div>
        <button
          onClick={() => { if (regen) return; setRegen(true); setTimeout(() => setRegen(false), 1700); }}
          style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 12.5, fontWeight: 500, color: "var(--text-2)", background: "var(--surface-2)", border: "1px solid var(--border-2)", padding: "7px 13px", borderRadius: 9 }}
        >
          ↻ Regenerate
        </button>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        {blocks.map((bl, i) => (
          <div key={i} style={{ paddingLeft: 14, borderLeft: `2px solid ${bl.warn ? WARN : ac.a1}` }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 7, color: bl.warn ? WARN : "var(--text)" }}>{bl.warn ? "⚠ " + bl.t : bl.t}</div>
            <p style={{ margin: 0, fontSize: 14.5, lineHeight: 1.6, color: "var(--text-2)", textWrap: "pretty" }}>{bl.b}</p>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 20, padding: "11px 14px", borderRadius: 7, background: "var(--surface-2)", fontSize: 12, color: "var(--text-3)", lineHeight: 1.5 }}>
        VolterraAI organizes market signals and explains possible interpretations. It does not predict prices or provide financial advice.
      </div>
    </div>
  );
}

function NewsFull() {
  const col = { pos: WIN, neutral: "var(--text-3)", neg: LOSS } as const;
  const lab = { pos: "Bullish", neutral: "Neutral", neg: "Cautious" } as const;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {DEMO_NEWS_FULL.map((it, i) => (
        <div key={i} style={{ borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", padding: 20, boxShadow: "var(--shadow)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 9 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 12, color: "var(--text-3)" }}>
              <span style={{ fontWeight: 600, color: "var(--text-2)" }}>{it[0]}</span>· {it[1]} ago
            </div>
            <span style={{ fontSize: 11, fontWeight: 600, color: col[it[2]], background: (it[2] === "neutral" ? "#8b93a8" : col[it[2]]) + "1f", padding: "3px 9px", borderRadius: 7 }}>{lab[it[2]]}</span>
          </div>
          <div style={{ fontSize: 16, fontWeight: 600, letterSpacing: "-0.01em", marginBottom: 7, textWrap: "pretty" }}>{it[3]}</div>
          <p style={{ margin: 0, fontSize: 14, lineHeight: 1.55, color: "var(--text-2)", textWrap: "pretty" }}>{it[4]}</p>
        </div>
      ))}
    </div>
  );
}

function History() {
  const { ac } = useTheme();
  const max = 5;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ ...card, padding: 24 }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Unusual activity · last 8 weeks</div>
        <div style={{ fontSize: 12.5, color: "var(--text-3)", marginBottom: 20 }}>Flagged events highlighted</div>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 14, height: 140 }}>
          {DEMO_HISTORY_WEEKS.map((w, i) => (
            <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
              <div style={{ width: "100%", height: (w[1] / max) * 110, borderRadius: "6px 6px 3px 3px", background: w[2] ? `linear-gradient(180deg,${ac.a1},${ac.a2})` : "var(--surface-2)" }} />
              <div style={{ fontSize: 11, color: "var(--text-3)" }}>{w[0]}</div>
            </div>
          ))}
        </div>
      </div>
      <div style={{ ...card, padding: 8 }}>
        {DEMO_HISTORY_ROWS.map((r, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 16px", borderBottom: i < DEMO_HISTORY_ROWS.length - 1 ? "1px solid var(--border)" : "none" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <span style={{ fontFamily: mono, fontSize: 12.5, color: "var(--text-3)", width: 52 }}>{r[0]}</span>
              <span style={{ fontSize: 14, color: "var(--text)" }}>{r[1]}</span>
            </div>
            <span style={{ fontSize: 11.5, fontWeight: 500, color: r[3] ? WIN : "var(--text-3)", background: (r[3] ? WIN : "#8b93a8") + "1f", padding: "4px 10px", borderRadius: 7 }}>{r[2]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TickerPage() {
  const params = useParams<{ symbol: string }>();
  const symbol = (params.symbol || "NVDA").toUpperCase();
  const router = useRouter();
  const { flash } = useToast();
  const w = useWidth();
  const mid = w < 1180;
  const [tab, setTab] = useState<Tab>("ai");
  const [detail, setDetail] = useState<TickerDetail>({
    demo: true,
    setup: DEMO_SETUPS.find((s) => s.t === symbol) ?? DEMO_SETUPS[0],
    series: DEMO_TICKER_SERIES,
    aiBlocks: null,
    history: null,
  });

  useEffect(() => {
    let alive = true;
    // Demo mode: the landing page's "View demo setup" stashes the payload
    // from GET /api/demo/setup and links here with ?demo=1 — render exactly
    // that instead of fetching live ticker data.
    if (new URLSearchParams(window.location.search).get("demo") === "1") {
      try {
        const raw = sessionStorage.getItem("volterra-demo-setup");
        if (raw) {
          const d = JSON.parse(raw) as { setup: TickerDetail["setup"]; aiBlocks: TickerDetail["aiBlocks"] };
          setDetail({ demo: true, setup: d.setup, series: DEMO_TICKER_SERIES, aiBlocks: d.aiBlocks, history: null });
          return;
        }
      } catch {
        /* corrupt/missing stash — fall through to the normal fetch */
      }
    }
    fetchTicker(symbol).then((d) => { if (alive) setDetail(d); });
    return () => { alive = false; };
  }, [symbol]);

  const s = detail.setup;
  const tg = tagFor(s.tag);
  const up = (s.chg ?? 0) >= 0;
  const blocks = detail.aiBlocks ?? DEMO_AI_BLOCKS;

  const save = () => {
    apiSend("/api/journal", "POST", { ticker: symbol, ai_summary_id: s.summaryId ?? null });
    flash(`${symbol} saved to your journal`);
  };

  const tabs: [Tab, string][] = [["overview", "Overview"], ["flow", "Flow stats"], ["ai", "AI analysis"], ["news", "News"], ["history", "History"]];

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--text-3)", marginBottom: 18 }}>
        <span onClick={() => router.push("/scan")} style={{ cursor: "pointer" }}>Daily scan</span>
        <span>/</span>
        <span style={{ color: "var(--text-2)" }}>{symbol}</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 18, marginBottom: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div style={{ width: 54, height: 54, borderRadius: 8, background: "var(--surface-2)", border: "1px solid var(--border-2)", display: "grid", placeItems: "center", fontSize: 18, fontWeight: 700, letterSpacing: "-0.02em" }}>{symbol.slice(0, 2)}</div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
              <h1 style={{ fontSize: 28, fontWeight: 600, lineHeight: 1.1, letterSpacing: "-0.02em", margin: 0 }}>{symbol}</h1>
              <span style={{ fontSize: 12, fontWeight: 500, color: tg.c, background: tg.c + "21", padding: "4px 10px", borderRadius: 8 }}>{tg.label}</span>
            </div>
            <div style={{ fontSize: 13.5, color: "var(--text-3)", marginTop: 3 }}>{s.name === symbol ? `${symbol} · latest scan` : `${s.name} · NASDAQ`}</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 20 }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: mono, fontSize: 30, fontWeight: 600, letterSpacing: "-0.02em" }}>${s.price.toFixed(2)}</div>
            {s.chg !== null ? (
              <div style={{ fontFamily: mono, fontSize: 14, color: up ? WIN : LOSS, marginTop: 3 }}>
                {(up ? "+" : "") + ((s.price * s.chg) / 100).toFixed(2)} ({(up ? "+" : "") + s.chg.toFixed(2)}%) today
              </div>
            ) : (
              <div style={{ fontFamily: mono, fontSize: 14, color: "var(--text-3)", marginTop: 3 }}>price at last scan</div>
            )}
          </div>
          <button onClick={save} style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 13.5, fontWeight: 600, color: "#faf6ee", background: "linear-gradient(135deg,var(--a1),var(--a2))", border: "none", padding: "11px 18px", borderRadius: 7 }}>
            ＋ Save to journal
          </button>
        </div>
      </div>
      <div style={{ display: "flex", borderBottom: "1px solid var(--border)", margin: "14px 0 26px", overflowX: "auto" }}>
        {tabs.map(([k, l]) => {
          const on = tab === k;
          return (
            <button key={k} onClick={() => setTab(k)} style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 14, fontWeight: on ? 600 : 500, color: on ? "var(--text)" : "var(--text-3)", background: "transparent", border: "none", borderBottom: `2px solid ${on ? "var(--a1)" : "transparent"}`, padding: "12px 2px", marginRight: 24, transition: "color .15s" }}>
              {l}
            </button>
          );
        })}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: mid ? "1fr" : "1.55fr 1fr", gap: 20, alignItems: "start" }}>
        <div style={{ minWidth: 0 }}>
          {tab === "overview" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              <PriceChartCard series={detail.series} />
              <AiAnalysis blocks={blocks} />
            </div>
          ) : tab === "flow" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              <FlowStrikes />
              <PriceChartCard series={detail.series} />
            </div>
          ) : tab === "ai" ? (
            <AiAnalysis blocks={blocks} />
          ) : tab === "news" ? (
            <NewsFull />
          ) : (
            <History />
          )}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <MarketPanel d={detail} />
          <NewsTeaser onAll={() => setTab("news")} />
        </div>
      </div>
    </>
  );
}
