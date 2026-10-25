"""Simulate an AI run writing a client-error log and reading it back."""

import json
import os
from pathlib import Path

from telemetry_tool_poc.telemetry_tool import fetch_session_logs_for_agent, write_session_log_for_agent


def load_env_file():
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def main():
    load_env_file()
    required = ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "TELEMETRY_TOOL_KEY", "TELEMETRY_SESSION_KEY")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise SystemExit("Missing AI client environment variables: " + ", ".join(missing))

    write_result = write_session_log_for_agent(
        level="error",
        event="highlight_palette_presentation_failed",
        detail={
            "view": "HighlightPaletteView",
            "action": "open_palette",
            "failure_code": "missing_presentation_context",
            "source": "ai_client_demo",
        },
    )
    print("Write result:")
    print(json.dumps(json.loads(write_result), indent=2))

    logs_result = fetch_session_logs_for_agent(limit=20)
    print("Logs for this AI session:")
    print(json.dumps(json.loads(logs_result), indent=2))


if __name__ == "__main__":
    main()
