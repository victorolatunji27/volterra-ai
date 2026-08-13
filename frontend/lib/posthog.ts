// PostHog product analytics. Explicit events only — autocapture is disabled
// and pageviews are tracked manually (see components/PostHogTracker.tsx).
//
// When NEXT_PUBLIC_POSTHOG_KEY is unset (local/demo), init is skipped and
// track/identifyUser are no-ops, so call sites never need to guard.
import posthog from "posthog-js";

let initialized = false;

export function initPostHog(): void {
  if (typeof window === "undefined") return;
  const key = process.env.NEXT_PUBLIC_POSTHOG_KEY;
  if (!key || initialized) return;
  posthog.init(key, {
    api_host: "https://app.posthog.com",
    capture_pageview: false, // manual page_viewed events on route change
    autocapture: false,
    persistence: "localStorage",
  });
  initialized = true;
}

export function track(event: string, props?: Record<string, unknown>): void {
  if (!initialized) return;
  posthog.capture(event, props);
}

export function identifyUser(id: string, props: Record<string, unknown>): void {
  if (!initialized) return;
  posthog.identify(id, props);
}

/** Drop the identified user on sign-out so the next session isn't attributed to them. */
export function resetAnalytics(): void {
  if (!initialized) return;
  posthog.reset();
}
