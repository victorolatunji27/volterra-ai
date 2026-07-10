"use client";
// Initializes PostHog on mount and fires a manual page_viewed event on every
// route change. Rendered once from the root layout; renders nothing.
import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { initPostHog, track } from "@/lib/posthog";

export default function PostHogTracker() {
  const pathname = usePathname();

  useEffect(() => {
    initPostHog();
  }, []);

  useEffect(() => {
    track("page_viewed", { path: pathname });
  }, [pathname]);

  return null;
}
