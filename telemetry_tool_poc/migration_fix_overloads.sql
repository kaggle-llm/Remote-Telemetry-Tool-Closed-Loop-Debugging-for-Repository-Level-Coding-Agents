-- Hotfix: remove the stale 5-argument overload of set_case_instructions.
--
-- The function gained a p_ai_session_id parameter, so a new 6-argument
-- overload was created next to the old 5-argument one. `create or replace`
-- cannot replace a function whose signature changed, so both variants now
-- exist and PostgREST cannot resolve a 5-argument call (PGRST203), which the
-- management API surfaces as HTTP 409.
--
-- Run this in the Supabase SQL Editor. It is safe to run more than once.

drop function if exists public.set_case_instructions(text, uuid, text, jsonb, text);

-- Verify: exactly one variant should remain.
select p.oid::regprocedure as signature
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public' and p.proname = 'set_case_instructions';
