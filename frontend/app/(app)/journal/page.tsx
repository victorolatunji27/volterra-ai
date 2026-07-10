"use client";
// Trade journal — stats, outcome filters, expandable rows table.
import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTheme, WIN, LOSS } from "@/components/theme";
import { useToast } from "@/components/toast";
import { ICONS, svgIcon } from "@/components/icons";
import EmptyState, { BookmarkIcon } from "@/components/EmptyState";
import { fetchJournal, apiSend } from "@/lib/api";
import { track } from "@/lib/posthog";
import { DEMO_JOURNAL, JournalRow } from "@/lib/demo";
import { useWidth } from "@/lib/useWidth";

const mono = "var(--mono)";
const FILTERS = ["All", "Win", "Loss", "Scratch", "Pending"] as const;

const TAG_COLOR: Record<string, string> = {
  Momentum: WIN, "Earnings Play": "#8b7bff", Breakout: "#33d6ea",
  Hedge: "#8b93a8", "IV Crush": "#bd8330", Contrarian: "#ff6bd6", Neutral: "#8b93a8",
};

export default function JournalPage() {
  const router = useRouter();
  const { ac } = useTheme();
  const { flash } = useToast();
  const w = useWidth();
  const narrow = w < 900;
  const [rows, setRows] = useState<JournalRow[]>(DEMO_JOURNAL);
  const [journalEmpty, setJournalEmpty] = useState(false);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("All");
  const [open, setOpen] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    fetchJournal().then((r) => {
      if (!alive) return;
      setRows(r.rows);
      setJournalEmpty(r.empty);
    });
    return () => { alive = false; };
  }, []);

  const SC: Record<string, string> = { Win: WIN, Loss: LOSS, Scratch: "var(--text-3)", Pending: ac.a1 };
  const data = filter === "All" ? rows : rows.filter((d) => d.status === filter);
  const cols = "1.1fr 1fr 0.85fr 0.85fr 0.9fr 0.85fr 34px";

  const resolved = rows.filter((r) => r.status !== "Pending");
  const wins = resolved.filter((r) => r.status === "Win").length;
  const winRate = resolved.length ? ((wins / resolved.length) * 100).toFixed(1) + "%" : "—";
  const net = rows.reduce((s, r) => s + (r.status !== "Pending" ? r.pnl : 0), 0);
  const best = rows.reduce<JournalRow | null>((b, r) => (r.status === "Win" && (!b || r.pnl > b.pnl) ? r : b), null);
  const stats: [string, string, string, string][] = [
    ["Open positions", String(rows.filter((r) => r.status === "Pending").length), "watching", ac.a1],
    ["Realized win rate", winRate, `${wins} of ${resolved.length} closed`, WIN],
    ["Net realized", (net >= 0 ? "+" : "") + net.toFixed(1) + "%", "this quarter", WIN],
    ["Best trade", best ? `+${best.pnl}%` : "—", best ? `${best.t} · ${best.strat}` : "no wins yet", WIN],
  ];

  const resolveTrade = (d: JournalRow) => {
    if (d.id) {
      apiSend(`/api/journal/${d.id}`, "PATCH", { outcome: "win", outcome_pnl_pct: d.pnl }).then(
        (ok) => { if (ok) track("outcome_marked", { ticker: d.t, outcome: "win", pnl_pct: d.pnl }); }
      );
    }
    flash(`${d.t} marked resolved`);
  };

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 14, marginBottom: 24 }}>
        <div style={{ flexShrink: 0 }}>
          <h1 style={{ fontSize: 30, fontWeight: 600, lineHeight: 1.12, letterSpacing: "-0.03em", margin: "0 0 6px", whiteSpace: "nowrap" }}>Trade journal</h1>
          <p style={{ fontSize: 15.5, color: "var(--text-2)", margin: 0 }}>Track your decisions and resolve them honestly. Your edge is in the review.</p>
        </div>
        <button onClick={() => flash("New trade added to your journal")} style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 13.5, fontWeight: 600, color: "#faf6ee", background: "linear-gradient(135deg,var(--a1),var(--a2))", border: "none", padding: "11px 18px", borderRadius: 7, whiteSpace: "nowrap" }}>
          ＋ Add trade
        </button>
      </div>

      {journalEmpty ? (
        /* Nothing saved yet — reachable API returned an empty journal. */
        <EmptyState
          icon={<BookmarkIcon />}
          heading="No trades saved yet"
          body="When you save a setup from the daily scan, it appears here."
          actionLabel="Go to today's scan"
          onAction={() => router.push("/scan")}
        />
      ) : (
      <>
      <div style={{ display: "grid", gridTemplateColumns: narrow ? "repeat(2,1fr)" : "repeat(4,1fr)", gap: 14, marginBottom: 24 }}>
        {stats.map((s, i) => (
          <div key={i} style={{ padding: "16px 18px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", boxShadow: "var(--shadow)" }}>
            <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 8 }}>{s[0]}</div>
            <div style={{ fontFamily: mono, fontSize: 22, fontWeight: 600, color: s[1].startsWith("+") ? s[3] : "var(--text)", whiteSpace: "nowrap" }}>{s[1]}</div>
            <div style={{ fontSize: 11.5, color: "var(--text-3)", marginTop: 6 }}>{s[2]}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {FILTERS.map((f) => {
          const on = filter === f;
          return (
            <button key={f} onClick={() => { setFilter(f); setOpen(null); }} style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 13, fontWeight: on ? 600 : 500, color: on ? "var(--text)" : "var(--text-3)", background: on ? "var(--surface-2)" : "transparent", border: "1px solid " + (on ? "var(--border-2)" : "transparent"), padding: "7px 14px", borderRadius: 9 }}>
              {f}
            </button>
          );
        })}
      </div>

      {data.length === 0 ? (
        <div style={{ padding: "56px 20px", textAlign: "center", borderRadius: 9, border: "1px dashed var(--border-2)", background: "var(--surface)" }}>
          <div style={{ width: 46, height: 46, borderRadius: 8, background: "var(--surface-2)", display: "grid", placeItems: "center", margin: "0 auto 16px", color: "var(--text-3)" }}>{svgIcon(ICONS.journal, 24)}</div>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>No {filter.toLowerCase()} trades yet</div>
          <div style={{ fontSize: 13.5, color: "var(--text-3)" }}>Resolve a position or save a setup from the daily scan to see it here.</div>
        </div>
      ) : (
        <div style={{ borderRadius: 9, border: "1px solid var(--border)", background: "var(--surface)", boxShadow: "var(--shadow)", overflow: "hidden" }}>
          <div style={{ display: "grid", gridTemplateColumns: cols, gap: 12, padding: "13px 20px", borderBottom: "1px solid var(--border)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-3)" }}>
            {["Ticker", "Strategy", "Entry", "Expiry", "Status", "P&L", ""].map((c, i) => (
              <div key={i} style={{ textAlign: i >= 2 && i < 6 ? "right" : "left" }}>{c}</div>
            ))}
          </div>
          {data.map((d, i) => {
            const isOpen = open === i;
            const tagC = TAG_COLOR[d.strat] ?? WIN;
            return (
              <div key={i} style={{ borderBottom: i < data.length - 1 || isOpen ? "1px solid var(--border)" : "none" }}>
                <div onClick={() => setOpen(isOpen ? null : i)} style={{ cursor: "pointer", display: "grid", gridTemplateColumns: cols, gap: 12, padding: "15px 20px", alignItems: "center", transition: "background .15s", background: isOpen ? "var(--surface-2)" : "transparent" }}>
                  <div style={{ fontWeight: 600, fontSize: 14.5 }}>{d.t}</div>
                  <div>
                    <span style={{ fontSize: 11.5, fontWeight: 500, color: tagC, background: tagC + "1f", padding: "3px 9px", borderRadius: 7, whiteSpace: "nowrap" }}>{d.strat}</span>
                  </div>
                  <div style={{ textAlign: "right", fontFamily: mono, fontSize: 13.5, color: "var(--text-2)" }}>${d.entry.toFixed(2)}</div>
                  <div style={{ textAlign: "right", fontFamily: mono, fontSize: 13.5, color: "var(--text-3)" }}>{d.exp}</div>
                  <div style={{ textAlign: "right" }}>
                    <span style={{ fontSize: 11.5, fontWeight: 600, color: SC[d.status], background: (d.status === "Pending" ? ac.a1 : d.status === "Win" ? WIN : d.status === "Loss" ? LOSS : "#8b93a8") + "1f", padding: "4px 10px", borderRadius: 7 }}>{d.status}</span>
                  </div>
                  <div style={{ textAlign: "right", fontFamily: mono, fontSize: 14, fontWeight: 600, color: d.pnl > 0 ? WIN : d.pnl < 0 ? LOSS : "var(--text-3)" }}>{(d.pnl > 0 ? "+" : "") + d.pnl}%</div>
                  <div style={{ textAlign: "right", color: "var(--text-3)", transform: isOpen ? "rotate(180deg)" : "none", transition: "transform .2s" }}>⌄</div>
                </div>
                {isOpen ? (
                  <div style={{ padding: "4px 20px 18px" }}>
                    <div style={{ padding: "14px 16px", borderRadius: 7, background: "var(--surface-2)", border: "1px solid var(--border)" }}>
                      <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-3)", marginBottom: 7 }}>Note</div>
                      <p style={{ margin: 0, fontSize: 14, lineHeight: 1.55, color: "var(--text-2)" }}>{d.note || "No note yet."}</p>
                      <div style={{ display: "flex", gap: 9, marginTop: 16 }}>
                        <button onClick={(e) => { e.stopPropagation(); flash(`${d.t} note updated`); }} style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 12.5, fontWeight: 500, color: "var(--text)", background: "var(--surface)", border: "1px solid var(--border-2)", padding: "8px 14px", borderRadius: 9 }}>
                          Edit note
                        </button>
                        <button onClick={(e) => { e.stopPropagation(); resolveTrade(d); }} style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 12.5, fontWeight: 600, color: "#faf6ee", background: "linear-gradient(135deg,var(--a1),var(--a2))", border: "none", padding: "8px 14px", borderRadius: 9 }}>
                          Resolve trade
                        </button>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
      </>
      )}
    </>
  );
}
