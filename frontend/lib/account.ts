// Account display helpers, shared by the sidebar and the settings page so the
// two can't drift. The API has no display-name field, so the email's local
// part stands in for one.
import type { Me } from "@/lib/api";

/** Illustrative identity shown in demo mode / when signed out (design values). */
export const DEMO_IDENTITY = { name: "Alex Rivera", plan: "Pro plan" };

export function displayName(email: string): string {
  return email.split("@")[0] || "Account";
}

export function planLabel(tier: string): string {
  return tier === "pro" ? "Pro plan" : "Free plan";
}

export function identityFromMe(me: Me): { name: string; plan: string } {
  return { name: displayName(me.email), plan: planLabel(me.tier) };
}
