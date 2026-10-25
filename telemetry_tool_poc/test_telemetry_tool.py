import json
import os
import unittest
from unittest.mock import patch

import telemetry_tool


USER_A = "00000000-0000-0000-0000-000000000001"
USER_B = "00000000-0000-0000-0000-000000000002"


class FetchClientLogsTests(unittest.TestCase):
    def setUp(self):
        self.client = telemetry_tool.MockTelemetryClient([
            {
                "id": 1,
                "user_id": USER_A,
                "session_id": "session-a",
                "level": "error",
                "event": "palette_failed",
                "detail": {"email": "private@example.com", "view": "Palette"},
                "created_at": "2026-10-24T18:00:00+00:00",
            },
            {
                "id": 2,
                "user_id": USER_B,
                "session_id": "session-b",
                "level": "error",
                "event": "other_user_event",
                "detail": {},
                "created_at": "2026-10-24T18:01:00+00:00",
            },
        ])
        self.environment = patch.dict(os.environ, {"TELEMETRY_MODE": "mock"})
        self.environment.start()
        self.client_patch = patch.object(telemetry_tool, "_client_from_environment", return_value=self.client)
        self.client_patch.start()

    def tearDown(self):
        self.client_patch.stop()
        self.environment.stop()

    def test_scopes_results_to_user_and_redacts_sensitive_detail(self):
        result = json.loads(telemetry_tool.fetch_client_logs(user_id=USER_A))
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["logs"][0]["event"], "palette_failed")
        self.assertEqual(result["logs"][0]["detail"]["email"], "[REDACTED]")

    def test_filters_session_and_level(self):
        result = json.loads(telemetry_tool.fetch_client_logs(
            user_id=USER_A, session_id="session-a", level="error"
        ))
        self.assertEqual(result["count"], 1)
        empty = json.loads(telemetry_tool.fetch_client_logs(
            user_id=USER_A, session_id="wrong-session"
        ))
        self.assertEqual(empty["count"], 0)

    def test_rejects_out_of_range_or_invalid_parameters(self):
        for kwargs in (
            {"user_id": USER_A, "limit": 0},
            {"user_id": USER_A, "limit": 101},
            {"user_id": USER_A, "level": "debug"},
            {"user_id": USER_A, "since_minutes": 20000},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                telemetry_tool.fetch_client_logs(**kwargs)

    def test_mock_client_is_user_scoped(self):
        result = self.client.fetch_logs(USER_A, 20)
        self.assertTrue(all(row["user_id"] == USER_A for row in result))


if __name__ == "__main__":
    unittest.main()
