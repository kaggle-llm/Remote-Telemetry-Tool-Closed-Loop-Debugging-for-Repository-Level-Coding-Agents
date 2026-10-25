import json
import unittest
from unittest.mock import patch

import telemetry_tool


TOOL_KEY = "tlk_" + "a" * 43
SESSION_KEY = "tls_" + "b" * 43


class MockClient:
    def fetch_logs(self, tool_key, session_key, limit):
        self.fetch_call = (tool_key, session_key, limit)
        return [{"event": "palette_failed", "detail": {"email": "private@example.com"}}]

    def write_log(self, tool_key, session_key, level, event, detail):
        self.write_call = (tool_key, session_key, level, event, detail)
        return {"id": 5, "created": True}


class TelemetryToolTests(unittest.TestCase):
    def setUp(self):
        self.client = MockClient()
        self.client_patch = patch.object(telemetry_tool, "_client_from_environment", return_value=self.client)
        self.client_patch.start()

    def tearDown(self):
        self.client_patch.stop()

    def test_fetch_passes_scoped_keys_and_redacts(self):
        result = json.loads(telemetry_tool.fetch_client_logs(TOOL_KEY, SESSION_KEY))
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["logs"][0]["detail"]["email"], "[REDACTED]")
        self.assertEqual(self.client.fetch_call, (TOOL_KEY, SESSION_KEY, 20))

    def test_write_passes_validated_log(self):
        result = json.loads(telemetry_tool.write_client_log(
            TOOL_KEY, SESSION_KEY, "error", "palette_failed", {"view": "Palette"}
        ))
        self.assertTrue(result["created"])
        self.assertEqual(self.client.write_call[1:4], (SESSION_KEY, "error", "palette_failed"))

    def test_rejects_invalid_keys_and_limits(self):
        bad_calls = (
            lambda: telemetry_tool.fetch_client_logs("bad", SESSION_KEY),
            lambda: telemetry_tool.fetch_client_logs(TOOL_KEY, "bad"),
            lambda: telemetry_tool.fetch_client_logs(TOOL_KEY, SESSION_KEY, 101),
            lambda: telemetry_tool.write_client_log(TOOL_KEY, SESSION_KEY, "debug", "x", {}),
            lambda: telemetry_tool.write_client_log(TOOL_KEY, SESSION_KEY, "error", "", {}),
        )
        for call in bad_calls:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()

    def test_rpc_uses_publishable_key_and_never_service_role(self):
        client = telemetry_tool.SupabaseTelemetryClient("https://example.supabase.co", "sb_publishable_test")
        self.client_patch.stop()
        with patch.dict("os.environ", {"TELEMETRY_MODE": "supabase", "SUPABASE_URL": "https://example.supabase.co", "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_test"}):
            with patch.object(telemetry_tool, "SupabaseTelemetryClient", return_value=client) as factory:
                selected = telemetry_tool._client_from_environment()
                factory.assert_called_once_with("https://example.supabase.co", "sb_publishable_test")
                self.assertIs(selected, client)
        self.client_patch.start()
        self.assertEqual(client.url, "https://example.supabase.co")

    def test_agent_wrappers_inject_credentials_and_do_not_expose_them_as_arguments(self):
        with patch.dict("os.environ", {
            "TELEMETRY_TOOL_KEY": TOOL_KEY,
            "TELEMETRY_SESSION_KEY": SESSION_KEY,
        }):
            fetched = json.loads(telemetry_tool.fetch_session_logs_for_agent(limit=7))
            written = json.loads(telemetry_tool.write_session_log_for_agent("warn", "agent_note", {"step": 2}))
        self.assertEqual(fetched["count"], 1)
        self.assertTrue(written["created"])
        self.assertEqual(self.client.fetch_call, (TOOL_KEY, SESSION_KEY, 7))
        self.assertEqual(self.client.write_call[0:4], (TOOL_KEY, SESSION_KEY, "warn", "agent_note"))


if __name__ == "__main__":
    unittest.main()
