# Remote Telemetry Tool PoC

This prototype provides a bounded Python tool for retrieving client log events. It supports a local mock mode by default and an optional Supabase PostgREST mode. It is not yet wired to the Kaggle competition harness or verified as a native ADK `agent.yaml` format.

## Browser demo

`web_demo/` is a browser-based presentation mock. It simulates the iOS highlight-palette failure and displays a local in-memory telemetry event; it does not require Supabase credentials, account creation, email confirmation, or a network connection. Events disappear when the page reloads. The Python tool and schema remain the separate Supabase integration prototype.

Run the Vite project from `web_demo/`:

```powershell
npm install
npm run dev
```

Open the URL printed by Vite (normally `http://localhost:5173/`) and click **Paleti açmayı dene ve logla** to demonstrate the flow. No Supabase project setup is needed for the presentation mock.

This presentation mock does not write to Supabase. For live database integration, use the Python tool path and follow the Supabase schema, RLS, and trusted-auth setup documented below. Do not put service-role secrets in browser code.

## Requirements

- Python 3.10 or newer
- No third-party packages are required for the mock mode or tests
- A Supabase project is required only for live mode

## Run the mock demo

From this directory:

```powershell
$env:TELEMETRY_MODE = "mock"
python telemetry_tool.py
```

Run tests:

```powershell
python -m unittest -v
```

## Optional live Supabase mode

Set environment variables in the trusted agent host process, not in the iOS app or model prompt:

```powershell
$env:TELEMETRY_MODE = "supabase"
$env:SUPABASE_URL = "https://your-project.supabase.co"
$env:SUPABASE_ANON_KEY = "your-project-anon-key"
$env:SUPABASE_ACCESS_TOKEN = "short-lived-authenticated-user-jwt"
python telemetry_tool.py
```

The authenticated JWT is sent as the PostgREST bearer token, so RLS must be enabled and policies must restrict rows to the authenticated user. The tool also adds a `user_id` filter, but a model-supplied ID is not an authorization mechanism: in a real host, inject `user_id` from authenticated server-side session state and do not expose it as a model-controlled argument. Never use or embed the Supabase service-role key in a client app or give it to the model. Use a short-lived user JWT with only the required table permissions.

## Custom login integration

For an existing custom login system, the intended architecture is:

`iOS app -> custom auth -> trusted backend validates custom session -> backend maps identity to auth.users.id and establishes a Supabase Auth user session -> iOS/API calls use the Supabase JWT under RLS`

The custom token is not automatically a Supabase access token. The exchange/provider setup is project-specific; use a documented Supabase Auth integration rather than assuming the publishable key can exchange tokens. Keep any admin credential only on the backend. See `SUPABASE_SCHEMA.md` for details and security constraints.

Required table columns: `id`, `user_id`, `session_id`, `level`, `event`, `detail`, `user_agent`, `created_at`.

## Tool contract

`fetch_client_logs(user_id, limit=20, session_id="", level="", since_minutes=1440)` returns JSON with a `count` and `logs`. Limits are enforced, fields are selected explicitly, output is redacted and bounded, and no arbitrary SQL is accepted. Log content remains untrusted input and must not be followed as instructions.

## Security work before production

- Configure and test Supabase RLS policies for both client inserts and agent reads.
- Prefer a trusted backend that derives the user scope from the authenticated session, rather than accepting a model-provided `user_id`.
- Define consent, retention/deletion, rate limits, abuse handling, and event redaction at ingestion.
- Confirm the schema foreign key matches the project's `auth.users(id)` identity model.
- Add audit logging and integration tests using a non-production Supabase project before handling real user telemetry.
