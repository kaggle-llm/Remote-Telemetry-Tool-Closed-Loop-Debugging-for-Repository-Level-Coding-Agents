"""Diagnose which parts of the telemetry schema are actually present in Supabase.

The SQL migration is idempotent but a failed run can leave it half-applied.
This script probes PostgREST for every table, column, and RPC the server
depends on, so the mismatch is visible without guesswork.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_env(path):
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def request(url, method="GET", headers=None, body=None):
    request_obj = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request_obj, timeout=20) as response:
            response_body = response.read().decode("utf-8", "ignore")
            return response.status, response_body
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "ignore")
    except urllib.error.URLError as error:
        return 0, str(error)


TABLES = [
    "users", "app_sessions", "tool_api_keys", "telemetry_ingest_keys",
    "ai_sessions", "client_sessions", "client_logs", "debug_cases", "case_probes",
]

RPCS = {
    "read_session_logs": {"p_tool_key": "invalid", "p_session_key": "invalid", "p_limit": 1},
    "write_session_log": {"p_tool_key": "invalid", "p_session_key": "invalid", "p_level": "info", "p_event": "x", "p_detail": {}},
    "read_client_session_logs": {"p_tool_key": "invalid", "p_client_session_key": "invalid", "p_limit": 1},
    "read_recent_client_logs": {"p_tool_key": "invalid", "p_limit": 1},
    "write_client_session_log": {"p_tool_key": "invalid", "p_client_session_key": "invalid", "p_level": "info", "p_event": "x", "p_detail": {}},
    "write_ingest_client_log": {"p_ingest_key": "invalid", "p_client_session_key": "invalid", "p_level": "info", "p_event": "x", "p_detail": {}},
    "create_debug_case": {"p_ingest_key": "invalid", "p_client_session_key": "invalid", "p_title": "t", "p_user_report": "r"},
    "read_case_state": {"p_ingest_key": "invalid", "p_client_session_key": "invalid", "p_case_id": "11111111-2222-3333-4444-555555555555"},
    "set_case_instructions": {"p_tool_key": "invalid", "p_case_id": "11111111-2222-3333-4444-555555555555", "p_instructions": "x", "p_probes": [], "p_next_state": "instrumenting"},
    "read_case_logs": {"p_tool_key": "invalid", "p_case_id": "11111111-2222-3333-4444-555555555555", "p_limit": 1},
    "report_case_progress": {"p_ingest_key": "invalid", "p_client_session_key": "invalid", "p_case_id": "11111111-2222-3333-4444-555555555555", "p_report": "r"},
    "approve_case": {"p_ingest_key": "invalid", "p_client_session_key": "invalid", "p_case_id": "11111111-2222-3333-4444-555555555555", "p_approved": True},
    "transition_case": {"p_tool_key": "invalid", "p_case_id": "11111111-2222-3333-4444-555555555555", "p_next_state": "patch_ready"},
    "purge_case_logs": {"p_tool_key": "invalid", "p_case_id": "11111111-2222-3333-4444-555555555555"},
    "list_cases": {"p_tool_key": "invalid", "p_limit": 1, "p_state": None},
}


def main():
    load_env("../web_demo/.env")
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SECRET_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    print("=== tables ===")
    missing_tables = []
    for table in TABLES:
        status, body = request(f"{base}/rest/v1/{table}?select=*&limit=1", headers=headers)
        if status in (200, 206):
            print(f"  OK      {table}")
        else:
            print(f"  MISSING {table}  (HTTP {status})")
            missing_tables.append(table)

    print("=== client_logs columns ===")
    missing_columns = []
    for column in ("id", "case_id", "client_session_id", "ai_session_id", "level", "event", "detail"):
        status, body = request(
            f"{base}/rest/v1/client_logs?select={column}&limit=1", headers=headers
        )
        if status in (200, 206):
            print(f"  OK      client_logs.{column}")
        else:
            print(f"  MISSING client_logs.{column}  (HTTP {status})")
            missing_columns.append(column)

    print("=== rpc ===")
    missing_rpcs = []
    for rpc, body in RPCS.items():
        status, response = request(
            f"{base}/rest/v1/rpc/{rpc}", method="POST",
            headers={**headers, "Content-Type": "application/json"},
            body=json.dumps(body).encode("utf-8"),
        )
        if status == 404 and "PGRST202" in response:
            print(f"  MISSING {rpc}")
            missing_rpcs.append(rpc)
        elif status in (400, 401, 403):
            # The function exists and rejected our deliberately invalid arguments.
            print(f"  OK      {rpc}  (rejected invalid arguments, as expected)")
        else:
            print(f"  OK      {rpc}  (HTTP {status})")

    print()
    print(json.dumps({
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "missing_rpcs": missing_rpcs,
    }, indent=2))
    return 1 if (missing_tables or missing_columns or missing_rpcs) else 0


if __name__ == "__main__":
    sys.exit(main())