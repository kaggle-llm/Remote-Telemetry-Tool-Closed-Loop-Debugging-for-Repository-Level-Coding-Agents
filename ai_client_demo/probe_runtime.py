"""Runtime-selectable probe runtime for the client side of the debugging loop.

The runtime polls the management API for the probes that are active for one
debugging case, applies them to instrumentation points in the app, and emits
bounded events that are linked to that case. It is fail-closed: when the probe
set cannot be confirmed, no event is emitted. When the case reaches a terminal
state the probes are withdrawn and the client stops collecting.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

MAX_DETAIL_BYTES = 2000
MAX_EVENT_NAME = 120
ALLOWED_LEVELS = {"info", "warn", "error"}
TERMINAL_STATES = {"resolved", "abandoned"}
SAFE_NAME = re.compile(r"[^a-z0-9_]+")


class ProbeRuntimeError(RuntimeError):
    """Raised when the runtime cannot confirm or apply its probe set."""


def _bounded_value(value):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:512]
    if isinstance(value, (list, tuple)):
        return [_bounded_value(item) for item in list(value)[:20]]
    if isinstance(value, dict):
        return {str(key)[:64]: _bounded_value(item) for key, item in list(value.items())[:20]}
    return str(value)[:256]


def _bounded_detail(detail):
    encoded = json.dumps(detail, ensure_ascii=True)
    if len(encoded.encode("utf-8")) <= MAX_DETAIL_BYTES:
        return detail
    trimmed = {}
    for key, value in detail.items():
        candidate = dict(trimmed)
        candidate[key] = value
        if len(json.dumps(candidate, ensure_ascii=True).encode("utf-8")) > MAX_DETAIL_BYTES:
            break
        trimmed = candidate
    return trimmed


class HttpTransport:
    """Talks to the management API with an ingest key and a client session key."""

    def __init__(self, base_url, ingest_key, timeout=15, origin=None):
        self.base_url = base_url.rstrip("/")
        self.ingest_key = ingest_key
        self.timeout = timeout
        self.origin = origin or os.getenv("TELEMETRY_ORIGIN", "").strip() or "http://localhost:5173"

    def _post(self, path, payload):
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Origin": self.origin,
                "Authorization": f"Bearer {self.ingest_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise ProbeRuntimeError("The management API could not be reached.") from exc

    def read_case_state(self, case_id, session_key):
        return self._post(f"/api/client/cases/{case_id}/state", {"session_key": session_key})

    def write_client_log(self, session_key, event):
        return self._post("/api/client/logs", {"session_key": session_key, **event})


class InMemoryTransport:
    """Transport used by the tests and by the offline lifecycle demonstration."""

    def __init__(self, state="reported", probes=None):
        self.state = state
        self.probes = list(probes or [])
        self.logs = []
        self.reads = 0

    def read_case_state(self, case_id, session_key):
        self.reads += 1
        return {"case_id": case_id, "state": self.state, "version": self.reads, "probes": list(self.probes)}

    def write_client_log(self, session_key, event):
        self.logs.append({"session_key": session_key, **event})
        return {"id": len(self.logs), "created": True}


class ProbeRuntime:
    """Applies published probes to instrumentation points and emits bounded events."""

    def __init__(self, transport, case_id, session_key, user_agent="probe-runtime"):
        self.transport = transport
        self.case_id = case_id
        self.session_key = session_key
        self.user_agent = user_agent
        self._probes = {}
        self.state = None
        self.instructions = None
        self.emitted_events = 0
        self.last_error = None

    @property
    def active_targets(self):
        return sorted(self._probes)

    def poll(self):
        """Refresh the probe set from the management API."""
        try:
            payload = self.transport.read_case_state(self.case_id, self.session_key)
        except Exception as exc:
            self._probes = {}
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise ProbeRuntimeError("The probe set could not be confirmed, so the runtime stopped collecting.") from exc

        self.last_error = None
        state = payload.get("state")
        self.state = state
        self.instructions = payload.get("instructions")
        previous = dict(self._probes)

        if state in TERMINAL_STATES:
            self._probes = {}
            return {"state": state, "applied": [], "withdrawn": sorted(previous), "instructions": self.instructions}

        refreshed = {}
        for probe in payload.get("probes") or []:
            target = probe.get("target")
            if not isinstance(target, str) or not target.strip():
                continue
            level = probe.get("level", "warn")
            if level not in ALLOWED_LEVELS:
                level = "warn"
            capture = probe.get("capture")
            if not isinstance(capture, dict):
                capture = {}
            refreshed[target.strip()] = {
                "probe_id": str(probe.get("probe_id") or target)[:80],
                "capture": capture,
                "level": level,
            }

        self._probes = refreshed
        return {
            "state": state,
            "applied": sorted(set(refreshed) - set(previous)),
            "withdrawn": sorted(set(previous) - set(refreshed)),
            "instructions": self.instructions,
        }

    def check(self, target, fields=None):
        """Emit one event when an active probe targets this instrumentation point."""
        probe = self._probes.get(target)
        if probe is None:
            return None
        source = fields or {}
        detail = {}
        for name in probe["capture"]:
            if name in source:
                detail[name] = _bounded_value(source[name])
        detail = _bounded_detail(detail)
        event_name = f"probe_{SAFE_NAME.sub('_', probe['probe_id'].lower())}"[:MAX_EVENT_NAME]
        event = {
            "level": probe["level"],
            "event": event_name,
            "detail": detail,
            "case_id": self.case_id,
            "user_agent": self.user_agent,
        }
        result = self.transport.write_client_log(self.session_key, event)
        self.emitted_events += 1
        return result

    def stop(self):
        """Withdraw every probe and stop collecting."""
        withdrawn = sorted(self._probes)
        self._probes = {}
        return {"withdrawn": withdrawn, "emitted_events": self.emitted_events}


def load_env(path):
    """Load KEY=value pairs from a .env file without overwriting the environment."""
    file_path = Path(path)
    if not file_path.exists():
        return
    for line in file_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
