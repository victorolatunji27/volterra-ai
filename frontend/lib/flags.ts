// Launch-level feature flags (mirrors backend/config.py).
//
// The first launch is free-tier-only with no Stripe integration, so anything
// that assumes a paid Pro tier stays off: the PaywallGate overlay and the
// "Manage subscription" billing entry point. Flip this together with the
// backend's BILLING_ENABLED when paid plans ship.
export const PAYWALL_ENABLED = process.env.NEXT_PUBLIC_PAYWALL_ENABLED === "true";
