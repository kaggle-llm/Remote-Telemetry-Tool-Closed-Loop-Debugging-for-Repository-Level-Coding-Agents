-- Run in Supabase SQL Editor. This schema does not use Supabase Auth.
create extension if not exists pgcrypto with schema extensions;

create table if not exists public.users (
  id uuid primary key default gen_random_uuid(),
  google_sub text not null unique,
  email text not null,
  display_name text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.client_logs (
  id bigint generated always as identity primary key,
  user_id uuid not null,
  session_id text not null check (length(session_id) between 1 and 128),
  ai_session_id uuid,
  client_session_id uuid,
  case_id uuid,
  level text not null default 'info' check (level in ('info', 'warn', 'error')),
  event text not null check (length(event) between 1 and 120),
  detail jsonb not null default '{}'::jsonb check (jsonb_typeof(detail) = 'object'),
  user_agent text,
  created_at timestamptz not null default now()
);

create table if not exists public.app_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  token_hash text not null unique check (length(token_hash) = 64),
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

create table if not exists public.tool_api_keys (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  name text not null default 'AI tool key' check (length(name) between 1 and 80),
  key_hash text not null unique check (length(key_hash) = 64),
  key_prefix text not null check (length(key_prefix) between 1 and 16),
  created_at timestamptz not null default now(),
  revoked_at timestamptz
);

create table if not exists public.telemetry_ingest_keys (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  name text not null default 'client app' check (length(name) between 1 and 80),
  key_hash text not null unique check (length(key_hash) = 64),
  key_prefix text not null check (length(key_prefix) between 1 and 16),
  created_at timestamptz not null default now(),
  revoked_at timestamptz
);
create index if not exists telemetry_ingest_keys_owner_idx on public.telemetry_ingest_keys (user_id, created_at desc);

create table if not exists public.ai_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  name text not null default 'AI session' check (length(name) between 1 and 80),
  session_hash text not null unique check (length(session_hash) = 64),
  session_prefix text not null check (length(session_prefix) between 1 and 16),
  created_at timestamptz not null default now(),
  revoked_at timestamptz
);

alter table public.ai_sessions add column if not exists run_id text;
update public.ai_sessions set run_id = encode(extensions.gen_random_bytes(16), 'hex') where run_id is null;
alter table public.ai_sessions alter column run_id set not null;
create unique index if not exists ai_sessions_user_run_idx on public.ai_sessions (user_id, run_id) where revoked_at is null;

create table if not exists public.client_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  client_id text not null check (length(client_id) between 1 and 100),
  name text not null default 'Client session' check (length(name) between 1 and 80),
  session_hash text not null unique check (length(session_hash) = 64),
  session_prefix text not null check (length(session_prefix) between 1 and 16),
  created_at timestamptz not null default now(),
  revoked_at timestamptz
);
alter table public.client_sessions add column if not exists client_id text;
update public.client_sessions set client_id = 'legacy-' || id::text where client_id is null;
alter table public.client_sessions alter column client_id set not null;
create unique index if not exists client_sessions_user_client_active_idx on public.client_sessions (user_id, client_id) where revoked_at is null;
create unique index if not exists client_sessions_session_hash_idx on public.client_sessions (session_hash);

-- debug_cases: stateful debugging loop (reported -> instrumenting -> awaiting_recheck -> rechecked -> patch_ready -> approved|rejected -> resolved|instrumenting)
create table if not exists public.debug_cases (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  client_session_id uuid not null references public.client_sessions(id) on delete cascade,
  ai_session_id uuid references public.ai_sessions(id) on delete set null,
  title text not null check (length(title) between 1 and 120),
  user_report text not null check (length(user_report) between 1 and 4000),
  state text not null default 'reported' check (state in ('reported','instrumenting','awaiting_recheck','rechecked','patch_ready','approved','rejected','resolved','abandoned')),
  instructions text check (length(instructions) <= 8000),
  version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  state_changed_at timestamptz not null default now(),
  resolved_at timestamptz
);
create index if not exists debug_cases_user_created_idx on public.debug_cases (user_id, created_at desc);
create index if not exists debug_cases_client_session_idx on public.debug_cases (client_session_id) where state not in ('resolved','abandoned');

-- case_probes: runtime-selectable instrumentation probes attached to a case
create table if not exists public.case_probes (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.debug_cases(id) on delete cascade,
  probe_id text not null check (length(probe_id) between 1 and 80),
  target text not null check (length(target) between 1 and 200),
  capture jsonb not null default '{}'::jsonb check (jsonb_typeof(capture) = 'object'),
  level text not null default 'warn' check (level in ('info','warn','error')),
  active boolean not null default true,
  created_at timestamptz not null default now()
);
create index if not exists case_probes_case_id_idx on public.case_probes (case_id);

-- case_reports: timeline of user re-check reports. Kept separate from
-- debug_cases.user_report so that repeated re-checks cannot overflow the
-- 4000-character column constraint on the original report.
create table if not exists public.case_reports (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.debug_cases(id) on delete cascade,
  report text not null check (length(report) between 1 and 4000),
  created_at timestamptz not null default now()
);
create index if not exists case_reports_case_id_created_idx on public.case_reports (case_id, created_at desc);

-- Columns must exist before their foreign keys are added: on an existing
-- database `create table if not exists` above is a no-op, so the alters here
-- are what actually introduce case_id / client_session_id / ai_session_id.
alter table public.client_logs add column if not exists client_session_id uuid;
alter table public.client_logs add column if not exists ai_session_id uuid;
alter table public.client_logs add column if not exists case_id uuid;

alter table public.client_logs drop constraint if exists client_logs_client_session_id_fkey;
alter table public.client_logs add constraint client_logs_client_session_id_fkey
  foreign key (client_session_id) references public.client_sessions(id) on delete set null;

alter table public.client_logs drop constraint if exists client_logs_user_id_fkey;
alter table public.client_logs drop constraint if exists client_logs_ai_session_id_fkey;
alter table public.client_logs drop constraint if exists client_logs_case_id_fkey;
alter table public.client_logs add constraint client_logs_user_id_fkey
  foreign key (user_id) references public.users(id) on delete cascade;
alter table public.client_logs add constraint client_logs_ai_session_id_fkey
  foreign key (ai_session_id) references public.ai_sessions(id) on delete set null;
alter table public.client_logs add constraint client_logs_case_id_fkey
  foreign key (case_id) references public.debug_cases(id) on delete set null;

create index if not exists client_logs_ai_session_created_idx on public.client_logs (ai_session_id, created_at desc);
create index if not exists client_logs_client_session_created_idx on public.client_logs (client_session_id, created_at desc);
create index if not exists client_logs_case_id_created_idx on public.client_logs (case_id, created_at desc);
create index if not exists tool_api_keys_owner_idx on public.tool_api_keys (user_id, created_at desc);
create index if not exists ai_sessions_owner_idx on public.ai_sessions (user_id, created_at desc);

alter table public.users enable row level security;
alter table public.app_sessions enable row level security;
alter table public.tool_api_keys enable row level security;
alter table public.telemetry_ingest_keys enable row level security;
alter table public.ai_sessions enable row level security;
alter table public.client_sessions enable row level security;
alter table public.client_logs enable row level security;
alter table public.debug_cases enable row level security;
alter table public.case_probes enable row level security;
alter table public.telemetry_ingest_keys add column if not exists name text not null default 'client app';
alter table public.telemetry_ingest_keys add column if not exists key_prefix text not null default 'tli_legacy';
alter table public.telemetry_ingest_keys add column if not exists created_at timestamptz not null default now();
alter table public.telemetry_ingest_keys add column if not exists revoked_at timestamptz;

-- No anon/authenticated table policies or grants: dashboard operations go through the custom backend.
revoke all on public.users, public.app_sessions, public.tool_api_keys, public.telemetry_ingest_keys, public.ai_sessions, public.client_sessions, public.client_logs, public.debug_cases, public.case_probes from anon, authenticated;
revoke all on public.client_logs from anon, authenticated;

-- The custom backend uses a Supabase server secret (service_role) for these operations.
-- Keep this credential server-side only. RLS is enabled above; service_role bypasses RLS.
grant select, insert, update, delete on public.users, public.app_sessions,
  public.tool_api_keys, public.telemetry_ingest_keys, public.ai_sessions, public.client_sessions, public.client_logs, public.debug_cases, public.case_probes to service_role;
grant usage, select on all sequences in schema public to service_role;

create or replace function public.read_session_logs(p_tool_key text, p_session_key text, p_limit integer default 50)
returns setof public.client_logs
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid; v_session_id uuid;
begin
  if p_limit is null or p_limit < 1 or p_limit > 100 then raise exception 'limit must be between 1 and 100' using errcode = '22023'; end if;
  select k.user_id into v_user_id from public.tool_api_keys k
    where k.key_hash = encode(extensions.digest(convert_to(p_tool_key, 'UTF8'), 'sha256'), 'hex') and k.revoked_at is null;
  if v_user_id is null then raise exception 'invalid tool key' using errcode = '42501'; end if;
  select s.id into v_session_id from public.ai_sessions s
    where s.user_id = v_user_id and s.session_hash = encode(extensions.digest(convert_to(p_session_key, 'UTF8'), 'sha256'), 'hex') and s.revoked_at is null;
  if v_session_id is null then raise exception 'invalid session key' using errcode = '42501'; end if;
  return query select l.* from public.client_logs l where l.user_id = v_user_id and l.ai_session_id = v_session_id order by l.created_at desc limit p_limit;
end;
$$;

create or replace function public.read_client_session_logs(p_tool_key text, p_client_session_key text, p_limit integer default 50)
returns setof public.client_logs
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid; v_session_id uuid;
begin
  if p_limit is null or p_limit < 1 or p_limit > 100 then raise exception 'limit must be between 1 and 100' using errcode = '22023'; end if;
  select k.user_id into v_user_id from public.tool_api_keys k
    where k.key_hash = encode(extensions.digest(convert_to(p_tool_key, 'UTF8'), 'sha256'), 'hex') and k.revoked_at is null;
  if v_user_id is null then raise exception 'invalid tool key' using errcode = '42501'; end if;
  select s.id into v_session_id from public.client_sessions s
    where s.user_id = v_user_id and s.session_hash = encode(extensions.digest(convert_to(p_client_session_key, 'UTF8'), 'sha256'), 'hex') and s.revoked_at is null;
  if v_session_id is null then raise exception 'invalid client session' using errcode = '42501'; end if;
  return query select l.* from public.client_logs l where l.user_id = v_user_id and l.client_session_id = v_session_id order by l.created_at desc limit p_limit;
end;
$$;

create or replace function public.read_recent_client_logs(p_tool_key text, p_limit integer default 50)
returns setof public.client_logs
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid;
begin
  if p_limit is null or p_limit < 1 or p_limit > 100 then raise exception 'limit must be between 1 and 100' using errcode = '22023'; end if;
  select k.user_id into v_user_id from public.tool_api_keys k
    where k.key_hash = encode(extensions.digest(convert_to(p_tool_key, 'UTF8'), 'sha256'), 'hex') and k.revoked_at is null;
  if v_user_id is null then raise exception 'invalid tool key' using errcode = '42501'; end if;
  return query select l.* from public.client_logs l where l.user_id = v_user_id and l.client_session_id is not null order by l.created_at desc limit p_limit;
end;
$$;

create or replace function public.write_client_session_log(p_tool_key text, p_client_session_key text, p_level text, p_event text, p_detail jsonb default '{}'::jsonb, p_user_agent text default null)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid; v_session_id uuid; v_log_id bigint;
begin
  if p_level not in ('info', 'warn', 'error') then raise exception 'invalid level' using errcode = '22023'; end if;
  if p_event is null or length(p_event) not between 1 and 120 then raise exception 'event must be 1-120 characters' using errcode = '22023'; end if;
  if p_detail is null or jsonb_typeof(p_detail) <> 'object' or length(p_detail::text) > 8000 then raise exception 'detail must be an object of at most 8000 characters' using errcode = '22023'; end if;
  select k.user_id into v_user_id from public.tool_api_keys k
    where k.key_hash = encode(extensions.digest(convert_to(p_tool_key, 'UTF8'), 'sha256'), 'hex') and k.revoked_at is null;
  if v_user_id is null then raise exception 'invalid tool key' using errcode = '42501'; end if;
  select s.id into v_session_id from public.client_sessions s
    where s.user_id = v_user_id and s.session_hash = encode(extensions.digest(convert_to(p_client_session_key, 'UTF8'), 'sha256'), 'hex') and s.revoked_at is null;
  if v_session_id is null then raise exception 'invalid client session' using errcode = '42501'; end if;
  insert into public.client_logs (user_id, session_id, client_session_id, level, event, detail, user_agent)
    values (v_user_id, v_session_id::text, v_session_id, p_level, p_event, p_detail, left(p_user_agent, 512)) returning id into v_log_id;
  return jsonb_build_object('id', v_log_id, 'client_session_id', v_session_id, 'created', true);
end;
$$;

create or replace function public.write_ingest_client_log(p_ingest_key text, p_client_session_key text, p_level text, p_event text, p_detail jsonb default '{}'::jsonb, p_user_agent text default null, p_case_id uuid default null)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid; v_session_id uuid; v_log_id bigint; v_case_id uuid;
begin
  if p_level not in ('info', 'warn', 'error') then raise exception 'invalid level' using errcode = '22023'; end if;
  if p_event is null or length(p_event) not between 1 and 120 then raise exception 'event must be 1-120 characters' using errcode = '22023'; end if;
  if p_detail is null or jsonb_typeof(p_detail) <> 'object' or length(p_detail::text) > 8000 then raise exception 'detail must be an object of at most 8000 characters' using errcode = '22023'; end if;
  select k.user_id into v_user_id from public.telemetry_ingest_keys k
    where k.key_hash = encode(extensions.digest(convert_to(p_ingest_key, 'UTF8'), 'sha256'), 'hex') and k.revoked_at is null;
  if v_user_id is null then raise exception 'invalid ingest key' using errcode = '42501'; end if;
  select s.id into v_session_id from public.client_sessions s
    where s.user_id = v_user_id and s.session_hash = encode(extensions.digest(convert_to(p_client_session_key, 'UTF8'), 'sha256'), 'hex') and s.revoked_at is null;
  if v_session_id is null then raise exception 'invalid client session' using errcode = '42501'; end if;
  if p_case_id is not null then
    select c.id into v_case_id from public.debug_cases c
      where c.id = p_case_id and c.user_id = v_user_id and c.client_session_id = v_session_id and c.state not in ('resolved','abandoned');
    if v_case_id is null then raise exception 'case not found or access denied' using errcode = '42501'; end if;
  else
    v_case_id := null;
  end if;
  insert into public.client_logs (user_id, session_id, client_session_id, case_id, level, event, detail, user_agent)
    values (v_user_id, v_session_id::text, v_session_id, v_case_id, p_level, p_event, p_detail, left(p_user_agent, 512)) returning id into v_log_id;
  return jsonb_build_object('id', v_log_id, 'client_session_id', v_session_id, 'case_id', v_case_id, 'created', true);
end;
$$;

create or replace function public.write_session_log(p_tool_key text, p_session_key text, p_level text, p_event text, p_detail jsonb default '{}'::jsonb)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid; v_session_id uuid; v_log_id bigint;
begin
  if p_level not in ('info', 'warn', 'error') then raise exception 'invalid level' using errcode = '22023'; end if;
  if p_event is null or length(p_event) not between 1 and 120 then raise exception 'event must be 1-120 characters' using errcode = '22023'; end if;
  if p_detail is null or jsonb_typeof(p_detail) <> 'object' or length(p_detail::text) > 8000 then raise exception 'detail must be an object of at most 8000 characters' using errcode = '22023'; end if;
  select k.user_id into v_user_id from public.tool_api_keys k
    where k.key_hash = encode(extensions.digest(convert_to(p_tool_key, 'UTF8'), 'sha256'), 'hex') and k.revoked_at is null;
  if v_user_id is null then raise exception 'invalid tool key' using errcode = '42501'; end if;
  select s.id into v_session_id from public.ai_sessions s
    where s.user_id = v_user_id and s.session_hash = encode(extensions.digest(convert_to(p_session_key, 'UTF8'), 'sha256'), 'hex') and s.revoked_at is null;
  if v_session_id is null then raise exception 'invalid session key' using errcode = '42501'; end if;
  insert into public.client_logs (user_id, session_id, ai_session_id, level, event, detail)
    values (v_user_id, v_session_id::text, v_session_id, p_level, p_event, p_detail) returning id into v_log_id;
  return jsonb_build_object('id', v_log_id, 'ai_session_id', v_session_id, 'created', true);
end;
$$;

-- Create a debug case (client-initiated)
create or replace function public.create_debug_case(p_ingest_key text, p_client_session_key text, p_title text, p_user_report text)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid; v_session_id uuid; v_case_id uuid;
begin
  if p_title is null or length(p_title) not between 1 and 120 then raise exception 'title must be 1-120 characters' using errcode = '22023'; end if;
  if p_user_report is null or length(p_user_report) not between 1 and 4000 then raise exception 'user_report must be 1-4000 characters' using errcode = '22023'; end if;
  select k.user_id into v_user_id from public.telemetry_ingest_keys k
    where k.key_hash = encode(extensions.digest(convert_to(p_ingest_key, 'UTF8'), 'sha256'), 'hex') and k.revoked_at is null;
  if v_user_id is null then raise exception 'invalid ingest key' using errcode = '42501'; end if;
  select s.id into v_session_id from public.client_sessions s
    where s.user_id = v_user_id and s.session_hash = encode(extensions.digest(convert_to(p_client_session_key, 'UTF8'), 'sha256'), 'hex') and s.revoked_at is null;
  if v_session_id is null then raise exception 'invalid client session' using errcode = '42501'; end if;
  insert into public.debug_cases (user_id, client_session_id, title, user_report)
    values (v_user_id, v_session_id, p_title, p_user_report)
    returning id into v_case_id;
  return jsonb_build_object('case_id', v_case_id, 'state', 'reported', 'version', 1, 'created', true);
end;
$$;

-- Read case state + instructions + active probes (client poll)
create or replace function public.read_case_state(p_ingest_key text, p_client_session_key text, p_case_id uuid)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid; v_session_id uuid; v_case record; v_probes jsonb;
begin
  select k.user_id into v_user_id from public.telemetry_ingest_keys k
    where k.key_hash = encode(extensions.digest(convert_to(p_ingest_key, 'UTF8'), 'sha256'), 'hex') and k.revoked_at is null;
  if v_user_id is null then raise exception 'invalid ingest key' using errcode = '42501'; end if;
  select s.id into v_session_id from public.client_sessions s
    where s.user_id = v_user_id and s.session_hash = encode(extensions.digest(convert_to(p_client_session_key, 'UTF8'), 'sha256'), 'hex') and s.revoked_at is null;
  if v_session_id is null then raise exception 'invalid client session' using errcode = '42501'; end if;
  select * into v_case from public.debug_cases c
    where c.id = p_case_id and c.user_id = v_user_id and c.client_session_id = v_session_id;
  if not found then raise exception 'case not found' using errcode = '42501'; end if;
  select jsonb_agg(jsonb_build_object('probe_id', cp.probe_id, 'target', cp.target, 'capture', cp.capture, 'level', cp.level))
    into v_probes from public.case_probes cp where cp.case_id = p_case_id and cp.active = true;
  return jsonb_build_object(
    'case_id', v_case.id, 'state', v_case.state, 'version', v_case.version,
    'title', v_case.title, 'user_report', v_case.user_report,
    'instructions', v_case.instructions, 'probes', v_probes,
    'updated_at', v_case.updated_at
  );
end;
$$;

-- Drop the pre-overload 5-arg signature so the 6-arg version is unambiguous.
drop function if exists public.set_case_instructions(text, uuid, text, jsonb, text);

-- AI sets instructions + probes; transitions state to instrumenting
create or replace function public.set_case_instructions(p_tool_key text, p_case_id uuid, p_instructions text, p_probes jsonb default '[]'::jsonb, p_next_state text default 'instrumenting', p_ai_session_id uuid default null)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid; v_case record; v_allowed_states text[] := array['reported','instrumenting','awaiting_recheck','rechecked','patch_ready','rejected']; v_probe record; v_ai_session_id uuid;
begin
  if p_instructions is null or length(p_instructions) > 8000 then raise exception 'instructions must be 1-8000 characters' using errcode = '22023'; end if;
  if p_next_state not in ('instrumenting','awaiting_recheck') then raise exception 'invalid next_state' using errcode = '22023'; end if;
  select k.user_id into v_user_id from public.tool_api_keys k
    where k.key_hash = encode(extensions.digest(convert_to(p_tool_key, 'UTF8'), 'sha256'), 'hex') and k.revoked_at is null;
  if v_user_id is null then raise exception 'invalid tool key' using errcode = '42501'; end if;
  select * into v_case from public.debug_cases c
    where c.id = p_case_id and c.user_id = v_user_id;
  if not found then raise exception 'case not found' using errcode = '42501'; end if;
  if not (v_case.state = any(v_allowed_states)) then raise exception 'invalid state transition' using errcode = '22023'; end if;
  -- Resolve the active AI run for this developer account so the case is
  -- linked to the agent session that is working on it.
  if p_ai_session_id is null then
    select s.id into v_ai_session_id from public.ai_sessions s
      where s.user_id = v_user_id and s.revoked_at is null
      order by s.created_at desc limit 1;
  else
    select s.id into v_ai_session_id from public.ai_sessions s
      where s.id = p_ai_session_id and s.user_id = v_user_id and s.revoked_at is null;
    if v_ai_session_id is null then raise exception 'invalid ai session' using errcode = '42501'; end if;
  end if;
  update public.debug_cases set instructions = p_instructions, state = p_next_state, ai_session_id = v_ai_session_id, version = version + 1, updated_at = now(), state_changed_at = now() where id = p_case_id;
  -- Upsert probes
  delete from public.case_probes where case_id = p_case_id;
  insert into public.case_probes (case_id, probe_id, target, capture, level, active)
    select p_case_id,
      (p->>'probe_id')::text,
      (p->>'target')::text,
      coalesce((p->>'capture')::jsonb, '{}'::jsonb),
      coalesce(p->>'level', 'warn'),
      true
    from jsonb_array_elements(p_probes) AS p;
  return jsonb_build_object('case_id', p_case_id, 'state', p_next_state, 'ai_session_id', v_ai_session_id, 'version', v_case.version + 1, 'updated', true);
end;
$$;

-- AI reads case-scoped logs
create or replace function public.read_case_logs(p_tool_key text, p_case_id uuid, p_limit integer default 50)
returns setof public.client_logs
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid; v_case_id uuid;
begin
  if p_limit is null or p_limit < 1 or p_limit > 100 then raise exception 'limit must be between 1 and 100' using errcode = '22023'; end if;
  select k.user_id into v_user_id from public.tool_api_keys k
    where k.key_hash = encode(extensions.digest(convert_to(p_tool_key, 'UTF8'), 'sha256'), 'hex') and k.revoked_at is null;
  if v_user_id is null then raise exception 'invalid tool key' using errcode = '42501'; end if;
  select c.id into v_case_id from public.debug_cases c where c.id = p_case_id and c.user_id = v_user_id;
  if v_case_id is null then raise exception 'case not found' using errcode = '42501'; end if;
  return query select l.* from public.client_logs l where l.user_id = v_user_id and l.case_id = v_case_id order by l.created_at desc limit p_limit;
end;
$$;

-- Client reports re-check result
create or replace function public.report_case_progress(p_ingest_key text, p_client_session_key text, p_case_id uuid, p_report text)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid; v_session_id uuid; v_case record;
begin
  if p_report is null or length(p_report) not between 1 and 4000 then raise exception 'report must be 1-4000 characters' using errcode = '22023'; end if;
  select k.user_id into v_user_id from public.telemetry_ingest_keys k
    where k.key_hash = encode(extensions.digest(convert_to(p_ingest_key, 'UTF8'), 'sha256'), 'hex') and k.revoked_at is null;
  if v_user_id is null then raise exception 'invalid ingest key' using errcode = '42501'; end if;
  select s.id into v_session_id from public.client_sessions s
    where s.user_id = v_user_id and s.session_hash = encode(extensions.digest(convert_to(p_client_session_key, 'UTF8'), 'sha256'), 'hex') and s.revoked_at is null;
  if v_session_id is null then raise exception 'invalid client session' using errcode = '42501'; end if;
  select * into v_case from public.debug_cases c
    where c.id = p_case_id and c.user_id = v_user_id and c.client_session_id = v_session_id;
  if not found then raise exception 'case not found' using errcode = '42501'; end if;
  if v_case.state <> 'awaiting_recheck' then raise exception 'case not awaiting recheck' using errcode = '22023'; end if;
  -- Append report to case_reports timeline instead of user_report to avoid
  -- overflowing the original user_report column constraint.
  insert into public.case_reports (case_id, report) values (p_case_id, p_report);
  update public.debug_cases set
    state = 'rechecked',
    version = version + 1,
    updated_at = now(),
    state_changed_at = now()
  where id = p_case_id;
  return jsonb_build_object('case_id', p_case_id, 'state', 'rechecked', 'version', v_case.version + 1, 'updated', true);
end;
$$;

-- Client approves/rejects the fix
create or replace function public.approve_case(p_ingest_key text, p_client_session_key text, p_case_id uuid, p_approved boolean)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid; v_session_id uuid; v_case record;
begin
  select k.user_id into v_user_id from public.telemetry_ingest_keys k
    where k.key_hash = encode(extensions.digest(convert_to(p_ingest_key, 'UTF8'), 'sha256'), 'hex') and k.revoked_at is null;
  if v_user_id is null then raise exception 'invalid ingest key' using errcode = '42501'; end if;
  select s.id into v_session_id from public.client_sessions s
    where s.user_id = v_user_id and s.session_hash = encode(extensions.digest(convert_to(p_client_session_key, 'UTF8'), 'sha256'), 'hex') and s.revoked_at is null;
  if v_session_id is null then raise exception 'invalid client session' using errcode = '42501'; end if;
  select * into v_case from public.debug_cases c
    where c.id = p_case_id and c.user_id = v_user_id and c.client_session_id = v_session_id;
  if not found then raise exception 'case not found' using errcode = '42501'; end if;
  if v_case.state <> 'patch_ready' then raise exception 'case not ready for approval' using errcode = '22023'; end if;
  update public.debug_cases set
    state = case when p_approved then 'approved' else 'rejected' end,
    version = version + 1,
    updated_at = now(),
    state_changed_at = now(),
    resolved_at = case when p_approved then now() else null end
  where id = p_case_id;
  return jsonb_build_object('case_id', p_case_id, 'state', case when p_approved then 'approved' else 'rejected' end, 'version', v_case.version + 1, 'updated', true);
end;
$$;

-- AI transitions case to patch_ready or abandoned
create or replace function public.transition_case(p_tool_key text, p_case_id uuid, p_next_state text)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid; v_case record;
begin
  if p_next_state not in ('patch_ready','abandoned') then raise exception 'invalid next_state' using errcode = '22023'; end if;
  select k.user_id into v_user_id from public.tool_api_keys k
    where k.key_hash = encode(extensions.digest(convert_to(p_tool_key, 'UTF8'), 'sha256'), 'hex') and k.revoked_at is null;
  if v_user_id is null then raise exception 'invalid tool key' using errcode = '42501'; end if;
  select * into v_case from public.debug_cases c where c.id = p_case_id and c.user_id = v_user_id;
  if not found then raise exception 'case not found' using errcode = '42501'; end if;
  if p_next_state = 'patch_ready' and v_case.state <> 'rechecked' then raise exception 'case must be rechecked to become patch_ready' using errcode = '22023'; end if;
  if p_next_state = 'abandoned' and v_case.state not in ('reported','instrumenting','awaiting_recheck','rechecked','patch_ready','rejected') then raise exception 'cannot abandon from current state' using errcode = '22023'; end if;
  update public.debug_cases set state = p_next_state, version = version + 1, updated_at = now(), state_changed_at = now() where id = p_case_id;
  return jsonb_build_object('case_id', p_case_id, 'state', p_next_state, 'version', v_case.version + 1, 'updated', true);
end;
$$;

-- AI purges case logs (only after approved)
create or replace function public.purge_case_logs(p_tool_key text, p_case_id uuid)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid; v_case record; v_deleted integer;
begin
  select k.user_id into v_user_id from public.tool_api_keys k
    where k.key_hash = encode(extensions.digest(convert_to(p_tool_key, 'UTF8'), 'sha256'), 'hex') and k.revoked_at is null;
  if v_user_id is null then raise exception 'invalid tool key' using errcode = '42501'; end if;
  select * into v_case from public.debug_cases c where c.id = p_case_id and c.user_id = v_user_id;
  if not found then raise exception 'case not found' using errcode = '42501'; end if;
  if v_case.state <> 'approved' then raise exception 'case not approved for cleanup' using errcode = '22023'; end if;
  delete from public.client_logs where case_id = p_case_id;
  get diagnostics v_deleted = row_count;
  -- Deactivate probes so the client stops collecting telemetry for this case.
  update public.case_probes set active = false where case_id = p_case_id;
  update public.debug_cases set state = 'resolved', version = version + 1, updated_at = now(), state_changed_at = now() where id = p_case_id;
  return jsonb_build_object('case_id', p_case_id, 'state', 'resolved', 'deleted_logs', v_deleted, 'cleaned', true);
end;
$$;

-- AI lists cases for this account
create or replace function public.list_cases(p_tool_key text, p_limit integer default 50, p_state text default null)
returns setof public.debug_cases
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid;
begin
  if p_limit is null or p_limit < 1 or p_limit > 100 then raise exception 'limit must be between 1 and 100' using errcode = '22023'; end if;
  if p_state is not null and p_state not in ('reported','instrumenting','awaiting_recheck','rechecked','patch_ready','approved','rejected','resolved','abandoned') then raise exception 'invalid state' using errcode = '22023'; end if;
  select k.user_id into v_user_id from public.tool_api_keys k
    where k.key_hash = encode(extensions.digest(convert_to(p_tool_key, 'UTF8'), 'sha256'), 'hex') and k.revoked_at is null;
  if v_user_id is null then raise exception 'invalid tool key' using errcode = '42501'; end if;
  return query
    select c.* from public.debug_cases c
    where c.user_id = v_user_id
      and (p_state is null or c.state = p_state)
    order by c.created_at desc limit p_limit;
end;
$$;

-- write_ingest_client_log gained a p_case_id argument; drop the superseded signature.
drop function if exists public.write_ingest_client_log(text, text, text, text, jsonb, text);

revoke all on function public.read_session_logs(text, text, integer) from public, anon, authenticated;
revoke all on function public.write_session_log(text, text, text, text, jsonb) from public, anon, authenticated;
revoke all on function public.read_client_session_logs(text, text, integer) from public, anon, authenticated;
revoke all on function public.read_recent_client_logs(text, integer) from public, anon, authenticated;
revoke all on function public.write_client_session_log(text, text, text, text, jsonb, text) from public, anon, authenticated;
revoke all on function public.write_ingest_client_log(text, text, text, text, jsonb, text, uuid) from public, anon, authenticated;
revoke all on function public.create_debug_case(text, text, text, text) from public, anon, authenticated;
revoke all on function public.read_case_state(text, text, uuid) from public, anon, authenticated;
revoke all on function public.set_case_instructions(text, uuid, text, jsonb, text, uuid) from public, anon, authenticated;
revoke all on function public.read_case_logs(text, uuid, integer) from public, anon, authenticated;
revoke all on function public.report_case_progress(text, text, uuid, text) from public, anon, authenticated;
revoke all on function public.approve_case(text, text, uuid, boolean) from public, anon, authenticated;
revoke all on function public.purge_case_logs(text, uuid) from public, anon, authenticated;
revoke all on function public.transition_case(text, uuid, text) from public, anon, authenticated;
revoke all on function public.list_cases(text, integer, text) from public, anon, authenticated;

grant execute on function public.read_session_logs(text, text, integer) to anon, authenticated;
grant execute on function public.write_session_log(text, text, text, text, jsonb) to anon, authenticated;
grant execute on function public.read_session_logs(text, text, integer) to service_role;
grant execute on function public.write_session_log(text, text, text, text, jsonb) to service_role;
grant execute on function public.read_client_session_logs(text, text, integer) to service_role;
grant execute on function public.read_recent_client_logs(text, integer) to service_role;
grant execute on function public.write_client_session_log(text, text, text, text, jsonb, text) to service_role;
grant execute on function public.write_ingest_client_log(text, text, text, text, jsonb, text, uuid) to service_role;
grant execute on function public.create_debug_case(text, text, text, text) to anon, authenticated;
grant execute on function public.read_case_state(text, text, uuid) to anon, authenticated;
grant execute on function public.set_case_instructions(text, uuid, text, jsonb, text) to service_role;
grant execute on function public.read_case_logs(text, uuid, integer) to service_role;
grant execute on function public.report_case_progress(text, text, uuid, text) to anon, authenticated;
grant execute on function public.approve_case(text, text, uuid, boolean) to anon, authenticated;
grant execute on function public.purge_case_logs(text, uuid) to service_role;
grant execute on function public.transition_case(text, uuid, text) to service_role;
grant execute on function public.list_cases(text, integer, text) to service_role;

grant select, insert, update, delete on public.telemetry_ingest_keys to service_role;