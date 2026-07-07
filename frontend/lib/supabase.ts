"use client";
// Browser Supabase client (cookie-based session via @supabase/ssr so the
// middleware can also see it). Returns null when Supabase env vars are not
// set — the app then runs in demo mode: auth flows simulate success and the
// middleware does not gate any route.
import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const isSupabaseConfigured = Boolean(url && anonKey);

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient | null {
  if (!isSupabaseConfigured) return null;
  if (!client) client = createBrowserClient(url as string, anonKey as string);
  return client;
}
