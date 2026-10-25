# Custom Google OAuth and Application Users

This configuration does **not** use Supabase Auth. Google OAuth is performed by the Node backend using Google's OAuth client. The backend verifies Google's signed ID token, creates/updates `public.users`, and creates an opaque application session stored as a hash in `public.app_sessions`. The browser receives only an HttpOnly, SameSite cookie.

## Setup

1. Apply `supabase_setup.sql` in Supabase SQL Editor. It creates app-owned users, `client_logs`, app sessions, tool keys, AI sessions, and scoped log RPCs. The SQL creates `public.client_logs` if it does not exist.
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

4. Start the backend and Vite frontend. The secret key is **server-only**; never put it in Vite `VITE_*` values, browser code, the mobile app, or an AI prompt. Production must use HTTPS and a managed secret store.

## Identity and session model

- Google authenticates the human. Backend validates OAuth state, token signature/audience and verified email.
- `public.users.google_sub` is the stable Google identity; `public.users.id` is the application's own UUID.
- `public.app_sessions` stores a hash of a random opaque session ID, expiry, and user ID. The signed `tl_session` cookie is HttpOnly, SameSite=Lax, Secure in production.
- The app does not issue Supabase Auth JWTs and does not use `auth.users`.
- Backend service key access bypasses RLS. Authorization is enforced by backend route scoping; protect the backend, add rate limits/audit logging, and never expose the key.

## AI key/session scope

The dashboard generates high-entropy `tlk_...` tool keys and `tls_...` AI-session keys. Only SHA-256 hashes/prefixes are persisted. The AI process calls `read_session_logs` / `write_session_log` with the publishable project key plus both secrets. Postgres resolves the user from the tool key and requires the session key to belong to that same user; each log is linked to `ai_sessions.id`.

For the Python tool, put `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `TELEMETRY_TOOL_KEY`, and `TELEMETRY_SESSION_KEY` in the AI runtime's secret store/environment. Register `telemetry_tool.fetch_session_logs_for_agent` and `telemetry_tool.write_session_log_for_agent`; expose only non-secret log arguments to the model. The dashboard's server secret is never passed to the AI tool.

## Existing database warning

The setup file targets a new/custom-auth schema. If the existing `client_logs` table or user rows were created with a foreign key to `auth.users`, do not blindly rerun it: map existing users to Google `sub` values, migrate UUID references and existing logs first. Back up the database and test the migration on a staging project. Do not delete production data to make the schema apply.
