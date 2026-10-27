"""End-to-end demonstration of the 7-step HITL debugging loop.

This script drives the full loop against the live management API:
  1. normal state -> no client logs
  2. client reports the failure
  3. AI publishes runtime instrumentation probes
  4. AI tells the user what to try and waits for a re-check
  5. client reports the re-check result
  6. AI finalizes the fix
  7. client approves the fix -> AI cleans up the captured telemetry

It is a scripted proof-of-concept, not a model run. It never prints secrets.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from telemetry_tool_poc.telemetry_tool import (
    cleanup_case_for_agent,
    finalize_case_for_agent,
    fetch_case_logs_for_agent,
    list_debug_cases_for_agent,
    request_instrumentation_for_agent,
    await_user_recheck_for_agent,
)


def load_env(path):
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


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


def get(base, path, key):
    request = urllib.request.Request(
        base.rstrip("/") + path,
        headers={
            "Origin": "http://localhost:5173",
            "Authorization": f"Bearer {key}",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.status, json.loads(response.read())


def main():
    load_env("web_demo/.env")
    base = f"http://localhost:{os.getenv('PORT', '5175')}"
    ingest_key = os.environ.get("TELEMETRY_TEST_INGEST_KEY") or os.environ.get("TELEMETRY_INGEST_KEY")
    if not ingest_key:
        raise SystemExit("Set TELEMETRY_TEST_INGEST_KEY (or TELEMETRY_INGEST_KEY) to a user-owned ingest key.")
    tool_key = os.environ["TELEMETRY_TOOL_KEY"]
    os.environ["TELEMETRY_DOMAIN"] = base
    os.environ["TELEMETRY_TOOL_KEY"] = tool_key

    client_id = f"loop-demo-{os.urandom(4).hex()}"
    status, session = post(base, "/api/client/sessions", {
        "name": "loop-demo", "client_id": client_id,
    }, ingest_key)
    print(f"1. normal state -> client session created (status {status})")

    status, case = post(base, "/api/client/cases", {
        "session_key": session["session_key"],
        "title": "Highlight palette does not open",
        "user_report": "I select text and tap highlight, but the color palette never appears.",
    }, ingest_key)
    case_id = case["case_id"]
    print(f"2. client reported the failure -> case {case_id[:8]}… state={case['state']}")

    probes = [{
        "probe_id": "palette_context",
        "target": "HighlightPaletteView.presentPalette",
        "capture": {"presentation_context": "true", "viewmodel_state": "true"},
        "level": "warn",
    }]
    result = json.loads(request_instrumentation_for_agent(
        case_id,
        "Reproduce the highlight flow and confirm the palette opens after the guard is applied.",
        probes,
    ))
    print(f"3. AI published instrumentation probes -> state={result['state']}")

    result = json.loads(await_user_recheck_for_agent(
        case_id,
        "Please select text and tap highlight again. The palette should now open.",
        probes,
    ))
    print(f"4. AI told the user what to try -> state={result['state']}")

    status, progress = post(base, "/api/client/cases/" + case_id + "/report", {
        "session_key": session["session_key"],
        "report": "Re-checked: the palette now opens and shows the yellow highlight.",
    }, ingest_key)
    print(f"5. client reported the re-check -> state={progress['state']}")

    result = json.loads(finalize_case_for_agent(case_id))
    print(f"6. AI finalized the fix -> state={result['state']}")

    status, approved = post(base, "/api/client/cases/" + case_id + "/approve", {
        "session_key": session["session_key"],
        "approved": True,
    }, ingest_key)
    print(f"7. client approved the fix -> state={approved['state']}")

    logs = json.loads(fetch_case_logs_for_agent(case_id, limit=50))
    print(f"   pre-cleanup case-scoped logs: {logs['count']}")

    cleanup = json.loads(cleanup_case_for_agent(case_id))
    print(f"   AI cleaned up telemetry -> state={cleanup['state']} deleted_logs={cleanup['deleted_logs']}")

    remaining = json.loads(list_debug_cases_for_agent(limit=50, state="resolved"))
    found = any(c["id"] == case_id for c in remaining["cases"])
    print(f"   case is now in the resolved list: {found}")
    print("secret values printed: no")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        print("HTTP error:", error.code, error.read().decode("utf-8", "ignore"))
        sys.exit(1)