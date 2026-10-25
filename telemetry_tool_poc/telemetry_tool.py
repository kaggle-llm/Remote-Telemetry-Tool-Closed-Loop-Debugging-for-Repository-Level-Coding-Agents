"""Bounded, user-scoped client telemetry retrieval for an agent tool."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

MAX_LIMIT = 100
MAX_RESPONSE_BYTES = 256_000
ALLOWED_LEVELS = {"info", "warn", "error"}
SENSITIVE_KEYS = {"email", "phone", "token", "password", "authorization", "access_token"}


class TelemetryError(RuntimeError):
    """Raised when telemetry configuration or retrieval fails safely."""


class TelemetryAPIClient:
    """Calls the app API; the AI client never connects to Supabase directly."""

    def __init__(self, base_url, developer_key, timeout=10):
        self.base_url = base_url.rstrip("/")
        self.developer_key = developer_key
        self.timeout = timeout

    def post(self, path, payload):
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            urljoin(self.base_url + "/", path.lstrip("/")),
            data=body,
            headers={
                "Authorization": f"Bearer {self.developer_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError) as exc:
            # Do not include response body or credentials in tool-visible errors.
            raise TelemetryError("Telemetry service request failed.") from exc
        if len(payload) > MAX_RESPONSE_BYTES:
            raise TelemetryError("Telemetry response exceeded the configured size limit.")
        try:
            rows = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TelemetryError("Telemetry service returned invalid JSON.") from exc
        return rows

    def create_session(self, name):
        return self.post("/api/tool/sessions", {"name": name})

    def create_client_session(self, name, client_id):
        return self.post("/api/client/sessions", {"name": name, "client_id": client_id})

    def fetch_logs(self, session_key, limit):
        rows = self.post("/api/tool/logs", {"session_key": session_key, "limit": limit})
        if not isinstance(rows, list):
            raise TelemetryError("Telemetry service returned an unexpected response.")
        return rows

    def fetch_recent_client_logs(self, limit, client_session_id=None):
        rows = self.post("/api/tool/client-logs/recent", {"limit": limit, "client_session_id": client_session_id})
        if not isinstance(rows, list):
            raise TelemetryError("Telemetry service returned an unexpected response.")
        return rows

    def write_log(self, session_key, level, event, detail):
        return self.post("/api/tool/logs/write", {
            "session_key": session_key, "level": level, "event": event, "detail": detail,
        })


def _redact(value):
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if key.lower() in SENSITIVE_KEYS else _redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value[:100]]
    if isinstance(value, str):
        return value[:4000]
    return value


def _client_from_environment():
    base_url = os.getenv("TELEMETRY_DOMAIN")
    developer_key = os.getenv("TELEMETRY_TOOL_KEY")
    if not base_url or not developer_key:
        raise TelemetryError("Set TELEMETRY_DOMAIN and TELEMETRY_TOOL_KEY in the AI client environment.")
    if not base_url.startswith(("http://", "https://")):
        raise TelemetryError("TELEMETRY_DOMAIN must be an http(s) URL.")
    return TelemetryAPIClient(base_url, developer_key)


def fetch_client_logs(session_key: str, limit: int = 20) -> str:
    """Fetch logs belonging to the active AI session through the management API."""
    _validate_session_key(session_key)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be an integer between 1 and {MAX_LIMIT}.")
    rows = _client_from_environment().fetch_logs(session_key, limit)
    safe_rows = [_redact(row) for row in rows]
    return json.dumps({"count": len(safe_rows), "logs": safe_rows}, ensure_ascii=True)


def write_client_log(session_key: str, level: str, event: str, detail: dict) -> str:
    """Write one bounded telemetry event to the AI session via the management API."""
    _validate_session_key(session_key)
    if level not in ALLOWED_LEVELS:
        raise ValueError("level must be info, warn, or error.")
    if not isinstance(event, str) or not 1 <= len(event) <= 120:
        raise ValueError("event must be between 1 and 120 characters.")
    if not isinstance(detail, dict) or len(json.dumps(detail)) > 8000:
        raise ValueError("detail must be an object no larger than 8000 characters.")
    result = _client_from_environment().write_log(session_key, level, event, detail)
    return json.dumps(result, ensure_ascii=True)


def _validate_session_key(session_key: str) -> None:
    if not isinstance(session_key, str) or not session_key.startswith("tls_") or len(session_key) < 40:
        raise ValueError("A valid session key is required.")


def start_ai_session(name: str = "AI run") -> str:
    """Create a fresh session for this AI run using only the developer tool key."""
    if not isinstance(name, str) or not name.strip() or len(name) > 80:
        raise ValueError("Session name must be between 1 and 80 characters.")
    session = _client_from_environment().create_session(name.strip())
    key = session.get("session_key") if isinstance(session, dict) else None
    if not key:
        raise TelemetryError("Server did not return an AI session key.")
    _validate_session_key(key)
    os.environ["TELEMETRY_SESSION_KEY"] = key
    return json.dumps({"session_id": session.get("id"), "session_name": session.get("name"), "status": "started"})


def start_client_session(name: str = "mbook client") -> str:
    """Register an app/client session with the developer key; return its secret once."""
    if not isinstance(name, str) or not name.strip() or len(name) > 80:
        raise ValueError("Client session name must be between 1 and 80 characters.")
    client_id = os.getenv("TELEMETRY_CLIENT_ID", "").strip()
    if not client_id or len(client_id) > 100:
        raise TelemetryError("Set TELEMETRY_CLIENT_ID to a stable app/device identifier before creating a client session.")
    session = _client_from_environment().create_client_session(name.strip(), client_id)
    key = session.get("session_key") if isinstance(session, dict) else None
    if not key or not key.startswith("tcs_"):
        raise TelemetryError("Server did not return a client session key.")
    return json.dumps({"client_session_id": session.get("id"), "client_session_key": key})


def start_ai_session_for_agent(name: str = "AI run") -> str:
    """Agent-facing session creation; only the developer key is runtime-injected."""
    return start_ai_session(name=name)


def fetch_session_logs_for_agent(limit: int = 20) -> str:
    """Fetch logs for the session created at the beginning of this AI run."""
    session_key = os.getenv("TELEMETRY_SESSION_KEY", "")
    if not session_key:
        raise TelemetryError("Start an AI session before reading logs.")
    return fetch_client_logs(session_key=session_key, limit=limit)


def fetch_recent_client_logs_for_agent(limit: int = 50, client_session_id: str = "") -> str:
    """Fetch app/client events, optionally restricted to a client session ID."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be an integer between 1 and {MAX_LIMIT}.")
    rows = _client_from_environment().fetch_recent_client_logs(limit, client_session_id or None)
    safe_rows = [_redact(row) for row in rows]
    return json.dumps({"count": len(safe_rows), "logs": safe_rows}, ensure_ascii=True)


def diagnose_client_logs_for_agent(limit: int = 50, client_session_id: str = "") -> str:
    """Read client telemetry and ask the model/runtime to diagnose from evidence."""
    return fetch_recent_client_logs_for_agent(limit=limit, client_session_id=client_session_id)


def write_session_log_for_agent(level: str, event: str, detail: dict) -> str:
    """Write into the session created at the beginning of this AI run."""
    session_key = os.getenv("TELEMETRY_SESSION_KEY", "")
    if not session_key:
        raise TelemetryError("Start an AI session before writing logs.")
    return write_client_log(session_key, level, event, detail)


if __name__ == "__main__":
    raise SystemExit(
        "This module is an agent tool library. Run the separate ai_client_demo project "
        "to test writing and reading session logs."
    )
