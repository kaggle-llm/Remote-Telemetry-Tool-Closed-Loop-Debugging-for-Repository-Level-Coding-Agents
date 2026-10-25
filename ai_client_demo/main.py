"""Standalone AI-client simulation; config needs only domain and developer key."""

import os
from pathlib import Path

from telemetry_tool_poc.telemetry_tool import (
    fetch_recent_client_logs_for_agent,
    fetch_session_logs_for_agent,
    start_ai_session_for_agent,
    write_session_log_for_agent,
)


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
    missing = [name for name in ("TELEMETRY_DOMAIN", "TELEMETRY_TOOL_KEY") if not os.getenv(name)]
    if missing:
        raise SystemExit("Missing AI client environment variables: " + ", ".join(missing))

    # Start once per AI process/run. The generated session key stays in process memory.
    session_info = start_ai_session_for_agent(name="highlight-palette-debug")
    print("Started telemetry session:", session_info)

    write_session_log_for_agent(
        level="error",
        event="highlight_palette_presentation_failed",
        detail={
            "view": "HighlightPaletteView",
            "action": "open_palette",
            "failure_code": "missing_presentation_context",
            "source": "ai_client_demo",
        },
    )
    print(fetch_session_logs_for_agent(limit=20))
    print("Recent mbook client logs:")
    print(fetch_recent_client_logs_for_agent(limit=20))


if __name__ == "__main__":
    main()
