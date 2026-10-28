"""Read-only synthetic API server used by the paired telemetry evaluation.

The server speaks the same HTTP contract as the production management API for
the read paths the evaluation agent is allowed to use. It holds only generated
data: case identifiers are deterministic UUIDs derived from the task id, and
every row comes from `eval/fixtures/cases.json`.
"""

from __future__ import annotations

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY_BYTES = 64_000
DEFAULT_LIMIT = 50
MAX_LIMIT = 100
EVAL_NAMESPACE = "papertrack-eval"


def synthetic_case_id(task_id: str) -> str:
    """Return a stable, non-production UUID for a synthetic evaluation case."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{EVAL_NAMESPACE}-case:{task_id}"))


def synthetic_tool_key(task_id: str, owner_id: str) -> str:
    """Return a stable synthetic developer key for the fixture backend."""
    import hashlib

    digest = hashlib.sha256(f"{EVAL_NAMESPACE}-key:{task_id}:{owner_id}".encode("utf-8")).hexdigest()
    return f"tlk_{digest[:40]}"


class FixtureStore:
    """In-memory owner-scoped store of synthetic cases and telemetry rows."""

    def __init__(self, cases, logs, keys):
        self.cases = {case["id"]: case for case in cases}
        self.logs = {case_id: list(rows) for case_id, rows in logs.items()}
        self.keys = {}
        for key, value in keys.items():
            if isinstance(value, dict):
                self.keys[key] = {"owner_id": value["owner_id"], "role": value.get("role", "tool")}
            else:
                self.keys[key] = {"owner_id": value, "role": "tool"}
        self.requests = []

    def owner_for_key(self, key):
        entry = self.keys.get(key)
        return entry["owner_id"] if entry else None

    def role_for_key(self, key):
        entry = self.keys.get(key)
        return entry["role"] if entry else None

    def list_cases(self, owner_id, limit, state=None):
        rows = [
            case for case in self.cases.values()
            if case["owner_id"] == owner_id and (not state or case["state"] == state)
        ]
        rows.sort(key=lambda case: case["created_at"], reverse=True)
        return rows[:limit]

    def case_logs(self, owner_id, case_id, limit):
        case = self.cases.get(case_id)
        if case is None or case["owner_id"] != owner_id:
            return None
        rows = list(self.logs.get(case_id, []))
        rows.sort(key=lambda row: row["created_at"], reverse=True)
        return rows[:limit]

    def recent_logs(self, owner_id, limit, client_session_id=None):
        rows = []
        for case_id, case_rows in self.logs.items():
            case = self.cases.get(case_id)
            if case is None or case["owner_id"] != owner_id:
                continue
            for row in case_rows:
                if client_session_id and row.get("client_session_id") != client_session_id:
                    continue
                rows.append(row)
        rows.sort(key=lambda row: row["created_at"], reverse=True)
        return rows[:limit]


def _clamp_limit(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return min(max(number, 1), MAX_LIMIT)


def _make_handler(store: FixtureStore):
    class Handler(BaseHTTPRequestHandler):
        server_version = "FixtureBackend/1.0"

        def log_message(self, *args):
            return

        def _send(self, status, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized_owner(self):
            entry = store.keys.get(self._presented_key())
            return entry["owner_id"] if entry else None

        def _presented_key(self):
            header = self.headers.get("Authorization") or ""
            if not header.startswith("Bearer "):
                return ""
            return header[len("Bearer "):].strip()

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                self._send(413, {"error": "Request body too large."})
                return
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw or b"{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send(400, {"error": "Invalid JSON."})
                return
            if not isinstance(body, dict):
                self._send(400, {"error": "Invalid JSON."})
                return

            owner_id = self._authorized_owner()
            path = self.path.split("?")[0].rstrip("/")
            if owner_id is None:
                store.requests.append({"path": path, "owner": None, "status": 401})
                self._send(401, {"error": "Invalid tool key."})
                return

            if path.startswith("/api/tool/") and store.role_for_key(self._presented_key()) != "tool":
                store.requests.append({"path": path, "owner": owner_id, "status": 403})
                self._send(403, {"error": "This key type cannot access agent endpoints."})
                return

            if path == "/api/tool/cases":
                limit = _clamp_limit(body.get("limit", DEFAULT_LIMIT))
                state = body.get("state") or None
                rows = store.list_cases(owner_id, limit, state)
                store.requests.append({"path": path, "owner": owner_id, "status": 200})
                self._send(200, rows)
                return

            if path == "/api/tool/client-logs/recent":
                limit = _clamp_limit(body.get("limit", DEFAULT_LIMIT))
                session_id = body.get("client_session_id") or None
                rows = store.recent_logs(owner_id, limit, session_id)
                store.requests.append({"path": path, "owner": owner_id, "status": 200})
                self._send(200, rows)
                return

            parts = [part for part in path.split("/") if part]
            if len(parts) == 5 and parts[:3] == ["api", "tool", "cases"] and parts[4] == "logs":
                case_id = parts[3]
                limit = _clamp_limit(body.get("limit", DEFAULT_LIMIT))
                rows = store.case_logs(owner_id, case_id, limit)
                if rows is None:
                    store.requests.append({"path": path, "owner": owner_id, "status": 404})
                    self._send(404, {"error": "Case not found."})
                    return
                store.requests.append({"path": path, "owner": owner_id, "status": 200})
                self._send(200, rows)
                return

            store.requests.append({"path": path, "owner": owner_id, "status": 404})
            self._send(404, {"error": "Not found."})

    return Handler


class FixtureBackend:
    """Context manager that serves a FixtureStore on a loopback port."""

    def __init__(self, store: FixtureStore):
        self.store = store
        self._server = None
        self._thread = None

    def start(self) -> str:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(self.store))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def stop(self):
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None

    def __enter__(self):
        self.url = self.start()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.stop()
        return False
