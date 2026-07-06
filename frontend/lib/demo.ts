// Illustrative demo data, lifted verbatim from the design prototype
// (VolterraAI.dc.html). Used whenever the backend is unreachable or returns
// nothing — the landing footer already discloses "Data shown is illustrative".

export interface Setup {
  rank: number;
  t: string;
  name: string;
  tag: string;
  price: number;
  chg: number | null;
  cp: number;
  oi: number;
  iv: number;
  avg: number;
  exp: string;
  score: number;
  bull: boolean;
  spark: number[];
  sum: string;
  risk: string;
  summaryId?: number;
}

export const DEMO_SETUPS: Setup[] = [
  { rank: 1, t: "NVDA", name: "NVIDIA Corp.", tag: "momentum", price: 172.4, chg: 2.4, cp: 2.8, oi: 4.1, iv: 61, avg: 180, exp: "Jun 21", score: 96, bull: true,
    spark: [20, 22, 21, 24, 28, 27, 31, 34, 33, 38, 42, 46],
    sum: "Heavy call buying concentrated in near-dated $180 strikes ahead of the GTC keynote. Volume is running 4× open interest, suggesting fresh positioning rather than rolls.",
    risk: "IV is elevated — a post-event vol crush could erase gains even if the stock moves up." },
  { rank: 2, t: "TSLA", name: "Tesla, Inc.", tag: "earnings_play", price: 248.21, chg: 1.3, cp: 2.1, oi: 1.9, iv: 62, avg: 260, exp: "Jun 28", score: 91, bull: true,
    spark: [30, 28, 31, 29, 33, 31, 35, 38, 36, 40, 39, 43],
    sum: "Weekly call sweeps clustering above spot into the delivery print. Skew is flattening as buyers reach for upside convexity.",
    risk: "Binary event risk — a soft delivery number unwinds the call premium quickly." },
  { rank: 3, t: "AMD", name: "Advanced Micro Devices", tag: "breakout", price: 148.9, chg: 3.1, cp: 2.5, oi: 2.2, iv: 57, avg: 155, exp: "Jul 19", score: 88, bull: true,
    spark: [18, 19, 22, 21, 25, 29, 28, 33, 37, 36, 41, 45],
    sum: "Call open interest building at the $155 breakout level with steady accumulation over three sessions — looks like a positioning campaign, not a single block.",
    risk: "Needs a clean break of $150 resistance; below it the thesis stalls and theta bleeds." },
  { rank: 4, t: "META", name: "Meta Platforms, Inc.", tag: "momentum", price: 502.31, chg: 0.9, cp: 1.9, oi: 1.6, iv: 48, avg: 520, exp: "Jul 19", score: 82, bull: true,
    spark: [40, 41, 39, 42, 44, 43, 46, 45, 48, 47, 50, 52],
    sum: "Steady call accumulation in monthly $520 strikes alongside positive ad-spend commentary. Flow reads as trend-following, not speculative.",
    risk: "Valuation is stretched; any macro wobble compresses multiples fast." },
  { rank: 5, t: "SPY", name: "S&P 500 ETF", tag: "hedge", price: 598.1, chg: -0.4, cp: 0.6, oi: 2.2, iv: 38, avg: 585, exp: "Jun 30", score: 74, bull: false,
    spark: [52, 51, 53, 50, 49, 51, 48, 49, 47, 48, 46, 45],
    sum: "Put volume outpacing calls nearly 2:1, weighted toward month-end expiries. The pattern reads as portfolio hedging rather than directional bearish bets.",
    risk: "Hedging flow is noisy — it signals caution, not a clean short setup." },
];

export interface JournalRow {
  id?: number;
  t: string;
  strat: string;
  entry: number;
  exp: string;
  status: "Win" | "Loss" | "Scratch" | "Pending";
  pnl: number;
  note: string;
}

export const DEMO_JOURNAL: JournalRow[] = [
  { t: "NVDA", strat: "Momentum", entry: 165.2, exp: "Jun 21", status: "Win", pnl: 24.5, note: "Sized in on the keynote run-up, trimmed half into strength." },
  { t: "TSLA", strat: "Earnings Play", entry: 241.0, exp: "May 31", status: "Loss", pnl: -12.3, note: "Delivery miss; vol crush hit before the move." },
  { t: "AMD", strat: "Breakout", entry: 142.1, exp: "Jul 19", status: "Pending", pnl: 6.4, note: "Holding for the $155 break." },
  { t: "AAPL", strat: "Momentum", entry: 214.5, exp: "Jun 14", status: "Win", pnl: 18.7, note: "WWDC follow-through played out." },
  { t: "AMZN", strat: "Breakout", entry: 186.4, exp: "Jun 28", status: "Pending", pnl: -1.2, note: "Chop near entry, watching volume." },
  { t: "QQQ", strat: "Hedge", entry: 512.0, exp: "May 24", status: "Scratch", pnl: 0.3, note: "Closed flat, macro never materialized." },
];

export const DEMO_TICKER_SERIES = [150, 152, 151, 154, 158, 156, 160, 159, 163, 168, 166, 170, 169, 171, 170, 172.4];

export const DEMO_EQUITY = [100, 104, 102, 108, 112, 109, 116, 122, 119, 128, 134, 131, 140, 148, 145, 156, 162];

export interface StrategyPerf { n: string; t: number; w: number; c: string }
export const DEMO_STRATEGY_PERF: StrategyPerf[] = [
  { n: "Momentum", t: 18, w: 65, c: "#3c8a5f" },
  { n: "Earnings Play", t: 9, w: 58, c: "#8b7bff" },
  { n: "Breakout", t: 11, w: 52, c: "#33d6ea" },
  { n: "IV Crush", t: 5, w: 48, c: "#bd8330" },
  { n: "Hedge", t: 4, w: 50, c: "#8b93a8" },
];

export const DEMO_TICKER_PERF: [string, number][] = [
  ["NVDA", 24.5], ["AAPL", 18.7], ["AMD", 12.1], ["AMZN", -1.2], ["TSLA", -12.3],
];

export const DEMO_ANALYTICS_OVERVIEW = {
  totalTrades: "47", totalSub: "+6 this month", totalSpark: [30, 32, 35, 38, 40, 44, 47],
  winRate: "61.7%", winSub: "+3.2 pts vs Q1", winSpark: [52, 54, 53, 57, 59, 60, 62],
  avgPnl: "+8.42%", avgSub: "per closed trade", avgSpark: [4, 6, 5, 7, 8, 8, 8.4],
  bestSetup: "+36.2%", bestSub: "NVDA · momentum", bestSpark: [10, 16, 20, 26, 30, 34, 36],
  overallWin: "61.7%",
  equityPct: "+62.0%", equityBalance: "$16,200 balance",
};

export const DEMO_NEWS_TEASER: [string, string, string][] = [
  ["Reuters", "2h", "NVIDIA unveils next-gen Rubin platform at GTC"],
  ["Bloomberg", "5h", "Hyperscaler capex lifts AI chip demand outlook"],
  ["WSJ", "1d", "Options desks flag elevated gamma into expiry"],
];

export const DEMO_NEWS_FULL: [string, string, "pos" | "neutral" | "neg", string, string][] = [
  ["Reuters", "2h", "pos", "NVIDIA unveils next-gen Rubin platform at GTC", "The new accelerator targets ~3× training throughput and deeper memory bandwidth, reinforcing the data-center upgrade cycle narrative."],
  ["Bloomberg", "5h", "pos", "Hyperscaler capex guidance lifts AI chip demand outlook", "Three major cloud providers raised full-year infrastructure spend, with commentary pointing to sustained accelerator orders."],
  ["WSJ", "1d", "neutral", "Options desks flag elevated NVDA gamma into expiry", "Dealers note positioning that could amplify intraday moves as Jun 21 approaches."],
  ["CNBC", "1d", "neg", "Analyst trims target on valuation, keeps buy", "One sell-side desk cited a stretched multiple while maintaining a constructive long-term view."],
];

export const DEMO_AI_BLOCKS: { t: string; b: string; warn?: boolean }[] = [
  { t: "Flow interpretation", b: "The dominant signal is fresh call buying in the $180 strike expiring Jun 21. Volume printed roughly 4× the resting open interest, and time-and-sales shows repeated sweeps lifting the offer — a footprint that reads as new directional positioning rather than rolls or covered-call writing." },
  { t: "Why this setup surfaced", b: "VolterraAI ranked NVDA #1 because three of its anomaly inputs spiked at once: call/put volume ratio (2.8), the volume-to-open-interest multiple (4.1×), and a near-dated catalyst window around the GTC keynote. When those align on a liquid large-cap, the unusual-activity score clears the daily threshold." },
  { t: "Risk factors", warn: true, b: "IV rank sits at 61 — elevated. If the keynote fails to deliver a surprise, a post-event volatility crush can compress these calls even on a flat-to-up move in the stock. Crowded positioning also raises the odds of a sharp unwind if momentum stalls below $175." },
];

export const DEMO_HISTORY_WEEKS: [string, number, number][] = [
  ["Apr", 2, 0], ["Apr", 1, 0], ["May", 3, 1], ["May", 1, 0], ["May", 4, 1], ["Jun", 2, 1], ["Jun", 5, 1], ["Jun", 3, 1],
];
export const DEMO_HISTORY_ROWS: [string, string, string, boolean][] = [
  ["Jun 14", "Call sweep · $180", "Momentum", true],
  ["Jun 7", "Put accumulation · $160", "Hedge", false],
  ["May 24", "Call sweep · $170", "Breakout", true],
  ["May 10", "Block trade · $175", "Momentum", true],
];
