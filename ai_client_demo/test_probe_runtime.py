"""Tests for the client-side probe runtime."""

import json
import unittest

from ai_client_demo.probe_runtime import (
    MAX_DETAIL_BYTES,
    InMemoryTransport,
    ProbeRuntime,
    ProbeRuntimeError,
)


class ProbeRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.transport = InMemoryTransport()
        self.runtime = ProbeRuntime(self.transport, "case-1", "tcs_test_session")

    def test_nothing_is_emitted_without_probes(self):
        self.runtime.poll()
        self.assertIsNone(self.runtime.check("palette.open", {"presentation_context": None}))
        self.assertEqual(self.transport.logs, [])

    def test_probe_is_applied_at_runtime_and_emits_case_scoped_event(self):
        self.transport.probes = [{
            "probe_id": "palette_context",
            "target": "palette.open",
            "capture": {"presentation_context": "true"},
            "level": "error",
        }]
        result = self.runtime.poll()
        self.assertEqual(result["applied"], ["palette.open"])
        emitted = self.runtime.check("palette.open", {"presentation_context": None, "secret": "x"})
        self.assertIsNotNone(emitted)
        self.assertEqual(len(self.transport.logs), 1)
        event = self.transport.logs[0]
        self.assertEqual(event["case_id"], "case-1")
        self.assertEqual(event["level"], "error")
        self.assertEqual(event["event"], "probe_palette_context")
        self.assertEqual(event["detail"], {"presentation_context": None})

    def test_instrumentation_point_without_probe_is_silent(self):
        self.transport.probes = [{
            "probe_id": "palette_context",
            "target": "palette.open",
            "capture": {"presentation_context": "true"},
            "level": "warn",
        }]
        self.runtime.poll()
        self.assertIsNone(self.runtime.check("palette.close", {"presentation_context": "present"}))
        self.assertEqual(self.transport.logs, [])

    def test_terminal_state_withdraws_probes(self):
        self.transport.probes = [{
            "probe_id": "palette_context",
            "target": "palette.open",
            "capture": {"presentation_context": "true"},
            "level": "warn",
        }]
        self.runtime.poll()
        self.transport.state = "resolved"
        result = self.runtime.poll()
        self.assertEqual(result["withdrawn"], ["palette.open"])
        self.assertIsNone(self.runtime.check("palette.open", {"presentation_context": None}))
        self.assertEqual(self.transport.logs, [])

    def test_changed_probe_set_replaces_the_previous_one(self):
        self.transport.probes = [{
            "probe_id": "palette_context",
            "target": "palette.open",
            "capture": {"presentation_context": "true"},
            "level": "warn",
        }]
        self.runtime.poll()
        self.transport.probes = [{
            "probe_id": "avatar_timeout",
            "target": "avatar.load",
            "capture": {"timeout_ms": "true"},
            "level": "info",
        }]
        result = self.runtime.poll()
        self.assertEqual(result["applied"], ["avatar.load"])
        self.assertEqual(result["withdrawn"], ["palette.open"])
        self.assertIsNone(self.runtime.check("palette.open", {"presentation_context": None}))

    def test_failed_poll_stops_collection(self):
        class BrokenTransport(InMemoryTransport):
            def read_case_state(self, case_id, session_key):
                raise OSError("network down")

        runtime = ProbeRuntime(BrokenTransport(), "case-1", "tcs_test_session")
        with self.assertRaises(ProbeRuntimeError):
            runtime.poll()
        self.assertEqual(runtime.active_targets, [])
        self.assertIsNone(runtime.check("palette.open", {}))

    def test_detail_is_bounded(self):
        self.transport.probes = [{
            "probe_id": "wide",
            "target": "module.call",
            "capture": {"payload": "true"},
            "level": "warn",
        }]
        self.runtime.poll()
        self.runtime.check("module.call", {"payload": "x" * 10_000})
        detail = self.transport.logs[0]["detail"]
        self.assertLessEqual(len(json.dumps(detail).encode("utf-8")), MAX_DETAIL_BYTES)

    def test_stop_withdraws_every_probe(self):
        self.transport.probes = [{
            "probe_id": "palette_context",
            "target": "palette.open",
            "capture": {"presentation_context": "true"},
            "level": "warn",
        }]
        self.runtime.poll()
        result = self.runtime.stop()
        self.assertEqual(result["withdrawn"], ["palette.open"])
        self.assertIsNone(self.runtime.check("palette.open", {"presentation_context": None}))

    def test_invalid_probe_level_falls_back_to_warn(self):
        self.transport.probes = [{
            "probe_id": "odd",
            "target": "module.call",
            "capture": {},
            "level": "critical",
        }]
        self.runtime.poll()
        self.runtime.check("module.call", {})
        self.assertEqual(self.transport.logs[0]["level"], "warn")


if __name__ == "__main__":
    unittest.main()
