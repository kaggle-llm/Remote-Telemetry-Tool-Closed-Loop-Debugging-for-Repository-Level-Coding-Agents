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

4. Start both the backend (`npm run dev:api`, port 5175) and Vite frontend (`npm run dev`, normally port 5173). Open the Vite origin (`APP_ORIGIN`), not the backend port; OAuth callback redirects there after login. The secret key is **server-only**; never put it in Vite `VITE_*` values, browser code, the mobile app, or an AI prompt. Production must use HTTPS and a managed secret store.

## Identity and session model

- Google authenticates the human. Backend validates OAuth state, token signature/audience and verified email, then upserts the app-owned user via its server-only Supabase key.
- `public.users.google_sub` is the stable Google identity; `public.users.id` is the application's own UUID.
- `public.app_sessions` stores a hash of a random opaque session ID, expiry, and user ID. The signed `tl_session` cookie is HttpOnly, SameSite=Lax, Secure in production.
- The app does not issue Supabase Auth JWTs and does not use `auth.users`.
- Backend service key access bypasses RLS. Authorization is enforced by backend route scoping; protect the backend, add rate limits/audit logging, and never expose the key.

## AI key/session scope

The dashboard generates high-entropy `tlk_...` developer keys. Each AI process calls `start_ai_session` using that developer key; the backend then generates a fresh `tls_...` session key. Only SHA-256 hashes/prefixes are persisted. The AI tool keeps the raw session key in process memory, while read/write requests send it with the developer key to the backend. The backend resolves the owner and enforces that the session belongs to that developer key; each log is linked to `ai_sessions.id`.

For the Python client, configure only `TELEMETRY_DOMAIN` (`http://localhost:5173/`, with Vite proxying `/api` to port 5175) and `TELEMETRY_TOOL_KEY`. Register `start_ai_session_for_agent` at run start, followed by `fetch_session_logs_for_agent` and `write_session_log_for_agent`. The model sees only the created session ID/status, never the session secret. Supabase URL and keys stay exclusively on the management backend.

## Existing database warning

The setup file targets a new/custom-auth schema. If the existing `client_logs` table or user rows were created with a foreign key to `auth.users`, do not blindly rerun it: map existing users to Google `sub` values, migrate UUID references and existing logs first. Back up the database and test the migration on a staging project. Do not delete production data to make the schema apply.
