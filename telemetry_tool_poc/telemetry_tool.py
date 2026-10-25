"""Bounded, user-scoped client telemetry retrieval for an agent tool."""

import json
import os
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MAX_LIMIT = 100
MAX_RESPONSE_BYTES = 256_000
ALLOWED_LEVELS = {"info", "warn", "error"}
SENSITIVE_KEYS = {"email", "phone", "token", "password", "authorization", "access_token"}


class TelemetryError(RuntimeError):
    """Raised when telemetry configuration or retrieval fails safely."""


class MockTelemetryClient:
    def __init__(self, logs=None):
        self.logs = logs or [{
            "id": 1,
            "user_id": "00000000-0000-0000-0000-000000000001",
            "session_id": "demo-session",
            "level": "error",
            "event": "highlight_palette_presentation_failed",
            "detail": {
                "view": "HighlightPaletteView",
                "action": "open_palette",
                "failure_code": "missing_presentation_context",
                "app_version": "1.2.0",
                "os_version": "iOS 18",
            },
            "user_agent": "PaperTrack-demo",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }]

    def fetch_logs(self, user_id, limit, session_id=None, level=None, since_minutes=1440):
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        rows = []
        for row in self.logs:
            timestamp = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            if row["user_id"] != user_id or timestamp < cutoff:
                continue
            if session_id and row["session_id"] != session_id:
                continue
            if level and row["level"] != level:
                continue
            rows.append(row)
        return sorted(rows, key=lambda item: item["created_at"], reverse=True)[:limit]


class SupabaseTelemetryClient:
    """Uses the caller's user JWT so Supabase RLS remains authoritative."""

    def __init__(self, url, anon_key, access_token, timeout=10):
        self.url = url.rstrip("/")
        self.anon_key = anon_key
        self.access_token = access_token
        self.timeout = timeout

    def fetch_logs(self, user_id, limit, session_id=None, level=None, since_minutes=1440):
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=since_minutes)).isoformat()
        params = {
            "select": "id,user_id,session_id,level,event,detail,user_agent,created_at",
            "user_id": f"eq.{user_id}",
            "created_at": f"gte.{cutoff}",
            "order": "created_at.desc",
            "limit": str(limit),
        }
        if session_id:
            params["session_id"] = f"eq.{session_id}"
        if level:
            params["level"] = f"eq.{level}"
        request = Request(
            f"{self.url}/rest/v1/client_logs?{urlencode(params)}",
            headers={
                "apikey": self.anon_key,
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            },
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
        if not isinstance(rows, list):
            raise TelemetryError("Telemetry service returned an unexpected response.")
        return rows


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
    if os.getenv("TELEMETRY_MODE", "mock").lower() == "mock":
        return MockTelemetryClient()
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    access_token = os.getenv("SUPABASE_ACCESS_TOKEN")
    if not all((url, anon_key, access_token)):
        raise TelemetryError(
            "Live mode requires SUPABASE_URL, SUPABASE_ANON_KEY, and SUPABASE_ACCESS_TOKEN."
        )
    if "service_role" in access_token.lower():
        raise TelemetryError("Service-role credentials are not accepted by this tool.")
    return SupabaseTelemetryClient(url, anon_key, access_token)


def fetch_client_logs(
    user_id: str,
    limit: int = 20,
    session_id: str = "",
    level: str = "",
    since_minutes: int = 1440,
) -> str:
    """Return recent logs within the caller's user scope; never accepts arbitrary SQL."""
    if not user_id or len(user_id) > 64:
        raise ValueError("A valid user_id is required.")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be an integer between 1 and {MAX_LIMIT}.")
    if session_id and (len(session_id) > 64 or not session_id.strip()):
        raise ValueError("session_id must be 1-64 characters when provided.")
    if level and level not in ALLOWED_LEVELS:
        raise ValueError("level must be info, warn, or error.")
    if not isinstance(since_minutes, int) or isinstance(since_minutes, bool) or not 1 <= since_minutes <= 10080:
        raise ValueError("since_minutes must be between 1 and 10080.")

    rows = _client_from_environment().fetch_logs(
        user_id, limit, session_id or None, level or None, since_minutes
    )
    safe_rows = [_redact(row) for row in rows]
    return json.dumps({"count": len(safe_rows), "logs": safe_rows}, ensure_ascii=True)


if __name__ == "__main__":
    demo_user = os.getenv("TELEMETRY_DEMO_USER_ID", "00000000-0000-0000-0000-000000000001")
    print(fetch_client_logs(user_id=demo_user))
