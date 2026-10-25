# AI Client Demo

This is a separate example project representing the AI agent/runtime. It writes a simulated iOS highlight-palette error to Supabase and fetches only logs belonging to the configured AI session. `web_demo` remains the management server for Google login and key/session creation; it does not execute AI log tests.

## Setup

1. In `web_demo`, sign in and create a tool API key.
2. Create a dedicated AI session key for this run.
3. Copy `.env.example` to `.env` in this project and fill the Supabase project URL, publishable key, tool key, and session key. Do not commit `.env` or paste keys into model prompts.
4. From the project root, run:

```powershell
python -m ai_client_demo.main
```

The client invokes the same agent-facing functions registered in `telemetry_tool_poc/agent.yaml`: `write_session_log_for_agent` and `fetch_session_logs_for_agent`. The tool and session keys are injected through environment variables and are not function arguments visible to the model.

Use a newly generated tool key. Any key pasted into a chat, issue, source file, or log should be revoked in the dashboard and replaced.
