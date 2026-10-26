import json
import os
import unittest
from unittest.mock import patch

import telemetry_tool


SESSION_KEY = "tls_" + "b" * 43
CASE_ID = "11111111-2222-3333-4444-555555555555"


class MockClient:
    def create_session(self, name):
        self.create_call = name
        return {"id": "session-uuid", "name": name, "session_key": SESSION_KEY}

    def fetch_logs(self, session_key, limit):
        self.fetch_call = (session_key, limit)
        return [{"event": "palette_failed", "detail": {"email": "private@example.com"}}]

    def fetch_recent_client_logs(self, limit, client_session_id=None):
        self.client_fetch_call = (limit, client_session_id)
        return [{"id": 4, "event": "highlight_palette_opened", "client_session_id": client_session_id}]

    def write_log(self, session_key, level, event, detail):
        self.write_call = (session_key, level, event, detail)
        return {"id": 5, "created": True}

    def list_cases(self, limit, state=None):
        self.list_cases_call = (limit, state)
        return [{"id": CASE_ID, "state": "reported", "user_report": "palette does not open"}]

    def fetch_case_logs(self, case_id, limit):
        self.fetch_case_logs_call = (case_id, limit)
        return [{"id": 9, "event": "palette_probe", "detail": {"password": "hunter2"}}]

    def instrument_case(self, case_id, instructions, probes):
        self.instrument_call = (case_id, instructions, probes)
        return {"case_id": case_id, "state": "instrumenting", "updated": True}

    def await_recheck(self, case_id, instructions, probes):
        self.await_recheck_call = (case_id, instructions, probes)
        return {"case_id": case_id, "state": "awaiting_recheck", "updated": True}

    def finalize_case(self, case_id):
        self.finalize_call = case_id
        return {"case_id": case_id, "state": "patch_ready", "updated": True}

    def abandon_case(self, case_id):
        self.abandon_call = case_id
        return {"case_id": case_id, "state": "abandoned", "updated": True}

    def cleanup_case(self, case_id):
        self.cleanup_call = case_id
        return {"case_id": case_id, "state": "resolved", "deleted_logs": 3, "cleaned": True}


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

    def test_recent_client_logs_can_be_filtered_by_client_session(self):
        with patch.object(telemetry_tool, "_client_from_environment", return_value=self.client):
            result = json.loads(telemetry_tool.fetch_recent_client_logs_for_agent(10, "client-session-id"))
        self.assertEqual(result["count"], 1)
        self.assertEqual(self.client.client_fetch_call, (10, "client-session-id"))


class DebugCaseToolTests(unittest.TestCase):
    def setUp(self):
        self.client = MockClient()
        self.client_patch = patch.object(telemetry_tool, "_client_from_environment", return_value=self.client)
        self.client_patch.start()

    def tearDown(self):
        self.client_patch.stop()

    def test_list_cases_forwards_limit_and_state_filter(self):
        result = json.loads(telemetry_tool.list_debug_cases_for_agent(limit=10, state="reported"))
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["cases"][0]["id"], CASE_ID)
        self.assertEqual(self.client.list_cases_call, (10, "reported"))

    def test_case_logs_are_case_scoped_and_redacted(self):
        result = json.loads(telemetry_tool.fetch_case_logs_for_agent(CASE_ID, limit=25))
        self.assertEqual(self.client.fetch_case_logs_call, (CASE_ID, 25))
        self.assertEqual(result["logs"][0]["detail"]["password"], "[REDACTED]")
        self.assertEqual(result["case_id"], CASE_ID)

    def test_instrumentation_publishes_probes_and_instructions(self):
        probes = [{"probe_id": "p1", "target": "HighlightPaletteView.presentPalette", "capture": {"fields": ["state"]}}]
        result = json.loads(telemetry_tool.request_instrumentation_for_agent(CASE_ID, "Try again.", probes))
        self.assertEqual(result["state"], "instrumenting")
        self.assertEqual(self.client.instrument_call[0], CASE_ID)
        self.assertEqual(self.client.instrument_call[2][0]["level"], "warn")

    def test_await_recheck_defaults_to_no_probes(self):
        result = json.loads(telemetry_tool.await_user_recheck_for_agent(CASE_ID, "Please retry the highlight action."))
        self.assertEqual(result["state"], "awaiting_recheck")
        self.assertEqual(self.client.await_recheck_call[2], [])

    def test_finalize_abandon_and_cleanup_drive_the_case_lifecycle(self):
        self.assertEqual(json.loads(telemetry_tool.finalize_case_for_agent(CASE_ID))["state"], "patch_ready")
        self.assertEqual(self.client.finalize_call, CASE_ID)
        self.assertEqual(json.loads(telemetry_tool.abandon_case_for_agent(CASE_ID))["state"], "abandoned")
        self.assertEqual(self.client.abandon_call, CASE_ID)
        cleanup = json.loads(telemetry_tool.cleanup_case_for_agent(CASE_ID))
        self.assertEqual(cleanup["state"], "resolved")
        self.assertEqual(cleanup["deleted_logs"], 3)
        self.assertEqual(self.client.cleanup_call, CASE_ID)

    def test_case_tools_reject_invalid_identifiers_limits_and_probes(self):
        invalid = (
            lambda: telemetry_tool.fetch_case_logs_for_agent("not-a-uuid"),
            lambda: telemetry_tool.fetch_case_logs_for_agent(CASE_ID, 0),
            lambda: telemetry_tool.list_debug_cases_for_agent(101),
            lambda: telemetry_tool.list_debug_cases_for_agent(10, "unknown_state"),
            lambda: telemetry_tool.request_instrumentation_for_agent(CASE_ID, "", []),
            lambda: telemetry_tool.request_instrumentation_for_agent(CASE_ID, "ok", [{"probe_id": "", "target": "t"}]),
            lambda: telemetry_tool.request_instrumentation_for_agent(CASE_ID, "ok", [{"probe_id": "p", "target": "t", "level": "fatal"}]),
            lambda: telemetry_tool.request_instrumentation_for_agent(CASE_ID, "ok", [{"probe_id": "p", "target": "t", "capture": []}]),
            lambda: telemetry_tool.request_instrumentation_for_agent(CASE_ID, "ok", [{"probe_id": "p" * 81, "target": "t"}]),
            lambda: telemetry_tool.request_instrumentation_for_agent(CASE_ID, "ok", ["not-an-object"]),
        )
        for call in invalid:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()

    def test_free_text_reports_are_scrubbed_before_reaching_the_model(self):
        rows = [{"user_report": "please check my account at user@example.com", "title": "t", "instructions": "retry"}]
        scrubbed = telemetry_tool._redact(rows)
        self.assertNotIn("user@example.com", scrubbed[0]["user_report"])
        self.assertIn("[REDACTED_EMAIL]", scrubbed[0]["user_report"])


if __name__ == "__main__":
    unittest.main()
