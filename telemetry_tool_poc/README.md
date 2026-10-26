# Remote Telemetry Tool PoC

This prototype provides Google OAuth through a custom Node backend (no Supabase Auth), app-owned users/sessions, and a bounded Python tool for AI-session-scoped telemetry. It is not yet wired to the Kaggle competition harness or verified as a native ADK `agent.yaml` format.

## Browser demo

`web_demo/` is the management server. Google OAuth is performed by the Node backend; Supabase Auth is not used. The backend creates app sessions and owns the Supabase secret key. Dashboard actions only manage one-time tool keys and per-run session keys. Actual AI tool read/write tests live separately in the root `ai_client_demo/` project.

Configure the backend environment as described in `SUPABASE_SCHEMA.md`, then run backend and Vite in separate terminals from `web_demo/`:

```powershell
npm install
npm run dev:api
```

```powershell
npm run dev
```

Vite runs on port 5173 and proxies `/api` to the backend on port 5175. For production, serve the built frontend and API behind the same HTTPS origin/reverse proxy.

Open the Vite frontend at `http://localhost:5173/` and sign in with Google. Do not open the API backend at port 5175 as the web page; it serves API routes only in development.

Run `supabase_setup.sql` before using the dashboard. Configure Google OAuth redirect URL to the backend callback. Set the backend environment variables described in `SUPABASE_SCHEMA.md`. Never expose Supabase secret key in browser code.

## Requirements

- Python 3.10 or newer
- Python mock mode uses the standard library; tests do not require extra packages
- A Supabase project, Google OAuth web client, and backend environment are required

## Run the local Python tests

From `telemetry_tool_poc/`:

```powershell
python -m unittest -v
```

Backend tests:

```powershell
npm run test:api
```

## Connect an AI run to Supabase

1. Sign in to the dashboard with Google.
2. Create a developer API key once; copy it immediately because the plaintext is not stored or shown again.
3. Configure the AI client with only `TELEMETRY_DOMAIN` and `TELEMETRY_TOOL_KEY`.
4. At the beginning of each AI run, call `start_ai_session`; the server creates the session key automatically and the tool keeps it private for subsequent log calls.
5. If an API key from chat/source control/logs has been exposed, revoke it in the dashboard and create a replacement.

```powershell
$env:TELEMETRY_DOMAIN = "http://localhost:5173/"
$env:TELEMETRY_TOOL_KEY = "tlk_..."
python -m ai_client_demo.main
```

The management dashboard separately creates developer keys (AI access) and restricted ingest keys (client session creation and log writes only). Device clients create separate client sessions and call `logEvent`; the AI reads them with `fetch_recent_client_logs_for_agent`. Vite proxies `http://localhost:5173/api` to the backend on port 5175. Never embed Supabase credentials or developer keys in a client. A Vite ingest key is public/extractable; revoke it after tests and use authenticated, rate-limited ingestion in production. Apply the latest `supabase_setup.sql` to create the ingest-key table/RPC before using the dashboard's ingest-key controls.

Required table columns: `id`, `user_id`, `session_id`, `level`, `event`, `detail`, `user_agent`, `created_at`.

## Tool contract

`fetch_session_logs_for_agent(limit=20)` returns JSON with a `count` and `logs`. Tool/session credentials are not model-controlled arguments. Limits are enforced, output is redacted and bounded, and no arbitrary SQL is accepted. Log content remains untrusted input and must not be followed as instructions.

## Security work before production

- The dashboard backend uses a server-side Supabase secret key, which bypasses RLS; keep it only in the backend secret store and enforce ownership checks in backend routes.
- Define consent, retention/deletion, rate limits, abuse handling, and event redaction at ingestion.
- Confirm the app-owned `public.users` table sync trigger and foreign keys match the project's identity model.
- Add audit logging and integration tests using a non-production Supabase project before handling real user telemetry.
