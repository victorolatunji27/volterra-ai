"use client";
// Landing page — ported from the design's isLanding section.
import React from "react";
import { useRouter } from "next/navigation";
import { ThemeControls, useTheme, WIN, LOSS } from "@/components/theme";
import { Spark } from "@/components/charts";
import { ICONS, svgIcon, playIcon } from "@/components/icons";
import { useWidth } from "@/lib/useWidth";
import { TAGS } from "@/lib/tags";
import { fetchDemoSetup } from "@/lib/api";

const mono = "var(--mono)";

function HeroCard() {
  const { ac } = useTheme();
  const tg = TAGS.momentum;
  const stat = (lab: string, val: string) => (
    <div key={lab}>
      <div style={{ fontSize: 10.5, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 4 }}>{lab}</div>
      <div style={{ fontFamily: mono, fontSize: 14, fontWeight: 500 }}>{val}</div>
    </div>
  );
  return (
    <div style={{ position: "relative", borderRadius: 9, border: "1px solid var(--border-2)", background: "var(--surface-2)", backdropFilter: "var(--glass-blur)", WebkitBackdropFilter: "var(--glass-blur)", boxShadow: "0 30px 70px -28px rgba(0,0,0,0.6)", padding: 26, overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: tg.c }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 22, fontWeight: 600 }}>NVDA</span>
            <span style={{ fontSize: 11.5, fontWeight: 500, color: tg.c, background: tg.c + "1f", padding: "3px 9px", borderRadius: 7 }}>momentum</span>
          </div>
          <div style={{ fontSize: 12.5, color: "var(--text-3)", marginTop: 3 }}>NVIDIA Corp.</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontFamily: mono, fontSize: 18, fontWeight: 600 }}>$172.40</div>
          <div style={{ fontFamily: mono, fontSize: 13, color: WIN, marginTop: 2 }}>+2.4%</div>
        </div>
      </div>
      <div style={{ margin: "18px 0" }}>
        <Spark data={[20, 22, 21, 24, 28, 27, 31, 34, 33, 38, 42, 46]} color={ac.a1} w={460} h={46} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, padding: "15px 0", borderTop: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}>
        {stat("C/P ratio", "2.8")}
        {stat("IV rank", "61")}
        {stat("Expiry", "Jun 21")}
      </div>
      <div style={{ display: "flex", gap: 10, marginTop: 16, alignItems: "flex-start" }}>
        <div style={{ flexShrink: 0, width: 22, height: 22, borderRadius: 7, background: "linear-gradient(135deg,var(--a1),var(--a2))", display: "grid", placeItems: "center" }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: "#faf6ee" }}>AI</span>
        </div>
        <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.5, color: "var(--text)" }}>
          Heavy call accumulation at $180 ahead of the GTC keynote — volume running 4× open interest.
        </p>
      </div>
    </div>
  );
}

function Tape() {
  const items: [string, string, number][] = [
    ["NVDA", "+2.4", 1], ["TSLA", "+1.3", 1], ["AMD", "+3.1", 1], ["META", "+0.9", 1], ["SPY", "-0.4", 0],
    ["AAPL", "+1.1", 1], ["AMZN", "-0.6", 0], ["QQQ", "+0.7", 1], ["GOOGL", "+1.8", 1], ["MSFT", "+0.5", 1],
  ];
  const one = (k: string) =>
    items.map(([t, c, up], i) => (
      <div key={k + i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "0 22px", borderRight: "1px solid var(--border)" }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{t}</span>
        <span style={{ fontFamily: mono, fontSize: 12.5, color: up ? WIN : LOSS }}>{c}%</span>
      </div>
    ));
  return <>{one("a")}{one("b")}</>;
}

function Features() {
  const { ac } = useTheme();
  const fs = [
    { ic: ICONS.scan, t: "Unusual flow detection", d: "Every weekday morning we surface the 10 tickers with the most anomalous options volume relative to open interest." },
    { ic: ICONS.analytics, t: "Claude reads the tape", d: "Market data and news catalysts go in; a plain-English setup, reasoning, and risk note come out — never a price prediction." },
    { ic: ICONS.journal, t: "Track your own calls", d: "Save setups to a journal, resolve them as wins or losses, and let analytics show what is actually working for you." },
  ];
  return (
    <>
      {fs.map((f, i) => (
        <div key={i} style={{ padding: 24, borderRadius: 9, border: "1px solid var(--border)", background: "var(--surface)", backdropFilter: "var(--glass-blur)", WebkitBackdropFilter: "var(--glass-blur)" }}>
          <div style={{ width: 42, height: 42, borderRadius: 7, display: "grid", placeItems: "center", background: "var(--a1-soft)", color: ac.a1, marginBottom: 16 }}>{svgIcon(f.ic, 22)}</div>
          <h3 style={{ margin: "0 0 9px", fontSize: 17, fontWeight: 600, letterSpacing: "-0.01em" }}>{f.t}</h3>
          <p style={{ margin: 0, fontSize: 14.5, lineHeight: 1.55, color: "var(--text-2)" }}>{f.d}</p>
        </div>
      ))}
    </>
  );
}

function FlowViz() {
  const bars: [string, number, number][] = [
    ["NVDA", 96, 1], ["TSLA", 91, 1], ["AMD", 88, 1], ["META", 82, 1], ["AVGO", 79, 1],
    ["SPY", 74, 0], ["AMZN", 70, 0], ["QQQ", 66, 1], ["AAPL", 61, 1], ["GOOGL", 55, 1],
  ];
  const max = 100;
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 10, height: 240, padding: "0 2px" }}>
      {bars.map(([t, v, up]) => (
        <div key={t} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 9 }}>
          <div style={{ fontFamily: mono, fontSize: 11, color: "var(--text-3)" }}>{v}</div>
          <div style={{ width: "100%", height: (v / max) * 180, borderRadius: "7px 7px 3px 3px", background: up ? `linear-gradient(180deg,${WIN},${WIN}99)` : `linear-gradient(180deg,${LOSS},${LOSS}88)`, transition: "height .5s ease" }} />
          <div style={{ fontSize: 10.5, color: "var(--text-3)", transform: "rotate(-32deg)", transformOrigin: "center", whiteSpace: "nowrap", marginTop: 4 }}>{t}</div>
        </div>
      ))}
    </div>
  );
}

export default function Landing() {
  const router = useRouter();
  const w = useWidth();
  const narrow = w < 900;
  const startTrial = () => router.push("/auth?mode=signup");
  const viewDemo = async () => {
    // Fetch the server's illustrative setup (public endpoint; local demo
    // fallback when the API is down), stash it, and open the ticker page in
    // demo mode so it renders exactly this payload.
    const demo = await fetchDemoSetup();
    try {
      sessionStorage.setItem("volterra-demo-setup", JSON.stringify(demo));
    } catch {
      /* sessionStorage unavailable — ticker page falls back on its own */
    }
    router.push(`/ticker/${demo.setup.t}?demo=1`);
  };

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: "0 28px" }}>
      {/* NAV */}
      <nav style={{ display: "flex", alignItems: "center", justifyContent: "space-between", height: 78 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="vm-light" src="/assets/volterra-logo.png" alt="Volterra" style={{ height: 30, width: "auto", display: "block" }} />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="vm-dark" src="/assets/volterra-logo-reversed.png" alt="Volterra" style={{ height: 30, width: "auto", display: "block" }} />
          <span style={{ fontFamily: "var(--sans)", fontSize: 14, fontWeight: 700, letterSpacing: "0.04em", color: "var(--a1)", alignSelf: "center" }}>AI</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <ThemeControls />
          <button onClick={() => router.push("/auth")} style={{ cursor: "pointer", border: "none", fontFamily: "inherit", fontSize: 14, fontWeight: 600, color: "#faf6ee", background: "var(--a1)", padding: "10px 18px", borderRadius: 6, boxShadow: "0 10px 26px -12px var(--a1)", whiteSpace: "nowrap" }}>
            Open app
          </button>
        </div>
      </nav>

      {/* HERO */}
      <header style={{ display: "grid", gridTemplateColumns: narrow ? "1fr" : "1.05fr 0.95fr", gap: 48, alignItems: "center", padding: "48px 0 40px" }}>
        <div>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 13px", borderRadius: 999, border: "1px solid var(--border)", background: "var(--surface)", fontSize: 12.5, color: "var(--text-2)", marginBottom: 24, whiteSpace: "nowrap" }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--a3)" }} />
            Today&apos;s scan is live · 10 setups ranked
          </div>
          <h1 style={{ fontSize: narrow ? 42 : 58, lineHeight: 1.0, letterSpacing: "-0.02em", fontWeight: 500, margin: "0 0 22px" }}>
            See the options flow<br /><em style={{ fontStyle: "italic", fontWeight: 500 }}>before</em> the crowd.
          </h1>
          <p style={{ fontSize: 18, lineHeight: 1.6, color: "var(--text-2)", maxWidth: 520, margin: "0 0 32px" }}>
            VolterraAI scans the options market every weekday morning, detects unusual activity, and uses Claude to turn raw flow into plain-English setups.{" "}
            <span style={{ color: "var(--text)" }}>No predictions. No advice. Just signal, organized.</span>
          </p>
          <div style={{ display: "flex", gap: 13, flexWrap: "wrap", alignItems: "center" }}>
            <button onClick={startTrial} style={{ cursor: "pointer", border: "none", fontFamily: "inherit", fontSize: 15, fontWeight: 600, color: "#faf6ee", background: "linear-gradient(135deg,var(--a1),var(--a2))", padding: "14px 24px", borderRadius: 7, boxShadow: "0 16px 36px -14px var(--a1)" }}>
              Start free trial
            </button>
            <button onClick={viewDemo} style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 15, fontWeight: 500, color: "var(--text)", background: "var(--surface)", border: "1px solid var(--border-2)", padding: "14px 22px", borderRadius: 7, display: "inline-flex", alignItems: "center", gap: 9 }}>
              {playIcon} View demo setup
            </button>
          </div>
          <div style={{ display: "flex", gap: 30, marginTop: 42, flexWrap: "wrap" }}>
            <div>
              <div style={{ fontFamily: mono, fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em" }}>10+</div>
              <div style={{ fontSize: 13, color: "var(--text-3)", marginTop: 3 }}>setups scanned daily</div>
            </div>
            <div style={{ width: 1, background: "var(--border)" }} />
            <div>
              <div style={{ fontFamily: mono, fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em", color: "var(--a1)" }}>Claude</div>
              <div style={{ fontSize: 13, color: "var(--text-3)", marginTop: 3 }}>AI-generated analysis</div>
            </div>
            <div style={{ width: 1, background: "var(--border)" }} />
            <div>
              <div style={{ fontFamily: mono, fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em" }}>100%</div>
              <div style={{ fontSize: 13, color: "var(--text-3)", marginTop: 3 }}>your decisions, tracked</div>
            </div>
          </div>
        </div>

        {/* HERO CARD STACK */}
        <div style={{ position: "relative" }}>
          <div style={{ position: "absolute", inset: "-40px -20px", background: "radial-gradient(closest-side,var(--a1-soft),transparent)", filter: "blur(20px)" }} />
          <div style={{ position: "absolute", top: -26, right: 6, zIndex: 3, display: "flex", alignItems: "center", gap: 9, padding: "9px 14px", borderRadius: 7, background: "var(--surface-2)", backdropFilter: "var(--glass-blur)", WebkitBackdropFilter: "var(--glass-blur)", border: "1px solid var(--border-2)", boxShadow: "var(--shadow)", animation: "floaty 5s ease-in-out infinite" }}>
            <div style={{ position: "relative", width: 22, height: 22, display: "grid", placeItems: "center" }}>
              <span style={{ position: "absolute", inset: 0, borderRadius: "50%", background: "var(--a1)", animation: "ringPulse 2.2s ease-out infinite" }} />
              <span style={{ width: 9, height: 9, borderRadius: "50%", background: "var(--a1)", position: "relative" }} />
            </div>
            <span style={{ fontSize: 12.5, color: "var(--text-2)" }}>Claude is analyzing flow…</span>
          </div>
          <HeroCard />
        </div>
      </header>

      {/* TICKER TAPE */}
      <div style={{ margin: "26px 0 70px", borderTop: "1px solid var(--border)", borderBottom: "1px solid var(--border)", overflow: "hidden", position: "relative", WebkitMaskImage: "linear-gradient(90deg,transparent,#000 8%,#000 92%,transparent)", maskImage: "linear-gradient(90deg,transparent,#000 8%,#000 92%,transparent)" }}>
        <div style={{ display: "flex", gap: 0, width: "max-content", animation: "marquee 34s linear infinite", padding: "14px 0" }}>
          <Tape />
        </div>
      </div>

      {/* FEATURE TRIO */}
      <section style={{ display: "grid", gridTemplateColumns: narrow ? "1fr" : "repeat(3,1fr)", gap: 18, paddingBottom: 64 }}>
        <Features />
      </section>

      {/* BIG VIZ STRIP */}
      <section style={{ position: "relative", borderRadius: 9, border: "1px solid var(--border)", background: "var(--surface)", backdropFilter: "var(--glass-blur)", WebkitBackdropFilter: "var(--glass-blur)", overflow: "hidden", padding: 44, marginBottom: 80, boxShadow: "var(--shadow)" }}>
        <div style={{ position: "absolute", inset: 0, background: "var(--bg-grad)", opacity: 0.6 }} />
        <div style={{ position: "relative", display: "grid", gridTemplateColumns: narrow ? "1fr" : "0.9fr 1.1fr", gap: 44, alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 12, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--a2)", fontWeight: 600, marginBottom: 14 }}>Market activity, visualized</div>
            <h2 style={{ fontSize: 34, lineHeight: 1.1, letterSpacing: "-0.03em", fontWeight: 600, margin: "0 0 16px" }}>Where the unusual volume is concentrating — right now.</h2>
            <p style={{ fontSize: 16, lineHeight: 1.6, color: "var(--text-2)", margin: "0 0 26px" }}>
              Every bar is a ticker&apos;s call vs. put pressure weighted by how far volume runs past open interest. The taller and greener, the more aggressive the positioning.
            </p>
            <button onClick={startTrial} style={{ cursor: "pointer", border: "none", fontFamily: "inherit", fontSize: 14, fontWeight: 600, color: "var(--text)", background: "var(--surface-2)", borderStyle: "solid", borderWidth: 1, borderColor: "var(--border-2)", padding: "12px 20px", borderRadius: 7, whiteSpace: "nowrap" }}>
              Explore today&apos;s board →
            </button>
          </div>
          <FlowViz />
        </div>
      </section>

      {/* FOOTER CTA */}
      <section style={{ textAlign: "center", padding: "30px 0 90px" }}>
        <h2 style={{ fontSize: 40, lineHeight: 1.04, letterSpacing: "-0.035em", fontWeight: 600, margin: "0 0 14px" }}>Options flow. AI insight. Your edge.</h2>
        <p style={{ fontSize: 17, color: "var(--text-2)", margin: "0 0 30px" }}>Start free. Your first scan is waiting.</p>
        <button onClick={startTrial} style={{ cursor: "pointer", border: "none", fontFamily: "inherit", fontSize: 16, fontWeight: 600, color: "#faf6ee", background: "linear-gradient(135deg,var(--a1),var(--a2))", padding: "16px 30px", borderRadius: 8, boxShadow: "0 18px 40px -14px var(--a1)" }}>
          Start free trial
        </button>
        <div style={{ marginTop: 64, paddingTop: 26, borderTop: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 16, color: "var(--text-3)", fontSize: 13 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/assets/volterra-icon.png" alt="" style={{ width: 24, height: 24, borderRadius: 7, display: "block" }} />
            VolterraAI
          </div>
          <div>Not financial advice · For research &amp; education · Data shown is illustrative</div>
        </div>
      </section>
    </div>
  );
}
