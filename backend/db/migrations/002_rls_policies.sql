-- 002_rls_policies.sql — Row Level Security for Supabase.
-- Run in the Supabase SQL Editor after 001_initial_schema.sql.
--
-- Scope note: these policies apply to connections that carry a Supabase JWT
-- (PostgREST / supabase-js — i.e. the anon and authenticated roles). The
-- FastAPI backend connects as the postgres role, which OWNS these tables and
-- therefore bypasses RLS — its queries are unaffected, and per-user scoping
-- there is enforced in the route code. Do NOT add FORCE ROW LEVEL SECURITY:
-- auth.uid() is NULL on the backend's connections and it would break the API.
--
-- Re-runnable: policies are dropped before being created.

-- ── journal_entries: users read/write only their own rows ───────────────────
ALTER TABLE journal_entries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users can select own journal entries" ON journal_entries;
CREATE POLICY "users can select own journal entries"
ON journal_entries FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "users can insert own journal entries" ON journal_entries;
CREATE POLICY "users can insert own journal entries"
ON journal_entries FOR INSERT
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "users can update own journal entries" ON journal_entries;
CREATE POLICY "users can update own journal entries"
ON journal_entries FOR UPDATE
USING (auth.uid() = user_id);
-- (No WITH CHECK needed: Postgres reuses USING for new rows, so a user cannot
-- reassign a row to another user_id. No DELETE policy on purpose — the app
-- soft-deletes via UPDATE deleted_at; hard deletes are denied by default.)

-- ── user_profiles: users see and edit only their own profile ────────────────
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users can select own profile" ON user_profiles;
CREATE POLICY "users can select own profile"
ON user_profiles FOR SELECT
USING (auth.uid() = id);

DROP POLICY IF EXISTS "users can update own profile" ON user_profiles;
CREATE POLICY "users can update own profile"
ON user_profiles FOR UPDATE
USING (auth.uid() = id);

-- ── alert_log: users read only their own alert history ──────────────────────
ALTER TABLE alert_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users can select own alerts" ON alert_log;
CREATE POLICY "users can select own alerts"
ON alert_log FOR SELECT
USING (auth.uid() = user_id);

-- ── flow_scans / ai_summaries: read-only for any signed-in user ─────────────
ALTER TABLE flow_scans ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "authenticated users can read flow scans" ON flow_scans;
CREATE POLICY "authenticated users can read flow scans"
ON flow_scans FOR SELECT
USING (auth.role() = 'authenticated');

ALTER TABLE ai_summaries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "authenticated users can read ai summaries" ON ai_summaries;
CREATE POLICY "authenticated users can read ai summaries"
ON ai_summaries FOR SELECT
USING (auth.role() = 'authenticated');

-- ── digest_log: ops-only data — no API access at all ────────────────────────
-- Not in the original spec, but without RLS enabled Supabase exposes this
-- table to the anon key via PostgREST. Enabling RLS with zero policies
-- denies all API access; the backend (table owner) is unaffected.
ALTER TABLE digest_log ENABLE ROW LEVEL SECURITY;
