-- 003_user_profile_trigger.sql — auto-create a user_profiles row per signup.
-- Run in the Supabase SQL Editor after 002_rls_policies.sql.
--
-- Supabase owns auth.users; the app reads public.user_profiles. Without this
-- bridge a brand-new signup has no profile row, and every authenticated API
-- call 401s. The backend also self-heals on first request (see
-- api/deps.py::_create_profile), but the trigger is the primary path: it
-- guarantees the row exists from the moment of signup, including for accounts
-- created straight from the Supabase dashboard or via OAuth.
--
-- SECURITY DEFINER so the function runs as its owner (the table owner) and
-- can insert regardless of the invoking role or RLS; search_path is pinned as
-- the standard hardening for definer functions.
--
-- Re-runnable.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.user_profiles (id, email, tier)
  VALUES (NEW.id, COALESCE(NEW.email, ''), 'free')
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Backfill: any auth.users that predate this trigger get a profile now.
INSERT INTO public.user_profiles (id, email, tier)
SELECT u.id, COALESCE(u.email, ''), 'free'
FROM auth.users u
LEFT JOIN public.user_profiles p ON p.id = u.id
WHERE p.id IS NULL;
