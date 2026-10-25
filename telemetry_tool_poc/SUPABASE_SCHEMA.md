# Supabase Tablo Yapısı

Uzak istemcilerden (iOS, Android vb.) gelen hata loglarının Supabase/PostgreSQL üzerinde saklanması ve Gemma 4 ajanı tarafından güvenli ve optimize edilmiş şekilde sorgulanabilmesi için nihai veritabanı şeması:

## SQL Tablo Tanımı

```sql
create table public.client_logs (
  id bigint generated always as identity not null,
  user_id uuid not null,
  session_id text not null,
  level text not null default 'info'::text,
  event text not null,
  detail jsonb not null default '{}'::jsonb,
  user_agent text null,
  created_at timestamp with time zone not null default now(),
  constraint client_logs_pkey primary key (id),
  constraint client_logs_user_id_fkey foreign KEY (user_id) references auth.users (id) on delete CASCADE,
  constraint client_logs_detail_object check ((jsonb_typeof(detail) = 'object'::text)),
  constraint client_logs_event_size check (
    (
      (length(event) >= 1)
      and (length(event) <= 120)
    )
  ),
  constraint client_logs_level check (
    (
      level = any (array['info'::text, 'warn'::text, 'error'::text])
    )
  ),
  constraint client_logs_session_size check (
    (
      (length(session_id) >= 1)
      and (length(session_id) <= 64)
    )
  )
) TABLESPACE pg_default;

create index IF not exists client_logs_user_created_idx on public.client_logs using btree (user_id, created_at desc) TABLESPACE pg_default;

-- Enable row-level security before exposing this table through the Data API.
alter table public.client_logs enable row level security;

-- Authenticated clients may insert only events associated with their own auth user.
create policy "Users can insert their own client logs"
on public.client_logs
for insert
to authenticated
with check ((select auth.uid()) = user_id);

-- Authenticated users may read only their own events.
create policy "Users can read their own client logs"
on public.client_logs
for select
to authenticated
using ((select auth.uid()) = user_id);
```

> Run this in the Supabase SQL Editor. Supabase Auth user records are in `auth.users`; an unqualified `users` table is not created automatically, which caused `ERROR: 42P01`. If the project intentionally has its own `public.users` table, use that table only if it is the desired identity source. Do not create a duplicate users table just to bypass the error.

## Important Access Notes
- The policies above permit authenticated users to insert and read their own rows. They do not allow anonymous access.
- The client must obtain a valid Supabase Auth session. The publishable key identifies the project but is not a user identity and does not bypass RLS.
- With custom login, do not pass the custom access token directly as the Supabase bearer token unless Supabase has been configured to trust that JWT issuer and its claims. Prefer a trusted backend to validate the custom session and establish/issue a Supabase Auth user session for the mapped `auth.users.id`.
- Ensure the custom account maps to exactly one stable UUID in `auth.users`; use that UUID as `client_logs.user_id`. Never accept the mapping UUID from an untrusted client request without validating the custom session.
- Do not put a service-role key in an iOS app or agent/model environment.
- For agent reads, prefer a trusted backend that derives the user ID from its authenticated session and passes a short-lived user JWT. Do not trust a user ID selected by the model.
- If policies with these names already exist, `create policy` will fail; remove/rename the old policy intentionally before rerunning.

## Custom Login + Supabase Token Exchange Flow
1. The iOS app signs in to the existing custom authentication service over TLS.
2. The app sends its custom session token to a trusted backend endpoint. The backend validates signature, issuer, audience, expiry, and revocation with the custom auth provider; it must not trust a user ID supplied separately by the app.
3. The backend maps the validated identity to a stable Supabase Auth user (`auth.users.id`) and uses a supported Supabase Auth flow/provider integration to obtain a user-scoped Supabase session. Keep any admin/service-role credential exclusively on this backend. Do not invent or call an undocumented token-exchange endpoint; the exact mechanism depends on the custom provider and Supabase Auth configuration.
4. The app uses the Supabase session JWT with the publishable key for Data API requests. `auth.uid()` then resolves to the mapped `auth.users.id`, and the existing RLS policies restrict reads/inserts to that user's rows.
5. The telemetry agent should receive credentials only through a trusted runtime/backend, with the user scope derived from the validated session. Never expose custom or Supabase tokens in prompts, logs, source control, or tool output.

If the custom identity provider can issue JWTs with a stable subject and Supabase is configured to validate that issuer/JWKS and map the subject to the intended database identity, a direct third-party JWT approach may be possible. Validate that configuration and RLS behavior with Supabase documentation and an isolated test project before deployment. The publishable key alone cannot perform this exchange.

## Tasarım Avantajları
1. **Veri Bütünlüğü:** `level` kısıtlaması ile sadece `info`, `warn` ve `error` loglarına izin verilir. `detail` kolonunun her zaman bir JSON nesnesi olması (`jsonb_typeof`) garanti edilir.
2. **Güvenlik & İlişki:** `auth.users(id)` tablosuna `on delete CASCADE` ile bağlıdır ve RLS politikaları kullanıcı kapsamını sınırlar.
3. **Performans:** `user_id` ve `created_at desc` bileşik indeksi (`btree`) kullanıcıya göre son logların verimli sorgulanmasını destekler. Gerçek süre veri hacmi ve altyapı üzerinde ölçülmelidir.
