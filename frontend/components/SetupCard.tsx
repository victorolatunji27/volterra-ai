"use client";
// Ranked setup card — the core unit of the daily scan, ported from setupCards().
import React from "react";
import { useRouter } from "next/navigation";
import { WIN, LOSS, WARN } from "@/components/theme";
import { Spark } from "@/components/charts";
import { useToast } from "@/components/toast";
import { tagFor } from "@/lib/tags";
import { apiSend } from "@/lib/api";
import type { Setup } from "@/lib/demo";

const mono = "var(--mono)";

function Stat({ lab, val }: { lab: string; val: string }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>{lab}</div>
      <div style={{ fontFamily: mono, fontSize: 15, fontWeight: 500 }}>{val}</div>
    </div>
  );
}

export default function SetupCard({ s }: { s: Setup }) {
  const router = useRouter();
  const { flash } = useToast();
  const tg = tagFor(s.tag);
  const up = (s.chg ?? 0) >= 0;

  const save = async () => {
    // Best-effort API save; the toast fires either way (demo parity).
    apiSend("/api/journal", "POST", { ticker: s.t, ai_summary_id: s.summaryId ?? null });
    flash(`${s.t} saved to your journal`);
  };

  return (
    <div style={{ position: "relative", borderRadius: 9, border: "1px solid var(--border)", background: "var(--surface)", backdropFilter: "var(--glass-blur)", WebkitBackdropFilter: "var(--glass-blur)", boxShadow: "var(--shadow)", padding: 24, overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: tg.c, opacity: 0.85 }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 13 }}>
          <div style={{ width: 30, height: 30, borderRadius: 9, display: "grid", placeItems: "center", background: "var(--surface-2)", border: "1px solid var(--border)", fontFamily: mono, fontSize: 13, fontWeight: 600, color: "var(--text-3)" }}>{s.rank}</div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 19, fontWeight: 600, letterSpacing: "-0.01em" }}>{s.t}</span>
              <span style={{ fontSize: 11.5, fontWeight: 500, color: tg.c, background: tg.c + "1f", padding: "3px 9px", borderRadius: 7, textTransform: "capitalize" }}>{tg.label}</span>
            </div>
            <div style={{ fontSize: 12.5, color: "var(--text-3)", marginTop: 3 }}>{s.name}</div>
          </div>
        </div>
        <div style={{ textAlign: "right", display: "flex", alignItems: "center", gap: 14 }}>
          {s.spark.length > 1 ? <Spark data={s.spark} color={up ? WIN : LOSS} w={84} h={30} /> : null}
          <div>
            <div style={{ fontFamily: mono, fontSize: 18, fontWeight: 600 }}>${s.price.toFixed(2)}</div>
            {s.chg !== null ? (
              <div style={{ fontFamily: mono, fontSize: 13, fontWeight: 500, color: up ? WIN : LOSS, marginTop: 2 }}>{(up ? "+" : "") + s.chg}%</div>
            ) : null}
          </div>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6,1fr)", gap: 12, margin: "20px 0", padding: "16px 0", borderTop: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}>
        <Stat lab="C/P ratio" val={s.cp.toFixed(1)} />
        <Stat lab="OI ratio" val={s.oi.toFixed(1)} />
        <Stat lab="IV rank" val={String(s.iv)} />
        <Stat lab="Price" val={"$" + s.price.toFixed(0)} />
        <Stat lab="Avg strike" val={"$" + s.avg} />
        <Stat lab="Expiry" val={s.exp} />
      </div>
      <div style={{ display: "flex", gap: 10, marginBottom: 14, alignItems: "flex-start" }}>
        <div style={{ flexShrink: 0, width: 24, height: 24, borderRadius: 7, background: "linear-gradient(135deg,var(--a1),var(--a2))", display: "grid", placeItems: "center", marginTop: 1 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: "#faf6ee" }}>AI</span>
        </div>
        <p style={{ margin: 0, fontSize: 14.5, lineHeight: 1.55, color: "var(--text)", textWrap: "pretty" }}>{s.sum}</p>
      </div>
      <div style={{ display: "flex", gap: 9, alignItems: "flex-start", padding: "11px 13px", borderRadius: 7, background: WARN + "14", border: "1px solid " + WARN + "2a", marginBottom: 18 }}>
        <span style={{ color: WARN, fontSize: 13, marginTop: 1 }}>⚠</span>
        <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.5, color: "var(--text-2)" }}>
          <b style={{ color: "var(--text)", fontWeight: 600 }}>Risk note. </b>
          {s.risk}
        </p>
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        <button onClick={() => router.push(`/ticker/${s.t}`)} style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 13.5, fontWeight: 600, color: "#faf6ee", background: "linear-gradient(135deg,var(--a1),var(--a2))", border: "none", padding: "10px 18px", borderRadius: 7, whiteSpace: "nowrap" }}>
          View details
        </button>
        <button onClick={save} style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 13.5, fontWeight: 500, color: "var(--text)", background: "var(--surface-2)", border: "1px solid var(--border-2)", padding: "10px 18px", borderRadius: 7, display: "inline-flex", alignItems: "center", gap: 7, whiteSpace: "nowrap" }}>
          <span style={{ fontSize: 15, lineHeight: 1 }}>＋</span>Save to journal
        </button>
      </div>
    </div>
  );
}
