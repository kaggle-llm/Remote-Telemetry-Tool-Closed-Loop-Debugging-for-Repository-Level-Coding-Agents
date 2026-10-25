# Remote Telemetry Tool PoC

This prototype provides Google OAuth through a custom Node backend (no Supabase Auth), app-owned users/sessions, and a bounded Python tool for AI-session-scoped telemetry. It is not yet wired to the Kaggle competition harness or verified as a native ADK `agent.yaml` format.

## Browser demo

`web_demo/` is the dashboard prototype. Google OAuth is performed by the Node backend; Supabase Auth is not used. The backend creates app sessions and owns the Supabase secret key. Dashboard actions manage one-time tool keys, per-run session keys, and scoped test logs.

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

From this directory:

```powershell
$env:TELEMETRY_MODE = "supabase"
python telemetry_tool.py
```

Run tests:

```powershell
python -m unittest -v
```

Backend tests:

```powershell
npm run test:api
```

## Optional live Supabase mode

Set credentials in the trusted agent host process/secret manager, not in a prompt:

```powershell
$env:TELEMETRY_MODE = "supabase"
$env:SUPABASE_URL = "https://your-project.supabase.co"
$env:SUPABASE_PUBLISHABLE_KEY = "sb_publishable_..."
$env:TELEMETRY_TOOL_KEY = "tlk_..."
$env:TELEMETRY_SESSION_KEY = "tls_..."
python telemetry_tool.py
```

The tool calls `read_session_logs` and `write_session_log`; both credentials are validated and bound to one user/session inside Postgres. Register `telemetry_tool.fetch_session_logs_for_agent` with `limit` as the model argument; its credentials are injected from environment. For writes, register `telemetry_tool.write_session_log_for_agent` with only `level`, `event`, and `detail` as model arguments. Never use or embed a Supabase secret/service-role key in the client or expose tool/session keys to model-generated arguments or logs.

Required table columns: `id`, `user_id`, `session_id`, `level`, `event`, `detail`, `user_agent`, `created_at`.

## Tool contract

`fetch_session_logs_for_agent(limit=20)` returns JSON with a `count` and `logs`. Tool/session credentials are not model-controlled arguments. Limits are enforced, output is redacted and bounded, and no arbitrary SQL is accepted. Log content remains untrusted input and must not be followed as instructions.

## Security work before production

- Configure and test Supabase RLS policies for both client inserts and agent reads.
- Prefer a trusted backend that derives the user scope from the authenticated session, rather than accepting a model-provided `user_id`.
- Define consent, retention/deletion, rate limits, abuse handling, and event redaction at ingestion.
- Confirm the app-owned `public.users` table sync trigger and foreign keys match the project's identity model.
- Add audit logging and integration tests using a non-production Supabase project before handling real user telemetry.
