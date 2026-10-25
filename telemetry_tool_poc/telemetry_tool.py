"""Bounded, user-scoped client telemetry retrieval for an agent tool."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_LIMIT = 100
MAX_RESPONSE_BYTES = 256_000
ALLOWED_LEVELS = {"info", "warn", "error"}
SENSITIVE_KEYS = {"email", "phone", "token", "password", "authorization", "access_token"}


class TelemetryError(RuntimeError):
    """Raised when telemetry configuration or retrieval fails safely."""


class SupabaseTelemetryClient:
    """Calls narrowly scoped RPCs; raw keys are never sent to the model output."""

    def __init__(self, url, publishable_key, timeout=10):
        self.url = url.rstrip("/")
        self.publishable_key = publishable_key
        self.timeout = timeout

    def rpc(self, name, payload):
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.url}/rest/v1/rpc/{name}",
            data=body,
            headers={
                "apikey": self.publishable_key,
                "Authorization": f"Bearer {self.publishable_key}",
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

    def fetch_logs(self, tool_key, session_key, limit):
        rows = self.rpc("read_session_logs", {
            "p_tool_key": tool_key,
            "p_session_key": session_key,
            "p_limit": limit,
        })
        if not isinstance(rows, list):
            raise TelemetryError("Telemetry service returned an unexpected response.")
        return rows

    def write_log(self, tool_key, session_key, level, event, detail):
        return self.rpc("write_session_log", {
            "p_tool_key": tool_key,
            "p_session_key": session_key,
            "p_level": level,
            "p_event": event,
            "p_detail": detail,
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
    mode = os.getenv("TELEMETRY_MODE", "supabase").lower()
    if mode != "supabase":
        raise TelemetryError("TELEMETRY_MODE must be 'supabase' for agent tool calls.")
    url = os.getenv("SUPABASE_URL")
    publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY")
    if not all((url, publishable_key)):
        raise TelemetryError("Live mode requires SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY.")
    if "service_role" in publishable_key.lower() or "secret" in publishable_key.lower():
        raise TelemetryError("Only a Supabase publishable key may be used by this tool.")
    return SupabaseTelemetryClient(url, publishable_key)


def fetch_client_logs(tool_key: str, session_key: str, limit: int = 20) -> str:
    """Fetch logs scoped to the owner and AI session proven by both generated keys."""
    _validate_credentials(tool_key, session_key)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be an integer between 1 and {MAX_LIMIT}.")
    rows = _client_from_environment().fetch_logs(tool_key, session_key, limit)
    safe_rows = [_redact(row) for row in rows]
    return json.dumps({"count": len(safe_rows), "logs": safe_rows}, ensure_ascii=True)


def write_client_log(tool_key: str, session_key: str, level: str, event: str, detail: dict) -> str:
    """Write one bounded telemetry event, linked server-side to the verified AI session."""
    _validate_credentials(tool_key, session_key)
    if level not in ALLOWED_LEVELS:
        raise ValueError("level must be info, warn, or error.")
    if not isinstance(event, str) or not 1 <= len(event) <= 120:
        raise ValueError("event must be between 1 and 120 characters.")
    if not isinstance(detail, dict) or len(json.dumps(detail)) > 8000:
        raise ValueError("detail must be an object no larger than 8000 characters.")
    result = _client_from_environment().write_log(tool_key, session_key, level, event, detail)
    return json.dumps(result, ensure_ascii=True)


def _validate_credentials(tool_key: str, session_key: str) -> None:
    if not isinstance(tool_key, str) or not tool_key.startswith("tlk_") or len(tool_key) < 40:
        raise ValueError("A valid tool key is required.")
    if not isinstance(session_key, str) or not session_key.startswith("tls_") or len(session_key) < 40:
        raise ValueError("A valid session key is required.")


def fetch_session_logs(tool_key: str, session_key: str, limit: int = 20) -> str:
    """Fetch session-scoped logs; credentials are injected by the trusted runtime."""
    if not tool_key or not session_key:
        raise TelemetryError("Configure TELEMETRY_TOOL_KEY and TELEMETRY_SESSION_KEY in the trusted runtime.")
    return fetch_client_logs(tool_key=tool_key, session_key=session_key, limit=limit)


def fetch_session_logs_for_agent(limit: int = 20) -> str:
    """Agent-facing wrapper: the model can choose the limit, never the credentials."""
    return fetch_session_logs(
        tool_key=os.getenv("TELEMETRY_TOOL_KEY", ""),
        session_key=os.getenv("TELEMETRY_SESSION_KEY", ""),
        limit=limit,
    )


def write_session_log_for_agent(level: str, event: str, detail: dict) -> str:
    """Agent-facing writer with credentials injected from the runtime environment."""
    tool_key = os.getenv("TELEMETRY_TOOL_KEY", "")
    session_key = os.getenv("TELEMETRY_SESSION_KEY", "")
    if not tool_key or not session_key:
        raise TelemetryError("Configure TELEMETRY_TOOL_KEY and TELEMETRY_SESSION_KEY in the trusted runtime.")
    return write_client_log(tool_key, session_key, level, event, detail)


if __name__ == "__main__":
    raise SystemExit(
        "This module is an agent tool library. Run the separate ai_client_demo project "
        "to test writing and reading session logs."
    )
