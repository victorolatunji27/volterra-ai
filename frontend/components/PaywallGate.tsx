"use client";
// Soft paywall for Pro-only features.
//
// Gates the wrapped content when the current user is on the free tier and
// their 30-day trial window has ended (created_at from /api/users/me).
// Ungated in demo mode / when unauthenticated (fetchMe returns null).
// "Maybe later" hides the gate for the browser session only
// (sessionStorage), never permanently.
import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchMe } from "@/lib/api";
import { track } from "@/lib/posthog";

const DISMISS_PREFIX = "vt-paywall-dismissed:";
const TRIAL_DAYS = 30;

export default function PaywallGate({
  feature,
  children,
}: {
  feature: string;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [gated, setGated] = useState(false);

  useEffect(() => {
    let alive = true;
    try {
      if (sessionStorage.getItem(DISMISS_PREFIX + feature) === "1") return;
    } catch {
      /* sessionStorage unavailable — fall through to the tier check */
    }
    fetchMe().then((me) => {
      if (!alive || !me || me.tier !== "free") return;
      const created = Date.parse(me.created_at);
      const trialEnded =
        Number.isFinite(created) &&
        Date.now() - created > TRIAL_DAYS * 24 * 60 * 60 * 1000;
      if (trialEnded) {
        setGated(true);
        track("upgrade_prompt_shown", { feature });
      }
    });
    return () => {
      alive = false;
    };
  }, [feature]);

  const dismiss = () => {
    try {
      sessionStorage.setItem(DISMISS_PREFIX + feature, "1");
    } catch {}
    setGated(false);
  };

  if (!gated) return <>{children}</>;

  return (
    <div style={{ position: "relative", minHeight: 240 }}>
      {/* Dimmed + blurred content behind the gate */}
      <div style={{ filter: "blur(4px)", opacity: 0.55, pointerEvents: "none", userSelect: "none" }} aria-hidden>
        {children}
      </div>
      <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", zIndex: 5 }}>
        <div style={{ maxWidth: 340, width: "calc(100% - 32px)", textAlign: "center", padding: "26px 24px", borderRadius: 9, border: "1px solid var(--border-2)", background: "var(--surface-2)", boxShadow: "var(--shadow)" }}>
          <h3 style={{ fontFamily: "var(--serif)", fontSize: 20, fontWeight: 600, letterSpacing: "-0.01em", margin: "0 0 8px", color: "var(--text)" }}>
            This is a Pro feature
          </h3>
          <p style={{ fontSize: 13.5, lineHeight: 1.5, color: "var(--text-2)", margin: "0 0 18px" }}>
            The {feature} is available on the Pro plan.
          </p>
          <button
            onClick={() => router.push("/settings#billing")}
            style={{ cursor: "pointer", fontFamily: "inherit", fontSize: 13.5, fontWeight: 600, color: "#faf6ee", background: "linear-gradient(135deg,var(--a1),var(--a2))", border: "none", padding: "10px 20px", borderRadius: 7 }}
          >
            Upgrade to Pro
          </button>
          <div style={{ marginTop: 12 }}>
            <button
              onClick={dismiss}
              style={{ cursor: "pointer", background: "none", border: "none", fontFamily: "inherit", fontSize: 12.5, fontWeight: 500, color: "var(--text-3)", padding: 0 }}
            >
              Maybe later
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
