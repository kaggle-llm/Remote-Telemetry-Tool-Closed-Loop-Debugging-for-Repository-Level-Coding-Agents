"""Tests for the paired telemetry evaluation harness."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.agent_loop import Workspace  # noqa: E402
from eval.eval_runner import (  # noqa: E402
    adjudicate,
    bootstrap_mean_ci,
    derive_trial_seed,
    mcnemar_exact,
    prepare_workspace,
    run_public_tests,
    run_validation_test,
    seed_store,
    validation_source,
)
from eval.fixture_backend import FixtureBackend, synthetic_case_id  # noqa: E402
from telemetry_tool_poc.telemetry_tool import fetch_case_logs_for_agent, list_debug_cases_for_agent  # noqa: E402

FIXTURES = ROOT / "eval" / "fixtures"
HAS_FIXTURES = (FIXTURES / "repo").is_dir() and (FIXTURES / "cases.json").is_file()


class FixtureBackendTests(unittest.TestCase):
    def setUp(self):
        self.store, self.case_id, self.key = seed_store(
            {
                "task_id": "t_test_scope",
                "title": "Test failure",
                "report": "Something fails.",
                "telemetry_events": [{"level": "error", "event": "test_event", "detail": {"value": 1}}],
            },
            "B",
        )
        self.backend = FixtureBackend(self.store)
        self.url = self.backend.start()

    def tearDown(self):
        self.backend.stop()

    def test_case_ids_are_deterministic_and_synthetic(self):
        first = synthetic_case_id("t_test_scope")
        second = synthetic_case_id("t_test_scope")
        self.assertEqual(first, second)
        self.assertNotEqual(first, synthetic_case_id("t_other"))
        self.assertRegex(first, r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

    def test_owner_can_read_own_case_logs(self):
        import os

        previous_domain = os.environ.get("TELEMETRY_DOMAIN")
        previous_key = os.environ.get("TELEMETRY_TOOL_KEY")
        os.environ["TELEMETRY_DOMAIN"] = self.url
        os.environ["TELEMETRY_TOOL_KEY"] = self.key
        try:
            cases = json.loads(list_debug_cases_for_agent(limit=10))
            self.assertEqual(cases["count"], 1)
            logs = json.loads(fetch_case_logs_for_agent(case_id=self.case_id, limit=10))
            self.assertEqual(logs["count"], 1)
            self.assertEqual(logs["logs"][0]["event"], "test_event")
        finally:
            if previous_domain is None:
                os.environ.pop("TELEMETRY_DOMAIN", None)
            else:
                os.environ["TELEMETRY_DOMAIN"] = previous_domain
            if previous_key is None:
                os.environ.pop("TELEMETRY_TOOL_KEY", None)
            else:
                os.environ["TELEMETRY_TOOL_KEY"] = previous_key

    def test_foreign_case_is_not_readable(self):
        foreign_case = dict(self.store.cases[self.case_id])
        foreign_case["id"] = "11111111-2222-3333-4444-555555555555"
        foreign_case["owner_id"] = "another-owner"
        self.store.cases[foreign_case["id"]] = foreign_case
        self.store.logs[foreign_case["id"]] = []
        import os

        previous_domain = os.environ.get("TELEMETRY_DOMAIN")
        previous_key = os.environ.get("TELEMETRY_TOOL_KEY")
        os.environ["TELEMETRY_DOMAIN"] = self.url
        os.environ["TELEMETRY_TOOL_KEY"] = self.key
        try:
            with self.assertRaises(Exception):
                fetch_case_logs_for_agent(case_id=foreign_case["id"], limit=10)
        finally:
            if previous_domain is None:
                os.environ.pop("TELEMETRY_DOMAIN", None)
            else:
                os.environ["TELEMETRY_DOMAIN"] = previous_domain
            if previous_key is None:
                os.environ.pop("TELEMETRY_TOOL_KEY", None)
            else:
                os.environ["TELEMETRY_TOOL_KEY"] = previous_key

    def test_unknown_key_is_rejected(self):
        import os

        previous_domain = os.environ.get("TELEMETRY_DOMAIN")
        previous_key = os.environ.get("TELEMETRY_TOOL_KEY")
        os.environ["TELEMETRY_DOMAIN"] = self.url
        os.environ["TELEMETRY_TOOL_KEY"] = "tlk_unknown_key"
        try:
            with self.assertRaises(Exception):
                list_debug_cases_for_agent(limit=10)
        finally:
            if previous_domain is None:
                os.environ.pop("TELEMETRY_DOMAIN", None)
            else:
                os.environ["TELEMETRY_DOMAIN"] = previous_domain
            if previous_key is None:
                os.environ.pop("TELEMETRY_TOOL_KEY", None)
            else:
                os.environ["TELEMETRY_TOOL_KEY"] = previous_key

    def test_condition_a_has_no_telemetry_rows(self):
        store, case_id, key = seed_store(
            {
                "task_id": "t_test_scope",
                "title": "Test failure",
                "report": "Something fails.",
                "telemetry_events": [{"level": "error", "event": "test_event", "detail": {}}],
            },
            "A",
        )
        self.assertEqual(store.logs[case_id], [])


class AdjudicationTests(unittest.TestCase):
    def test_matching_root_cause_line_is_accurate(self):
        task = {"adjudication_key": ["presentation context", "presentation_context"]}
        answer = "ROOT_CAUSE: open_palette ignores the presentation context\nFIX: app/ui/palette.py"
        result = adjudicate(task, answer)
        self.assertTrue(result["diagnostic_accurate"])
        self.assertIn("presentation context", result["matched_phrases"])

    def test_unrelated_answer_is_not_accurate(self):
        task = {"adjudication_key": ["presentation context"]}
        answer = "ROOT_CAUSE: the network stack drops packets\nFIX: app/net/cache.py"
        result = adjudicate(task, answer)
        self.assertFalse(result["diagnostic_accurate"])

    def test_adjudication_ignores_free_text_when_root_cause_line_present(self):
        task = {"adjudication_key": ["presentation context"]}
        answer = "I looked at the presentation context earlier in the file.\nROOT_CAUSE: the network stack drops packets"
        result = adjudicate(task, answer)
        self.assertFalse(result["diagnostic_accurate"])

    def test_compound_identifier_matches_the_key_phrase(self):
        task = {"adjudication_key": ["presentation context"], "target_module": "app/ui/palette.py"}
        answer = "ROOT_CAUSE: open_palette requires an explicit PresentationContext"
        result = adjudicate(task, answer)
        self.assertTrue(result["diagnostic_accurate"])
        self.assertTrue(result["module_mentioned"])

    def test_module_localization_is_reported(self):
        task = {"adjudication_key": ["timeout"], "target_module": "app/net/imageloader.py"}
        answer = "ROOT_CAUSE: the imageloader never applies a timeout"
        result = adjudicate(task, answer)
        self.assertTrue(result["module_mentioned"])


class StatisticsTests(unittest.TestCase):
    def test_mcnemar_exact_cases(self):
        self.assertEqual(mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(mcnemar_exact(3, 0), 0.25)
        self.assertAlmostEqual(mcnemar_exact(5, 0), 0.0625)
        self.assertAlmostEqual(mcnemar_exact(2, 2), 1.0)

    def test_bootstrap_interval_contains_mean(self):
        values = [10.0, 12.0, 14.0, 16.0]
        result = bootstrap_mean_ci(values, seed=7, iterations=2000)
        self.assertLessEqual(result["low"], result["mean"])
        self.assertGreaterEqual(result["high"], result["mean"])


class TrialSeedTests(unittest.TestCase):
    def test_seed_is_stable_for_the_same_pair(self):
        first = derive_trial_seed(20261028, "t1_palette_presentation_context", 1)
        second = derive_trial_seed(20261028, "t1_palette_presentation_context", 1)
        self.assertEqual(first, second)
        self.assertGreater(first, 0)
        self.assertLess(first, 2**31 - 1)

    def test_repeats_and_tasks_get_different_seeds(self):
        base = derive_trial_seed(20261028, "t1_palette_presentation_context", 1)
        self.assertNotEqual(base, derive_trial_seed(20261028, "t1_palette_presentation_context", 2))
        self.assertNotEqual(base, derive_trial_seed(20261028, "t2_imageloader_request_timeout", 1))
        self.assertNotEqual(base, derive_trial_seed(20261029, "t1_palette_presentation_context", 1))


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="papertrack-workspace-"))
        (self.root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_public.py").write_text(
            "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_edit_writes_file_and_blocks_tests(self):
        workspace = Workspace(self.root)
        result = workspace.edit_file("app.py", "VALUE = 2\n")
        self.assertTrue(result["written"].endswith("app.py"))
        self.assertEqual((self.root / "app.py").read_text(encoding="utf-8"), "VALUE = 2\n")
        with self.assertRaises(ValueError):
            workspace.edit_file("tests/test_public.py", "raise SystemExit(1)\n")

    def test_edit_rejects_new_files(self):
        workspace = Workspace(self.root)
        with self.assertRaises(ValueError):
            workspace.edit_file("new_module.py", "VALUE = 3\n")

    def test_public_tests_run(self):
        workspace = Workspace(self.root)
        result = workspace.run_tests()
        self.assertTrue(result["passed"])


@unittest.skipUnless(HAS_FIXTURES, "fixture definitions are not present yet")
class FixtureIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tasks = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
        self.tasks = self.tasks["tasks"] if isinstance(self.tasks, dict) else self.tasks
        self.validation = validation_source(FIXTURES)

    def _workspace(self):
        directory = Path(tempfile.mkdtemp(prefix="papertrack-fixture-"))
        prepare_workspace(FIXTURES, directory)
        return directory

    def test_public_tests_pass_on_pristine_repo(self):
        directory = self._workspace()
        try:
            result = run_public_tests(directory)
            self.assertTrue(result["passed"], result["output"])
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_validation_tests_fail_on_pristine_repo(self):
        directory = self._workspace()
        try:
            shutil.copyfile(self.validation, directory / "tests" / "test_validation.py")
            for task in self.tasks:
                result = run_validation_test(directory, task["validation_test"])
                self.assertFalse(result["passed"], task["task_id"])
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_reference_fix_makes_validation_test_pass(self):
        for task in self.tasks:
            directory = self._workspace()
            try:
                target = directory / task["reference_fix"]["file"]
                source = target.read_text(encoding="utf-8")
                self.assertIn(task["reference_fix"]["old"], source, task["task_id"])
                patched = source.replace(task["reference_fix"]["old"], task["reference_fix"]["new"], 1)
                target.write_text(patched, encoding="utf-8", newline="\n")
                shutil.copyfile(self.validation, directory / "tests" / "test_validation.py")
                result = run_validation_test(directory, task["validation_test"])
                self.assertTrue(result["passed"], f"{task['task_id']}: {result['output']}")
                self.assertTrue(run_public_tests(directory)["passed"], task["task_id"])
            finally:
                shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
