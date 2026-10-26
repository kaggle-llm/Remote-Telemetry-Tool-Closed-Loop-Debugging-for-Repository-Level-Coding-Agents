# AI Client Demo

## Generate prototype keys

Run `python ai_client_demo/generate_keys.py` from the repository root only if you need a new `APP_SESSION_SECRET`. Ingest keys are user-owned and generated in the management dashboard; they are not global backend environment variables. The server's existing `TELEMETRY_TOOL_KEY` stays server-side for AI tool sessions and must never be copied into a client app.

In the web dashboard, create a **user-owned ingest key** (not a developer key), then set it as `VITE_TELEMETRY_INGEST_KEY` in the client app environment. Set a stable `VITE_TELEMETRY_CLIENT_ID` for that app/device installation. Vite embeds `VITE_*` values in browser assets, so users can extract this key. It is restricted to client-session creation and log insertion; it cannot read logs or manage keys. Revoke it after testing if exposed. Do not treat it as a production secret.

This is a separate example project representing the AI agent/runtime. Its `.env` contains only the management API domain and developer tool key. At the beginning of each process/run, the AI tool calls `start_ai_session`; the server creates a fresh session and the tool keeps the session secret in process memory. The AI then writes a simulated iOS highlight-palette error and fetches logs for that session. Supabase URL/keys and session keys are not configured in this client project. The current launcher starts one session per process; keep the same process alive for one AI run.

## Setup

1. In `web_demo`, sign in and create a developer tool key. Copy it once.
2. Copy `.env.example` to `.env` in this project. Set `TELEMETRY_DOMAIN` to `http://localhost:5173/` and `TELEMETRY_TOOL_KEY` to the developer key. Do not commit `.env` or paste the key into model prompts.
3. From the project root, run:

```powershell
python -m ai_client_demo.main
```

The client invokes the same agent-facing functions registered in `telemetry_tool_poc/agent.yaml`: `start_ai_session_for_agent`, `write_session_log_for_agent`, `fetch_session_logs_for_agent`, and `fetch_recent_client_logs_for_agent`. Device/client sessions are separate from AI sessions; the AI reads client events by owner and optional client session ID. Keep the AI process alive for the duration of one run so its in-memory AI session key stays associated with that run.

Use a newly generated tool key. Any key pasted into a chat, issue, source file, or log should be revoked in the dashboard and replaced.
