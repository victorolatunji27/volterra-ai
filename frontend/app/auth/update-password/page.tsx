"use client";
// Where the password-reset email lands (via /auth/callback, which exchanges
// the link's code for a recovery session). Sets a new password on that
// session, then sends the user into the app.
import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LOSS } from "@/components/theme";
import { useToast } from "@/components/toast";
import { getSupabase } from "@/lib/supabase";

const mono = "var(--mono)";
const MIN_PASSWORD_LENGTH = 8;

const label: React.CSSProperties = { display: "block", fontFamily: mono, fontSize: 11, letterSpacing: "0.07em", textTransform: "uppercase", color: "var(--text-3)", margin: "0 0 7px" };
const inputStyle: React.CSSProperties = { width: "100%", fontFamily: "var(--sans)", fontSize: 14.5, color: "var(--text)", background: "var(--surface-solid)", border: "1px solid var(--border-2)", borderRadius: 8, padding: "12px 13px" };
const btn: React.CSSProperties = { width: "100%", cursor: "pointer", border: "none", fontFamily: "inherit", fontSize: 15, fontWeight: 600, color: "#faf6ee", background: "linear-gradient(135deg,var(--a1),var(--a2))", padding: 13, borderRadius: 8, boxShadow: "0 16px 36px -16px var(--a1)" };
const linkStyle: React.CSSProperties = { color: "var(--a1)", fontSize: 13, textDecoration: "none", fontWeight: 500, cursor: "pointer", background: "none", border: "none", fontFamily: "inherit", padding: 0 };

export default function UpdatePasswordPage() {
  const router = useRouter();
  const { success } = useToast();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // null = still checking, true/false = whether a recovery session exists.
  const [hasSession, setHasSession] = useState<boolean | null>(null);

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) {
      // Demo mode — let the form render so the flow is walkable.
      setHasSession(true);
      return;
    }
    let alive = true;
    supabase.auth.getSession().then(({ data }) => {
      if (alive) setHasSession(Boolean(data.session));
    });
    return () => { alive = false; };
  }, []);

  const submit = async () => {
    if (busy) return;
    setError(null);

    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    const supabase = getSupabase();
    if (!supabase) {
      success("Password updated");
      router.push("/scan");
      return;
    }

    setBusy(true);
    const { error: err } = await supabase.auth.updateUser({ password });
    setBusy(false);
    if (err) {
      setError(err.message);
      return;
    }
    success("Password updated");
    router.push("/scan");
  };

  return (
    <section style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "48px 32px" }}>
      <div style={{ width: "100%", maxWidth: 384 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 28 }}>
          <svg width={28} height={28} viewBox="0 0 100 100" aria-hidden="true">
            <rect x={30} y={30} width={40} height={40} rx={9} fill="var(--a1)" />
            <path d="M52 40 L44 54 H50 L48 62 L58 46 H52 L54 40 Z" fill="#faf6ee" />
          </svg>
          <span style={{ fontWeight: 700, fontSize: 19, letterSpacing: "-0.01em" }}>Volterra</span>
          <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.04em", color: "var(--a1)" }}>AI</span>
        </div>

        <h1 style={{ fontSize: 30, letterSpacing: "-0.01em", margin: 0 }}>Set a new password</h1>

        {hasSession === null ? (
          <p style={{ fontSize: 14.5, color: "var(--text-2)", margin: "9px 0 0", lineHeight: 1.5 }}>Checking your reset link…</p>
        ) : hasSession === false ? (
          <>
            <p style={{ fontSize: 14.5, color: "var(--text-2)", margin: "9px 0 24px", lineHeight: 1.5 }}>
              This reset link is invalid or has expired. Request a new one and it will arrive within a few minutes.
            </p>
            <button style={btn} onClick={() => router.push("/auth")}>Back to sign in</button>
          </>
        ) : (
          <>
            <p style={{ fontSize: 14.5, color: "var(--text-2)", margin: "9px 0 28px", lineHeight: 1.5 }}>
              Choose a password you haven&apos;t used before.
            </p>

            <div style={{ marginBottom: 16 }}>
              <label style={label} htmlFor="new-pw">New password</label>
              <input id="new-pw" type="password" placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`} style={inputStyle} value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <div style={{ marginBottom: 20 }}>
              <label style={label} htmlFor="confirm-pw">Confirm password</label>
              <input id="confirm-pw" type="password" placeholder="Repeat it" style={inputStyle} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </div>

            {error ? (
              <div style={{ fontSize: 13, color: LOSS, lineHeight: 1.45, margin: "0 0 14px" }}>{error}</div>
            ) : null}

            <button style={{ ...btn, opacity: busy ? 0.7 : 1 }} onClick={submit} disabled={busy}>
              {busy ? "…" : "Update password"}
            </button>

            <div style={{ marginTop: 24, fontSize: 13.5, color: "var(--text-2)", textAlign: "center" }}>
              <button style={linkStyle} onClick={() => router.push("/auth")}>← Back to sign in</button>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
