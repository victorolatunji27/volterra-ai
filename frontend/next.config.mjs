import { withSentryConfig } from "@sentry/nextjs";

/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    // Required on Next 14 for instrumentation.ts (Sentry server/edge init).
    instrumentationHook: true,
  },
};

// Source-map upload is skipped (with a warning) until SENTRY_AUTH_TOKEN /
// SENTRY_ORG / SENTRY_PROJECT are configured — safe for local builds.
export default withSentryConfig(nextConfig, {
  silent: true,
  disableLogger: true,
});
