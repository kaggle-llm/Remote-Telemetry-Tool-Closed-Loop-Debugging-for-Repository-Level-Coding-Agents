"""Secret-safe smoke test for client session ingest and AI retrieval."""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from telemetry_tool_poc.telemetry_tool import fetch_recent_client_logs_for_agent


def load_env(path):
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            os.environ[name.strip()] = value.strip().strip("\"'")


def post(base, path, payload, key):
    request = urllib.request.Request(
        base.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Origin": "http://localhost:5173",
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.status, json.loads(response.read())


def main():
    load_env("web_demo/.env")
    base = f"http://localhost:{os.getenv('PORT', '5175')}"
    ingest_key = os.environ["TELEMETRY_TEST_INGEST_KEY"]
    tool_key = os.environ["TELEMETRY_TOOL_KEY"]
    client_id = f"verification-{os.urandom(6).hex()}"

    status, session = post(base, "/api/client/sessions", {
        "name": "ingest-verification", "client_id": client_id,
    }, ingest_key)
    print("client session creation:", status)

    status, created = post(base, "/api/client/logs", {
        "session_key": session["session_key"],
        "level": "info",
        "event": "highlight_completed",
        "detail": {"source": "verification", "color_id": "yellow"},
        "user_agent": "verification-client",
    }, ingest_key)
    print("client log insertion:", status)

    try:
        post(base, "/api/tool/client-logs/recent", {"limit": 10}, ingest_key)
        raise SystemExit("Ingest key unexpectedly accessed an AI-only endpoint.")
    except urllib.error.HTTPError as error:
        print("ingest key blocked from AI log-read endpoint:", error.code == 401)

    os.environ["TELEMETRY_DOMAIN"] = base
    os.environ["TELEMETRY_TOOL_KEY"] = tool_key
    logs = json.loads(fetch_recent_client_logs_for_agent(20, session["id"]))
    found = any(row.get("event") == "highlight_completed" for row in logs["logs"])
    print("AI tool retrieved client event:", found)
    print("AI tool result count:", logs["count"])
    print("secret values printed: no")
    if not found:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        print("HTTP error:", error.code)
        raise SystemExit(1)
