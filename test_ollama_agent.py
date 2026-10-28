import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ollama_agent


class WorkspaceToolTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.old_workspace = ollama_agent.PATCH_WORKSPACE
        self.old_enabled = ollama_agent.PATCH_ENABLED
        ollama_agent.PATCH_WORKSPACE = self.workspace

    def tearDown(self):
        ollama_agent.PATCH_WORKSPACE = self.old_workspace
        ollama_agent.PATCH_ENABLED = self.old_enabled
        self.temp_dir.cleanup()

    def test_read_file_blocks_traversal_and_secrets(self):
        (self.workspace / "source.py").write_text("value = 1\n", encoding="utf-8")
        self.assertEqual(ollama_agent.read_workspace_file("source.py").replace("\r\n", "\n"), "value = 1\n")
        with self.assertRaises(ValueError):
            ollama_agent.read_workspace_file("../outside.txt")
        with self.assertRaises(ValueError):
            ollama_agent._workspace_file("config.env")

    def test_patch_application_is_disabled_by_default(self):
        with self.assertRaises(PermissionError):
            ollama_agent.apply_workspace_patch("diff --git a/a b/a\n")

    def test_patch_updates_existing_file_when_enabled(self):
        target = self.workspace / "source.py"
        target.write_text("value = 1\n", encoding="utf-8")
        patch_text = (
            "diff --git a/source.py b/source.py\n"
            "--- a/source.py\n"
            "+++ b/source.py\n"
            "@@ -1 +1 @@\n"
            "-value = 1\n"
            "+value = 2\n"
        )
        ollama_agent.PATCH_ENABLED = True
        result = json.loads(ollama_agent.apply_workspace_patch(patch_text))
        self.assertTrue(result["applied"])
        self.assertEqual(target.read_text(encoding="utf-8"), "value = 2\n")

    def test_patch_recount_fallback_tolerates_miscounted_hunks(self):
        target = self.workspace / "source.py"
        target.write_text("value = 1\n", encoding="utf-8")
        patch_text = (
            "diff --git a/source.py b/source.py\n"
            "--- a/source.py\n"
            "+++ b/source.py\n"
            "@@ -1,4 +1,4 @@\n"
            "-value = 1\n"
            "+value = 2\n"
        )
        ollama_agent.PATCH_ENABLED = True
        result = json.loads(ollama_agent.apply_workspace_patch(patch_text))
        self.assertTrue(result["applied"])
        self.assertEqual(target.read_text(encoding="utf-8").replace("\r\n", "\n"), "value = 2\n")

    def test_test_runner_requires_existing_workspace_directory(self):
        ollama_agent.ALLOWED_TESTS["missing-dir"] = ([ollama_agent.sys.executable, "-c", "print(1)"], "not-there")
        try:
            with self.assertRaises(ValueError):
                ollama_agent.run_workspace_test("missing-dir")
        finally:
            ollama_agent.ALLOWED_TESTS.pop("missing-dir", None)

    def test_patch_without_trailing_newline_is_applied(self):
        target = self.workspace / "source.py"
        target.write_text("value = 1\n", encoding="utf-8")
        patch_text = (
            "diff --git a/source.py b/source.py\n"
            "--- a/source.py\n"
            "+++ b/source.py\n"
            "@@ -1,4 +1,4 @@\n"
            "-value = 1\n"
            "+value = 2\n"
        )
        ollama_agent.PATCH_ENABLED = True
        result = json.loads(ollama_agent.apply_workspace_patch(patch_text))
        self.assertTrue(result["applied"])
        self.assertEqual(target.read_text(encoding="utf-8").replace("\r\n", "\n"), "value = 2\n")

    def test_patch_applies_to_crlf_file_with_lf_diff(self):
        target = self.workspace / "source.py"
        target.write_bytes(b"value = 1\r\nother = 2\r\n")
        patch_text = (
            "diff --git a/source.py b/source.py\n"
            "--- a/source.py\n"
            "+++ b/source.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-value = 1\n"
            "+value = 3\n"
            " other = 2\n"
        )
        ollama_agent.PATCH_ENABLED = True
        result = json.loads(ollama_agent.apply_workspace_patch(patch_text))
        self.assertTrue(result["applied"])
        self.assertEqual(target.read_bytes(), b"value = 3\r\nother = 2\r\n")

    def test_patch_rejects_new_files(self):
        ollama_agent.PATCH_ENABLED = True
        with self.assertRaises(ValueError):
            ollama_agent.apply_workspace_patch(
                "diff --git a/new.py b/new.py\n"
                "new file mode 100644\n"
                "--- /dev/null\n"
                "+++ b/new.py\n"
                "@@ -0,0 +1 @@\n"
                "+created = True\n"
            )

    def test_only_allowlisted_test_suites_can_run(self):
        with self.assertRaises(ValueError):
            ollama_agent.run_workspace_test("arbitrary-shell")

    def test_allowlisted_test_runs_inside_configured_workspace(self):
        (self.workspace / "test_synthetic.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n",
            encoding="utf-8",
        )
        ollama_agent.ALLOWED_TESTS["synthetic"] = ([ollama_agent.sys.executable, "-m", "unittest", "test_synthetic"], ".")
        try:
            result = json.loads(ollama_agent.run_workspace_test("synthetic"))
        finally:
            ollama_agent.ALLOWED_TESTS.pop("synthetic", None)
        self.assertTrue(result["passed"])

    def test_cleanup_requires_approved_state(self):
        case_id = "11111111-2222-3333-4444-555555555555"
        with patch.object(ollama_agent, "list_debug_cases_for_agent", return_value=json.dumps({"cases": [{"id": case_id, "state": "reported"}]})):
            with self.assertRaises(PermissionError):
                ollama_agent.cleanup_approved_case(case_id)

    def test_cleanup_runs_only_for_approved_state(self):
        case_id = "11111111-2222-3333-4444-555555555555"
        with (
            patch.object(ollama_agent, "list_debug_cases_for_agent", return_value=json.dumps({"cases": [{"id": case_id, "state": "approved"}]})),
            patch.object(ollama_agent, "cleanup_case_for_agent", return_value='{"state":"resolved"}') as cleanup,
        ):
            result = ollama_agent.cleanup_approved_case(case_id)
        self.assertEqual(result, '{"state":"resolved"}')
        cleanup.assert_called_once_with(case_id)

    def test_remote_debug_finding_records_feedback_request_without_cleanup(self):
        case_id = "11111111-2222-3333-4444-555555555555"
        with (
            patch.object(ollama_agent, "list_debug_cases_for_agent", return_value=json.dumps({"cases": [{"id": case_id, "state": "reported", "title": "Synthetic case"}]})),
            patch.object(ollama_agent, "start_ai_session_for_agent", return_value='{"session_id":"session-1"}'),
            patch.object(ollama_agent, "await_user_recheck_for_agent", return_value='{"state":"awaiting_recheck"}') as await_recheck,
            patch.object(ollama_agent, "write_session_log_for_agent", return_value='{"created":true}') as write_log,
            patch.object(ollama_agent, "cleanup_case_for_agent") as cleanup,
        ):
            result = json.loads(ollama_agent.record_remote_debug_finding(case_id, "Needs device reproduction", "Please retry and report the screen state."))
        self.assertTrue(result["recorded"])
        self.assertTrue(result["awaiting_user_feedback"])
        self.assertFalse(result["cleanup_performed"])
        await_recheck.assert_called_once()
        write_log.assert_called_once()
        cleanup.assert_not_called()

    def test_remote_debug_finding_rejects_unknown_case(self):
        with patch.object(ollama_agent, "list_debug_cases_for_agent", return_value='{"cases":[]}'):
            with self.assertRaises(ValueError):
                ollama_agent.record_remote_debug_finding("11111111-2222-3333-4444-555555555555", "finding", "feedback")


if __name__ == "__main__":
    unittest.main()
