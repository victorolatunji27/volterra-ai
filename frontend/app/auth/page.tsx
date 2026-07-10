"use client";
// Auth — ported from the design's uploads/files/10-auth.html
// (sign in / sign up / reset password as modes of one split-panel layout).
//
// Wired to Supabase when NEXT_PUBLIC_SUPABASE_URL/ANON_KEY are set; otherwise
// runs in demo mode where flows simulate success. Sign-in honours ?next=
// (set by middleware.ts when an unauthenticated user hits a protected route).
import React, { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { LOSS } from "@/components/theme";
import { useToast } from "@/components/toast";
import { fetchMe, invalidateMe } from "@/lib/api";
import { identifyUser } from "@/lib/posthog";
import { getSupabase } from "@/lib/supabase";

const mono = "var(--mono)";
type Mode = "signin" | "signup" | "reset";

function Logo({ size = 30 }: { size?: number }) {
  return (
    <>
      <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
        <rect x={30} y={30} width={40} height={40} rx={9} fill="var(--a1)" />
        <path d="M52 40 L44 54 H50 L48 62 L58 46 H52 L54 40 Z" fill="#faf6ee" />
      </svg>
      <span style={{ fontWeight: 700, fontSize: 19, letterSpacing: "-0.01em" }}>Volterra</span>
      <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.04em", color: "var(--a1)" }}>AI</span>
    </>
  );
}

function PreviewCard({ mode }: { mode: Mode }) {
  const isSignup = mode === "signup";
  const stat = (lab: string, val: string) => (
    <div key={lab}>
      <span style={{ display: "block", fontFamily: mono, fontSize: 10, letterSpacing: "0.06em", color: "var(--text-3)", textTransform: "uppercase" }}>{lab}</span>
      <b style={{ fontFamily: mono, fontSize: 14, fontWeight: 600 }}>{val}</b>
    </div>
  );
  return (
    <div style={{ marginTop: 34, background: "var(--surface-2)", border: "1px solid var(--border-2)", borderRadius: 10, boxShadow: "var(--shadow)", padding: "16px 18px", maxWidth: 400 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <div>
          <span style={{ fontFamily: "var(--serif)", fontSize: 19, fontWeight: 600 }}>{isSignup ? "TSLA" : "NVDA"}</span>
          <span style={{ fontSize: 11, padding: "2px 9px", borderRadius: 6, marginLeft: 9, ...(isSignup ? { background: "rgba(125,51,80,0.14)", color: "#7d3350" } : { background: "rgba(63,125,92,0.16)", color: "#2f6b4a" }) }}>
            {isSignup ? "earnings play" : "momentum"}
          </span>
        </div>
        <span style={{ fontFamily: mono, fontSize: 16, fontWeight: 600 }}>{isSignup ? "$248.21" : "$172.40"}</span>
      </div>
      <div style={{ display: "flex", gap: 22, margin: "12px 0 10px" }}>
        {isSignup ? [stat("C/P", "2.1"), stat("OI", "1.9"), stat("IV", "62")] : [stat("C/P", "2.8"), stat("OI", "4.1"), stat("IV", "61")]}
      </div>
      <div style={{ fontSize: 13, lineHeight: 1.5, color: "var(--text-2)" }}>
        {isSignup ? "Weekly call sweeps clustering above spot into the delivery print." : "Heavy call buying at $180 ahead of the GTC keynote — volume running 4x open interest."}
      </div>
    </div>
  );
}

const COPY: Record<Mode, { tag: string; h2: React.ReactNode; p: string; h1: string; sub: string }> = {
  signin: {
    tag: "Sign in",
    h2: <>See the options flow <em>before</em> the crowd.</>,
    p: "Every weekday morning, VolterraAI scans the options market, detects unusual activity, and turns raw flow into plain-English setups.",
    h1: "Welcome back",
    sub: "Sign in to see today's ranked setups.",
  },
  signup: {
    tag: "Sign up",
    h2: <>Your first scan is <em>waiting</em>.</>,
    p: "Start free. Get the daily ranked scan, an AI read on every setup, and a journal that tracks what actually works for you.",
    h1: "Start your free trial",
    sub: "Seven days of the full product. No card required.",
  },
  reset: {
    tag: "Reset password",
    h2: <>Back in, <em>quickly</em>.</>,
    p: "Enter the email on your account and we'll send a link to set a new password. The link expires in one hour.",
    h1: "Reset your password",
    sub: "We'll email you a secure reset link.",
  },
};

const label: React.CSSProperties = { display: "block", fontFamily: mono, fontSize: 11, letterSpacing: "0.07em", textTransform: "uppercase", color: "var(--text-3)", margin: "0 0 7px" };
const inputStyle: React.CSSProperties = { width: "100%", fontFamily: "var(--sans)", fontSize: 14.5, color: "var(--text)", background: "var(--surface-solid)", border: "1px solid var(--border-2)", borderRadius: 8, padding: "12px 13px" };
const btn: React.CSSProperties = { width: "100%", cursor: "pointer", border: "none", fontFamily: "inherit", fontSize: 15, fontWeight: 600, color: "#faf6ee", background: "linear-gradient(135deg,var(--a1),var(--a2))", padding: 13, borderRadius: 8, boxShadow: "0 16px 36px -16px var(--a1)" };
const btnGhost: React.CSSProperties = { width: "100%", cursor: "pointer", fontFamily: "inherit", fontSize: 14.5, fontWeight: 500, color: "var(--text)", background: "var(--surface)", border: "1px solid var(--border-2)", padding: 12, borderRadius: 8, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 9 };
const linkStyle: React.CSSProperties = { color: "var(--a1)", fontSize: 13, textDecoration: "none", fontWeight: 500, cursor: "pointer", background: "none", border: "none", fontFamily: "inherit", padding: 0 };

const successBlock: React.CSSProperties = { display: "flex", gap: 11, background: "rgba(63,125,92,0.12)", border: "1px solid rgba(63,125,92,0.3)", borderRadius: 9, padding: "13px 15px", fontSize: 13.5, color: "#2f6b4a", lineHeight: 1.5, marginBottom: 22 };

function SuccessCheck() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="#2f6b4a" strokeWidth={2} style={{ flexShrink: 0, marginTop: 1 }}>
      <path d="M20 6L9 17l-5-5" />
    </svg>
  );
}

function AuthInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { flash } = useToast();
  const [mode, setModeState] = useState<Mode>(params.get("mode") === "signup" ? "signup" : "signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resetSent, setResetSent] = useState(false);
  const [signupDone, setSignupDone] = useState(false);
  const copy = COPY[mode];

  // Where to land after sign-in: the middleware sets ?next={path} when an
  // unauthenticated user hits a protected route. Same-origin paths only.
  const rawNext = params.get("next");
  const nextPath = rawNext && rawNext.startsWith("/") && !rawNext.startsWith("//") ? rawNext : "/scan";

  const setMode = (m: Mode) => {
    setModeState(m);
    setError(null);
    setResetSent(false);
    setSignupDone(false);
  };

  const submit = async () => {
    if (busy) return;
    setError(null);
    const supabase = getSupabase();

    if (mode === "signin") {
      if (!supabase) {
        // Demo mode — no Supabase project configured.
        flash("Signed in (demo)");
        router.push(nextPath);
        return;
      }
      setBusy(true);
      const { data, error: err } = await supabase.auth.signInWithPassword({ email, password });
      setBusy(false);
      if (err) {
        setError(err.message);
        return;
      }
      if (data.user) {
        // Identify immediately with what Supabase gives us, then enrich with
        // the tier from /api/users/me without blocking navigation.
        const user = data.user;
        identifyUser(user.id, { email: user.email });
        invalidateMe();
        fetchMe().then((me) => {
          if (me) identifyUser(user.id, { email: me.email, tier: me.tier });
        });
      }
      router.push(nextPath);
      return;
    }

    if (mode === "signup") {
      if (!supabase) {
        setSignupDone(true);
        return;
      }
      setBusy(true);
      const { error: err } = await supabase.auth.signUp({ email, password });
      setBusy(false);
      if (err) {
        setError(err.message);
        return;
      }
      // No redirect, no form clear — just swap the submit area for the notice.
      setSignupDone(true);
      return;
    }

    // reset
    if (supabase) {
      setBusy(true);
      // Deliberately ignore errors: the confirmation copy is noncommittal so
      // the form can't be used to probe which emails have accounts.
      await supabase.auth.resetPasswordForEmail(email).catch(() => undefined);
      setBusy(false);
    }
    setResetSent(true);
  };

  return (
    <section style={{ minHeight: "100vh", display: "grid", gridTemplateColumns: "1.05fr 1fr", alignItems: "stretch", position: "relative" }} className="auth-frame">
      <style>{`@media(max-width:880px){.auth-frame{grid-template-columns:1fr !important}.auth-brand{display:none !important}.auth-card-logo{display:flex !important;margin-bottom:28px}}`}</style>
      <div style={{ position: "absolute", top: 22, left: 22, zIndex: 5, display: "inline-flex", alignItems: "center", gap: 7, padding: "5px 12px", borderRadius: 999, border: "1px solid var(--border)", background: "var(--surface)", fontSize: 12, color: "var(--text-2)" }}>
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--a3)" }} /> {copy.tag}
      </div>

      {/* brand panel */}
      <div className="auth-brand" style={{ position: "relative", overflow: "hidden", padding: "56px 52px", display: "flex", flexDirection: "column", justifyContent: "space-between", borderRight: "1px solid var(--border)" }}>
        <div style={{ position: "absolute", top: -120, right: -120, width: 420, height: 420, background: "radial-gradient(closest-side,var(--a1-soft),transparent)", filter: "blur(8px)" }} />
        <div style={{ display: "flex", alignItems: "center", gap: 9, position: "relative", zIndex: 2 }}>
          <Logo />
        </div>
        <div style={{ position: "relative", zIndex: 2, maxWidth: 440 }}>
          <h2 style={{ fontSize: 44, letterSpacing: "-0.02em", margin: 0 }}>{copy.h2}</h2>
          <p style={{ fontSize: 16, lineHeight: 1.6, color: "var(--text-2)", margin: "20px 0 0" }}>{copy.p}</p>
          {mode !== "reset" ? <PreviewCard mode={mode} /> : null}
        </div>
        <div style={{ position: "relative", zIndex: 2, fontFamily: mono, fontSize: 11, letterSpacing: "0.04em", color: "var(--text-3)" }}>
          NOT FINANCIAL ADVICE · FOR RESEARCH &amp; EDUCATION
        </div>
      </div>

      {/* form panel */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "48px 32px" }}>
        <div style={{ width: "100%", maxWidth: 384 }}>
          <div className="auth-card-logo" style={{ display: "none", alignItems: "center", gap: 9 }}>
            <Logo size={28} />
          </div>
          <h1 style={{ fontSize: 30, letterSpacing: "-0.01em", margin: 0 }}>{copy.h1}</h1>
          <p style={{ fontSize: 14.5, color: "var(--text-2)", margin: "9px 0 28px", lineHeight: 1.5 }}>{copy.sub}</p>

          {mode === "reset" && resetSent ? (
            /* Reset confirmation — replaces the form entirely. */
            <>
              <div style={successBlock}>
                <SuccessCheck />
                <div>If an account exists for that email, a reset link is on its way. Check your inbox.</div>
              </div>
              <div style={{ marginTop: 24, fontSize: 13.5, color: "var(--text-2)", textAlign: "center" }}>
                <button style={linkStyle} onClick={() => setMode("signin")}>← Back to sign in</button>
              </div>
            </>
          ) : (
            <>
              <div style={{ marginBottom: 16 }}>
                <label style={label} htmlFor="auth-email">Email</label>
                <input id="auth-email" type="email" placeholder="you@email.com" style={inputStyle} value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              {mode !== "reset" ? (
                <div style={{ marginBottom: 16 }}>
                  <label style={label} htmlFor="auth-pw">Password</label>
                  <input id="auth-pw" type="password" placeholder={mode === "signup" ? "At least 8 characters" : "••••••••"} style={inputStyle} value={password} onChange={(e) => setPassword(e.target.value)} />
                </div>
              ) : null}

              {mode === "signin" ? (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", margin: "-4px 0 20px" }}>
                  <span />
                  <button style={linkStyle} onClick={() => setMode("reset")}>Forgot password?</button>
                </div>
              ) : null}

              {error ? (
                <div style={{ fontSize: 13, color: LOSS, lineHeight: 1.45, margin: "0 0 14px" }}>{error}</div>
              ) : null}

              {mode === "signup" && signupDone ? (
                /* Sign-up confirmation — replaces the submit button area only. */
                <div style={{ ...successBlock, marginBottom: 0 }}>
                  <SuccessCheck />
                  <div>Check your inbox to confirm your email before signing in.</div>
                </div>
              ) : (
                <button style={{ ...btn, opacity: busy ? 0.7 : 1 }} onClick={submit} disabled={busy}>
                  {busy ? "…" : mode === "signin" ? "Sign in" : mode === "signup" ? "Create account" : "Send reset link"}
                </button>
              )}

              {mode === "signin" ? (
                <>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "18px 0", color: "var(--text-3)", fontSize: 12 }}>
                    <span style={{ flex: 1, height: 1, background: "var(--border)" }} />or<span style={{ flex: 1, height: 1, background: "var(--border)" }} />
                  </div>
                  <button style={btnGhost} onClick={() => flash("Google sign-in coming soon")}>
                    <svg width={16} height={16} viewBox="0 0 24 24" aria-hidden="true">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z" />
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z" />
                      <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88z" />
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.06l3.66 2.84C6.71 7.3 9.14 5.38 12 5.38z" />
                    </svg>
                    Continue with Google
                  </button>
                </>
              ) : null}

              {mode === "signup" && !signupDone ? (
                <p style={{ fontSize: 12.5, color: "var(--text-3)", marginTop: 14, textAlign: "center", lineHeight: 1.5 }}>
                  By creating an account you agree to the Terms and Privacy Policy. VolterraAI is for research and education, not investment advice.
                </p>
              ) : null}

              <div style={{ marginTop: 24, fontSize: 13.5, color: "var(--text-2)", textAlign: "center" }}>
                {mode === "signin" ? (
                  <>New to VolterraAI? <button style={linkStyle} onClick={() => setMode("signup")}>Create an account</button></>
                ) : mode === "signup" ? (
                  <>Already have an account? <button style={linkStyle} onClick={() => setMode("signin")}>Sign in</button></>
                ) : (
                  <button style={linkStyle} onClick={() => setMode("signin")}>← Back to sign in</button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}

export default function AuthPage() {
  return (
    <Suspense>
      <AuthInner />
    </Suspense>
  );
}
