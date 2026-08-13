"use client";
// Settings — account card + appearance (theme and accent direction).
// The account card reads live tier/email/member-since from /api/users/me,
// keeping the design's illustrative values in demo mode.
import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ACCENTS, AccentKey, useTheme } from "@/components/theme";
import { Sk } from "@/components/Skeleton";
import { useToast } from "@/components/toast";
import { displayName, planLabel } from "@/lib/account";
import { fetchMe, invalidateMe, Me } from "@/lib/api";
import { PAYWALL_ENABLED } from "@/lib/flags";
import { resetAnalytics } from "@/lib/posthog";
import { getSupabase } from "@/lib/supabase";
import { useWidth } from "@/lib/useWidth";

const mono = "var(--mono)";
const card: React.CSSProperties = { borderRadius: 9, border: "1px solid var(--border)", background: "var(--surface)", padding: 24, boxShadow: "var(--shadow)" };

// Illustrative account (design values) shown in demo mode / unauthenticated.
const DEMO_ACCOUNT = {
  name: "Alex Rivera",
  subtitle: "Pro plan · active",
  rows: [
    ["Email", "alex.rivera@gmail.com"],
    ["Subscription tier", "Pro · $29/mo"],
    ["Member since", "March 2025"],
    ["Next billing", "Jul 1, 2026"],
  ] as [string, string][],
};

function accountFromMe(me: Me) {
  const isPro = me.tier === "pro";
  const created = Date.parse(me.created_at);
  const memberSince = Number.isFinite(created)
    ? new Date(created).toLocaleDateString("en-US", { month: "long", year: "numeric" })
    : "—";
  return {
    // Shared with the sidebar so the two can't drift (lib/account.ts).
    name: displayName(me.email),
    subtitle: isPro ? `${planLabel(me.tier)} · active` : planLabel(me.tier),
    rows: [
      ["Email", me.email],
      // No billing fields on the backend yet — the price is display copy.
      ["Subscription tier", isPro ? "Pro · $29/mo" : "Free"],
      ["Member since", memberSince],
      ["Next billing", isPro ? "Jul 1, 2026" : "—"],
    ] as [string, string][],
  };
}

const ACCENT_LABELS: [AccentKey, string][] = [["aurora", "Ember"], ["oceanic", "Pine"], ["cosmic", "Aubergine"]];

export default function SettingsPage() {
  const router = useRouter();
  const { theme, accent, setTheme, setAccent } = useTheme();
  const { flash } = useToast();
  const w = useWidth();
  const narrow = w < 900;
  const [account, setAccount] = useState(DEMO_ACCOUNT);
  const [accountLoading, setAccountLoading] = useState(true);

  const signOut = async () => {
    const supabase = getSupabase();
    if (supabase) await supabase.auth.signOut();
    // Drop cached identity so the next user doesn't inherit this one's
    // profile or analytics attribution.
    invalidateMe();
    resetAnalytics();
    flash("Signed out");
    router.push("/");
  };

  useEffect(() => {
    let alive = true;
    fetchMe()
      .then((me) => {
        if (alive && me) setAccount(accountFromMe(me));
      })
      .finally(() => {
        if (alive) setAccountLoading(false);
      });
    return () => { alive = false; };
  }, []);

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 30, fontWeight: 600, lineHeight: 1.12, letterSpacing: "-0.03em", margin: "0 0 6px", whiteSpace: "nowrap" }}>Settings</h1>
        <p style={{ fontSize: 15.5, color: "var(--text-2)", margin: 0 }}>Manage your account, billing, and how VolterraAI looks.</p>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: narrow ? "1fr" : "1fr 1fr", gap: 18, alignItems: "start" }}>
        {/* Account — #billing is the PaywallGate "Upgrade to Pro" target */}
        <div id="billing" style={card}>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 18 }}>Account</div>
          {accountLoading ? (
            /* Shape-matched skeleton: avatar row + four detail rows. */
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 14, paddingBottom: 20, marginBottom: 6, borderBottom: "1px solid var(--border)" }}>
                <Sk h={48} w={48} r={24} />
                <div style={{ flex: 1 }}>
                  <Sk h={15} w="45%" style={{ marginBottom: 8 }} />
                  <Sk h={12} w="35%" />
                </div>
              </div>
              {[0, 1, 2, 3].map((i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "13px 0", borderTop: i > 0 ? "1px solid var(--border)" : "none" }}>
                  <Sk h={13} w="30%" />
                  <Sk h={13} w="40%" />
                </div>
              ))}
            </>
          ) : (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 14, paddingBottom: 20, marginBottom: 6, borderBottom: "1px solid var(--border)" }}>
                <div style={{ width: 48, height: 48, borderRadius: "50%", background: "linear-gradient(135deg,var(--a1),var(--a3))", display: "grid", placeItems: "center", fontSize: 18, fontWeight: 600, color: "#faf6ee" }}>
                  {account.name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 600 }}>{account.name}</div>
                  <div style={{ fontSize: 13, color: "var(--text-3)" }}>{account.subtitle}</div>
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column" }}>
                {account.rows.map((r, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "13px 0", borderTop: i > 0 ? "1px solid var(--border)" : "none" }}>
                    <span style={{ fontSize: 13.5, color: "var(--text-3)" }}>{r[0]}</span>
                    <span style={{ fontSize: 13.5, fontWeight: 500, fontFamily: r[1].indexOf("@") > 0 || /\d/.test(r[1]) ? mono : "inherit" }}>{r[1]}</span>
                  </div>
                ))}
              </div>
            </>
          )}
          <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
            {/* No billing integration on the free-tier launch — showing a
                "Manage subscription" button would promise a portal that
                doesn't exist. Returns when PAYWALL_ENABLED flips on. */}
            {PAYWALL_ENABLED ? (
              <button onClick={() => flash("Billing portal opened")} style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 13.5, fontWeight: 600, color: "#faf6ee", background: "linear-gradient(135deg,var(--a1),var(--a2))", border: "none", padding: "10px 18px", borderRadius: 7 }}>
                Manage subscription
              </button>
            ) : null}
            <button onClick={signOut} style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 13.5, fontWeight: 500, color: "var(--text-2)", background: "var(--surface-2)", border: "1px solid var(--border-2)", padding: "10px 18px", borderRadius: 7 }}>
              Sign out
            </button>
          </div>
        </div>

        {/* Appearance */}
        <div style={card}>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 18 }}>Appearance</div>
          <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 10 }}>Theme</div>
          <div style={{ display: "flex", gap: 8, marginBottom: 22 }}>
            {([["dark", "Dark"], ["light", "Light"]] as const).map(([k, l]) => {
              const on = theme === k;
              return (
                <button key={k} onClick={() => setTheme(k)} style={{ cursor: "pointer", flex: 1, fontFamily: "inherit", fontSize: 13.5, fontWeight: on ? 600 : 500, color: on ? "var(--text)" : "var(--text-3)", background: on ? "var(--surface-2)" : "transparent", border: "1px solid " + (on ? "var(--border-2)" : "var(--border)"), padding: 11, borderRadius: 7 }}>
                  {l}
                </button>
              );
            })}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 10 }}>Accent direction</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
            {ACCENT_LABELS.map(([k, l]) => {
              const on = accent === k;
              const a = ACCENTS[k];
              return (
                <button key={k} onClick={() => setAccent(k)} style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 12, fontFamily: "inherit", fontSize: 14, fontWeight: 500, color: "var(--text)", textAlign: "left", background: on ? "var(--a1-soft)" : "var(--surface-2)", border: "1px solid " + (on ? "var(--border-2)" : "var(--border)"), padding: "11px 14px", borderRadius: 7 }}>
                  <span style={{ width: 34, height: 18, borderRadius: 6, background: `linear-gradient(135deg,${a.a1},${a.a2},${a.a3})` }} />
                  {l}
                  {on ? <span style={{ marginLeft: "auto", color: "var(--a1)", fontSize: 14 }}>✓</span> : null}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}
