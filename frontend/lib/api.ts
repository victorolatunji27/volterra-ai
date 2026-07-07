"use client";
// API-first data layer with demo fallback.
//
// Each fetcher tries the FastAPI backend (NEXT_PUBLIC_API_URL); on any
// network error, non-2xx, or empty payload it returns the design's
// illustrative demo data with { demo: true } so callers can tell.
import {
  DEMO_SETUPS, DEMO_JOURNAL, DEMO_TICKER_SERIES, DEMO_EQUITY,
  DEMO_STRATEGY_PERF, DEMO_TICKER_PERF, DEMO_ANALYTICS_OVERVIEW,
  DEMO_AI_BLOCKS,
  Setup, JournalRow, StrategyPerf,
} from "./demo";
import { WIN, LOSS, WARN } from "@/components/theme";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TIMEOUT_MS = 4000;

async function apiGet<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_URL}${path}`, {
      signal: AbortSignal.timeout(TIMEOUT_MS),
      headers: authHeaders(),
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function apiSend(path: string, method: string, body?: unknown): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method,
      signal: AbortSignal.timeout(TIMEOUT_MS),
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    return res.ok;
  } catch {
    return false;
  }
}

function authHeaders(): Record<string, string> {
  // Supabase session wiring lands with real auth; until then a token may be
  // planted in localStorage for testing against a live backend.
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("volterra-token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ---------------------------------------------------------------------------
// Scans
// ---------------------------------------------------------------------------

interface ApiScan {
  id: number;
  ticker: string;
  call_volume: number | null;
  put_volume: number | null;
  oi_ratio: number | null;
  call_put_ratio: number | null;
  avg_strike: number | null;
  avg_expiry: string | null;
  iv_rank: number | null;
  price_at_scan: number | null;
  summary: {
    id: number;
    setup_summary: string | null;
    risk_note: string | null;
    flow_interpretation: string | null;
    strategy_tags: string[] | null;
  } | null;
}

function fmtExpiry(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  return isNaN(d.getTime()) ? "—" : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function scanToSetup(s: ApiScan, i: number): Setup {
  const price = s.price_at_scan ?? 0;
  return {
    rank: i + 1,
    t: s.ticker,
    name: s.ticker,
    tag: s.summary?.strategy_tags?.[0] ?? "neutral",
    price,
    chg: null, // day-change % has no backend field yet
    cp: s.call_put_ratio ?? 0,
    oi: s.oi_ratio ?? 0,
    iv: Math.round(s.iv_rank ?? 0),
    avg: Math.round(s.avg_strike ?? 0),
    exp: fmtExpiry(s.avg_expiry),
    score: Math.min(99, Math.round((s.oi_ratio ?? 0) * 20)),
    bull: (s.call_put_ratio ?? 1) >= 1,
    spark: [],
    sum: s.summary?.setup_summary ?? "AI summary pending for this scan.",
    risk: s.summary?.risk_note ?? "No risk note generated yet.",
    summaryId: s.summary?.id,
  };
}

export async function fetchSetups(): Promise<{ setups: Setup[]; demo: boolean; empty: boolean }> {
  const data = await apiGet<ApiScan[]>("/api/scans/today");
  // Unreachable API → illustrative demo data. A reachable API returning []
  // (weekend, scan not yet run) → genuine empty state.
  if (data === null) return { setups: DEMO_SETUPS, demo: true, empty: false };
  if (data.length === 0) return { setups: [], demo: false, empty: true };
  return { setups: data.map(scanToSetup), demo: false, empty: false };
}

// ---------------------------------------------------------------------------
// Ticker detail
// ---------------------------------------------------------------------------

export interface TickerDetail {
  demo: boolean;
  setup: Setup;
  series: number[];
  aiBlocks: { t: string; b: string; warn?: boolean }[] | null;
  history: { scan_date: string; oi_ratio: number | null; call_put_ratio: number | null; iv_rank: number | null; price_at_scan: number | null }[] | null;
}

interface ApiTickerDetail {
  symbol: string;
  latest: ApiScan;
  news: unknown;
  history: TickerDetail["history"];
  price_series: { date: string; close: number }[] | null;
}

export async function fetchTicker(symbol: string): Promise<TickerDetail> {
  const data = await apiGet<ApiTickerDetail>(`/api/ticker/${symbol}`);
  if (data) {
    const setup = scanToSetup(data.latest, 0);
    const series = data.price_series?.map((p) => p.close) ?? DEMO_TICKER_SERIES;
    const aiBlocks = data.latest.summary
      ? [
          { t: "Flow interpretation", b: data.latest.summary.flow_interpretation ?? "" },
          { t: "Setup summary", b: data.latest.summary.setup_summary ?? "" },
          { t: "Risk factors", warn: true, b: data.latest.summary.risk_note ?? "" },
        ]
      : null;
    return { demo: false, setup, series, aiBlocks, history: data.history };
  }
  const fallback = DEMO_SETUPS.find((s) => s.t === symbol.toUpperCase()) ?? DEMO_SETUPS[0];
  return { demo: true, setup: fallback, series: DEMO_TICKER_SERIES, aiBlocks: null, history: null };
}

// ---------------------------------------------------------------------------
// Demo setup (landing page "View demo setup")
// ---------------------------------------------------------------------------

export interface DemoSetupDetail {
  setup: Setup;
  aiBlocks: { t: string; b: string; warn?: boolean }[];
}

interface ApiDemoSetup {
  is_demo: boolean;
  ticker: string;
  company_name: string;
  strategy_tag: string;
  call_put_ratio: number;
  oi_ratio: number;
  iv_rank: number;
  price_at_scan: number;
  price_change_pct: number;
  avg_strike: number;
  expiry: string;
  setup_summary: string;
  flow_interpretation: string;
  risk_note: string;
}

/** Fetch the server's illustrative setup; fall back to the local demo data. */
export async function fetchDemoSetup(): Promise<DemoSetupDetail> {
  const d = await apiGet<ApiDemoSetup>("/api/demo/setup");
  if (d) {
    return {
      setup: {
        rank: 1,
        t: d.ticker,
        name: d.company_name,
        tag: d.strategy_tag,
        price: d.price_at_scan,
        chg: d.price_change_pct,
        cp: d.call_put_ratio,
        oi: d.oi_ratio,
        iv: Math.round(d.iv_rank),
        avg: Math.round(d.avg_strike),
        exp: fmtExpiry(d.expiry),
        score: Math.min(99, Math.round(d.oi_ratio * 20)),
        bull: d.call_put_ratio >= 1,
        spark: DEMO_SETUPS[0].spark,
        sum: d.setup_summary,
        risk: d.risk_note,
      },
      aiBlocks: [
        { t: "Flow interpretation", b: d.flow_interpretation },
        { t: "Setup summary", b: d.setup_summary },
        { t: "Risk factors", warn: true, b: d.risk_note },
      ],
    };
  }
  return { setup: DEMO_SETUPS[0], aiBlocks: DEMO_AI_BLOCKS };
}

// ---------------------------------------------------------------------------
// Journal
// ---------------------------------------------------------------------------

interface ApiJournalEntry {
  id: number;
  ticker: string;
  entry_price: number | null;
  strategy_type: string | null;
  expiry_date: string | null;
  outcome: string | null;
  outcome_pnl_pct: number | null;
  user_notes: string | null;
}

const STRAT_LABEL: Record<string, string> = {
  momentum: "Momentum", earnings_play: "Earnings Play", breakout: "Breakout",
  hedge: "Hedge", iv_crush: "IV Crush", contrarian: "Contrarian", neutral: "Neutral",
};

export async function fetchJournal(): Promise<{ rows: JournalRow[]; demo: boolean; empty: boolean }> {
  const data = await apiGet<ApiJournalEntry[]>("/api/journal?limit=100");
  // Unreachable/unauthenticated → demo rows; reachable-but-empty → empty state.
  if (data === null) return { rows: DEMO_JOURNAL, demo: true, empty: false };
  if (data.length === 0) return { rows: [], demo: false, empty: true };
  const rows = data.map((e): JournalRow => ({
    id: e.id,
    t: e.ticker,
    strat: STRAT_LABEL[e.strategy_type ?? ""] ?? "Momentum",
    entry: e.entry_price ?? 0,
    exp: fmtExpiry(e.expiry_date),
    status: e.outcome === "win" ? "Win" : e.outcome === "loss" ? "Loss" : e.outcome === "scratch" ? "Scratch" : "Pending",
    pnl: e.outcome_pnl_pct ?? 0,
    note: e.user_notes ?? "",
  }));
  return { rows, demo: false, empty: false };
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export interface AnalyticsData {
  demo: boolean;
  overview: typeof DEMO_ANALYTICS_OVERVIEW;
  equity: number[];
  strategyPerf: StrategyPerf[];
  tickerPerf: [string, number][];
}

const STRAT_COLOR: Record<string, string> = {
  Momentum: WIN, "Earnings Play": "#8b7bff", Breakout: "#33d6ea",
  "IV Crush": WARN, Hedge: "#8b93a8", Contrarian: "#ff6bd6", Neutral: "#8b93a8",
};

export async function fetchAnalytics(): Promise<AnalyticsData> {
  const [summary, byStrategy, byTicker, curve] = await Promise.all([
    apiGet<{ total_trades: number; resolved_trades: number; win_rate: number; avg_pnl_pct: number; best_setup: { ticker: string; pnl_pct: number } | null }>("/api/analytics/summary"),
    apiGet<{ strategy_type: string; trade_count: number; win_rate: number }[]>("/api/analytics/by-strategy"),
    apiGet<{ ticker: string; trade_count: number; win_rate: number }[]>("/api/analytics/by-ticker"),
    apiGet<{ date: string; cumulative_pnl_pct: number }[]>("/api/analytics/equity-curve"),
  ]);
  if (summary && summary.resolved_trades > 0) {
    return {
      demo: false,
      overview: {
        ...DEMO_ANALYTICS_OVERVIEW,
        totalTrades: String(summary.total_trades),
        totalSub: `${summary.resolved_trades} resolved`,
        winRate: `${summary.win_rate}%`,
        winSub: "of resolved trades",
        avgPnl: `${summary.avg_pnl_pct >= 0 ? "+" : ""}${summary.avg_pnl_pct}%`,
        avgSub: "per closed trade",
        bestSetup: summary.best_setup ? `+${summary.best_setup.pnl_pct}%` : "—",
        bestSub: summary.best_setup?.ticker ?? "no wins yet",
        overallWin: `${summary.win_rate}%`,
      },
      equity: curve && curve.length > 1 ? curve.map((p) => p.cumulative_pnl_pct) : DEMO_EQUITY,
      strategyPerf: byStrategy && byStrategy.length > 0
        ? byStrategy.map((s) => ({
            n: STRAT_LABEL[s.strategy_type] ?? s.strategy_type,
            t: s.trade_count,
            w: Math.round(s.win_rate),
            c: STRAT_COLOR[STRAT_LABEL[s.strategy_type] ?? s.strategy_type] ?? WIN,
          }))
        : DEMO_STRATEGY_PERF,
      tickerPerf: byTicker && byTicker.length > 0
        ? byTicker.slice(0, 5).map((t): [string, number] => [t.ticker, t.win_rate])
        : DEMO_TICKER_PERF,
    };
  }
  return {
    demo: true,
    overview: DEMO_ANALYTICS_OVERVIEW,
    equity: DEMO_EQUITY,
    strategyPerf: DEMO_STRATEGY_PERF,
    tickerPerf: DEMO_TICKER_PERF,
  };
}

// ---------------------------------------------------------------------------
// Strategy preferences
// ---------------------------------------------------------------------------

const CHIP_TO_API: Record<string, string> = {
  Momentum: "momentum", "Earnings Play": "earnings_play", Breakout: "breakout",
  "IV Crush": "iv_crush", Hedge: "hedge", Contrarian: "contrarian", Neutral: "neutral",
};

export async function saveStrategyPrefs(chips: string[]): Promise<boolean> {
  const strategy_tags = chips.map((c) => CHIP_TO_API[c]).filter(Boolean);
  return apiSend("/api/users/me/strategies", "PATCH", { strategy_tags });
}

export { LOSS, WIN, WARN };
