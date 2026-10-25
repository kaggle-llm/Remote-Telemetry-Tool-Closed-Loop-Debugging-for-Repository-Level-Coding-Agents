import json
import os
import unittest
from unittest.mock import patch

import telemetry_tool


SESSION_KEY = "tls_" + "b" * 43


class MockClient:
    def create_session(self, name):
        self.create_call = name
        return {"id": "session-uuid", "name": name, "session_key": SESSION_KEY}

    def fetch_logs(self, session_key, limit):
        self.fetch_call = (session_key, limit)
        return [{"event": "palette_failed", "detail": {"email": "private@example.com"}}]

    def write_log(self, session_key, level, event, detail):
        self.write_call = (session_key, level, event, detail)
        return {"id": 5, "created": True}


class TelemetryToolTests(unittest.TestCase):
    def setUp(self):
        self.client = MockClient()
        self.client_patch = patch.object(telemetry_tool, "_client_from_environment", return_value=self.client)
        self.client_patch.start()
        self.session_env = patch.dict("os.environ", {}, clear=False)
        self.session_env.start()
        os.environ.pop("TELEMETRY_SESSION_KEY", None)

    def tearDown(self):
        self.client_patch.stop()
        self.session_env.stop()

    def test_start_creates_unique_session_key_hidden_from_model_output(self):
        result = json.loads(telemetry_tool.start_ai_session_for_agent("test run"))
        self.assertEqual(result["session_id"], "session-uuid")
        self.assertNotIn(SESSION_KEY, json.dumps(result))
        self.assertEqual(os.environ["TELEMETRY_SESSION_KEY"], SESSION_KEY)
        self.assertEqual(self.client.create_call, "test run")

    def test_fetch_and_write_use_current_session_and_redact(self):
        os.environ["TELEMETRY_SESSION_KEY"] = SESSION_KEY
        result = json.loads(telemetry_tool.fetch_session_logs_for_agent(limit=7))
        written = json.loads(telemetry_tool.write_session_log_for_agent("warn", "agent_note", {"step": 2}))
        self.assertEqual(result["logs"][0]["detail"]["email"], "[REDACTED]")
        self.assertEqual(self.client.fetch_call, (SESSION_KEY, 7))
        self.assertTrue(written["created"])
        self.assertEqual(self.client.write_call, (SESSION_KEY, "warn", "agent_note", {"step": 2}))

    def test_log_tools_require_session_to_be_started(self):
        with self.assertRaises(telemetry_tool.TelemetryError):
            telemetry_tool.fetch_session_logs_for_agent()
        with self.assertRaises(telemetry_tool.TelemetryError):
            telemetry_tool.write_session_log_for_agent("error", "event", {})

    def test_rejects_bad_session_key_limit_and_log_data(self):
        invalid = (
            lambda: telemetry_tool.fetch_client_logs("bad"),
            lambda: telemetry_tool.fetch_client_logs(SESSION_KEY, 101),
            lambda: telemetry_tool.write_client_log(SESSION_KEY, "debug", "x", {}),
            lambda: telemetry_tool.write_client_log(SESSION_KEY, "error", "", {}),
            lambda: telemetry_tool.write_client_log(SESSION_KEY, "error", "x", []),
        )
        for call in invalid:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()


if __name__ == "__main__":
    unittest.main()
