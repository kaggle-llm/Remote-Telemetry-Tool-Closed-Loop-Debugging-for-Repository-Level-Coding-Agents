# Custom Google OAuth and Application Users

This configuration does **not** use Supabase Auth. Google OAuth is performed by the Node backend using Google's OAuth client. The backend verifies Google's signed ID token, creates/updates `public.users`, and creates an opaque application session stored as a hash in `public.app_sessions`. The browser receives only an HttpOnly, SameSite cookie.

## Setup

1. Apply the latest `supabase_setup.sql` in Supabase SQL Editor. It creates app-owned users, `client_logs`, app sessions, tool keys, AI sessions, scoped log RPCs, and the required `service_role` table grants. The SQL creates `public.client_logs` if it does not exist.
2. Create a Google OAuth web client in Google Cloud. Set the authorized redirect URI to `GOOGLE_CALLBACK_URL` (for local development: `http://localhost:5174/api/auth/google/callback`).
3. Copy `web_demo/.env.example` to `web_demo/.env` and set the real backend environment values there. The server loads `.env` via `dotenv`; `.env` is ignored by Git. Never commit or share the populated file.

```text
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_CALLBACK_URL=http://localhost:5175/api/auth/google/callback
APP_SESSION_SECRET=<at-least-32-random-characters>
APP_ORIGIN=http://localhost:5173
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=<server-only-secret-key>
```

4. Start both the backend (`npm run dev:api`, port 5175) and Vite frontend (`npm run dev`, normally port 5173). Open the Vite origin (`APP_ORIGIN`), not the backend port; OAuth callback redirects there after login. The secret key is **server-only**; never put it in Vite `VITE_*` values, browser code, a client app, or an AI prompt. Production must use HTTPS and a managed secret store.

## Identity and session model

- Google authenticates the human. Backend validates OAuth state, token signature/audience and verified email, then upserts the app-owned user via its server-only Supabase key.
- `public.users.google_sub` is the stable Google identity; `public.users.id` is the application's own UUID.
- `public.app_sessions` stores a hash of a random opaque session ID, expiry, and user ID. The signed `tl_session` cookie is HttpOnly, SameSite=Lax, Secure in production.
- The app does not issue Supabase Auth JWTs and does not use `auth.users`.
- Backend service key access bypasses RLS. Authorization is enforced by backend route scoping; protect the backend, add rate limits/audit logging, and never expose the key.

## AI key/session scope

The dashboard generates separate high-entropy `tlk_...` developer keys and `tli_...` ingest keys. Developer keys allow AI tools to create AI sessions and read logs. Ingest keys are restricted to creating client sessions and writing events; only SHA-256 hashes/prefixes are persisted. AI runs call `start_ai_session` using the developer key and receive a separate `tls_...` session held in tool process memory. Device sessions use their own `tcs_...` key. Every log is linked to either `ai_sessions.id` or `client_sessions.id`.

The dashboard requires the `telemetry_ingest_keys` table and write-ingest RPC from the latest `supabase_setup.sql`; apply that SQL migration before creating ingest keys. Developer and ingest key secrets are displayed only once and can be revoked in the dashboard.

For the Python client, configure only `TELEMETRY_DOMAIN` (`http://localhost:5173/`, with Vite proxying `/api` to port 5175) and `TELEMETRY_TOOL_KEY`. Register `start_ai_session_for_agent` at run start, followed by `fetch_session_logs_for_agent` and `write_session_log_for_agent`. The model sees only the created session ID/status, never the session secret. Supabase URL and keys stay exclusively on the management backend.

## Real app/client telemetry

The client starts its own `client_sessions` record through `/api/client/sessions`; this is separate from an AI run. App events are stored with `client_session_id`. The AI tool reads recent client events through `/api/tool/client-logs/recent`, optionally filtered by the client session UUID. AI and device sessions are therefore not conflated.

An iOS/web client uses its same-origin `/api` route to the management API. A signed-in user generates an ingest key in the dashboard and configures it as `VITE_TELEMETRY_INGEST_KEY` with a stable `VITE_TELEMETRY_CLIENT_ID`. The server validates that key against `telemetry_ingest_keys`; the RPC derives the owner directly from the ingest key. The client never receives a developer key or Supabase credentials. Frontend environment keys are extractable, so ingest keys are restricted, revocable credentials; rate-limit them and avoid treating them as secrets. For production, use per-install authentication and abuse controls.

## Existing database warning

The setup file targets a new/custom-auth schema. If the existing `client_logs` table or user rows were created with a foreign key to `auth.users`, do not blindly rerun it: map existing users to Google `sub` values, migrate UUID references and existing logs first. Back up the database and test the migration on a staging project. Do not delete production data to make the schema apply.
