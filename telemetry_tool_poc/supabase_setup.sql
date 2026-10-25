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
  session_id text not null check (length(session_id) between 1 and 64),
  ai_session_id uuid,
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

create table if not exists public.ai_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  name text not null default 'AI session' check (length(name) between 1 and 80),
  session_hash text not null unique check (length(session_hash) = 64),
  session_prefix text not null check (length(session_prefix) between 1 and 16),
  created_at timestamptz not null default now(),
  revoked_at timestamptz
);

alter table public.client_logs add column if not exists ai_session_id uuid;
alter table public.client_logs drop constraint if exists client_logs_user_id_fkey;
alter table public.client_logs drop constraint if exists client_logs_ai_session_id_fkey;
alter table public.client_logs add constraint client_logs_user_id_fkey
  foreign key (user_id) references public.users(id) on delete cascade;
alter table public.client_logs add constraint client_logs_ai_session_id_fkey
  foreign key (ai_session_id) references public.ai_sessions(id) on delete set null;

create index if not exists client_logs_ai_session_created_idx on public.client_logs (ai_session_id, created_at desc);
create index if not exists tool_api_keys_owner_idx on public.tool_api_keys (user_id, created_at desc);
create index if not exists ai_sessions_owner_idx on public.ai_sessions (user_id, created_at desc);

alter table public.users enable row level security;
alter table public.app_sessions enable row level security;
alter table public.tool_api_keys enable row level security;
alter table public.ai_sessions enable row level security;
alter table public.client_logs enable row level security;

-- No anon/authenticated table policies or grants: dashboard operations go through the custom backend.
revoke all on public.users, public.app_sessions, public.tool_api_keys, public.ai_sessions from anon, authenticated;
revoke all on public.client_logs from anon, authenticated;

-- The custom backend uses a Supabase server secret (service_role) for these operations.
-- Keep this credential server-side only. RLS is enabled above; service_role bypasses RLS.
grant select, insert, update, delete on public.users, public.app_sessions,
  public.tool_api_keys, public.ai_sessions, public.client_logs to service_role;
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

revoke all on function public.read_session_logs(text, text, integer) from public, anon, authenticated;
revoke all on function public.write_session_log(text, text, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.read_session_logs(text, text, integer) to anon, authenticated;
grant execute on function public.write_session_log(text, text, text, text, jsonb) to anon, authenticated;
