"""Paired A/B evaluation of case-scoped telemetry for a repository-level agent.

Every trial runs against a local fixture backend that serves synthetic cases
and synthetic telemetry rows only. The two conditions share the prompt, the
tool schemas, the model, the repository copy and the run order is randomized;
the only difference is whether the case-scoped telemetry contains diagnostic
events. Repair success is decided by executing the held-out validation test
that the agent never sees. Root-cause accuracy is adjudicated by a frozen
rubric that cannot observe the condition.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.agent_loop import Workspace, run_agent_trial  # noqa: E402
from eval.fixture_backend import (  # noqa: E402
    FixtureBackend,
    FixtureStore,
    synthetic_case_id,
    synthetic_tool_key,
)

EVAL_OWNER = "eval-owner"
CONDITIONS = ("A", "B")
NON_ALNUM = re.compile(r"[^a-z0-9]+")


def load_tasks(fixtures_dir: Path):
    payload = json.loads((fixtures_dir / "cases.json").read_text(encoding="utf-8"))
    tasks = payload["tasks"] if isinstance(payload, dict) else payload
    if not tasks:
        raise SystemExit("No tasks found in the fixture definition.")
    return tasks


def validation_source(fixtures_dir: Path) -> Path:
    candidates = [
        fixtures_dir / "validation" / "tests" / "test_validation.py",
        fixtures_dir / "validation" / "test_validation.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit("Pristine validation test file not found under eval/fixtures/validation.")


def prepare_workspace(fixtures_dir: Path, destination: Path):
    shutil.copytree(
        fixtures_dir / "repo",
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    hidden = destination / "tests" / "test_validation.py"
    if hidden.exists():
        hidden.unlink()


def seed_store(task, condition):
    case_id = synthetic_case_id(task["task_id"])
    key = synthetic_tool_key(task["task_id"], EVAL_OWNER)
    case = {
        "id": case_id,
        "owner_id": EVAL_OWNER,
        "title": task["title"],
        "user_report": task["report"],
        "state": "reported",
        "created_at": "2026-10-28T09:00:00.000Z",
        "updated_at": "2026-10-28T09:00:00.000Z",
    }
    logs = []
    if condition == "B":
        for index, event in enumerate(task.get("telemetry_events", [])):
            logs.append({
                "id": f"{case_id[:8]}-log-{index}",
                "case_id": case_id,
                "client_session_id": f"{case_id[:8]}-client",
                "level": event.get("level", "warn"),
                "event": event.get("event", "client_event"),
                "detail": event.get("detail", {}),
                "created_at": f"2026-10-28T09:0{index}:00.000Z",
            })
    store = FixtureStore([case], {case_id: logs}, {key: EVAL_OWNER})
    return store, case_id, key


def run_validation_test(workspace: Path, dotted_test: str):
    command = [sys.executable, "-m", "unittest", dotted_test]
    process = subprocess.run(
        command,
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    return {
        "passed": process.returncode == 0,
        "exit_code": process.returncode,
        "output": (process.stdout + process.stderr)[-4000:],
    }


def run_public_tests(workspace: Path):
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_public.py"]
    process = subprocess.run(
        command,
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    return {
        "passed": process.returncode == 0,
        "exit_code": process.returncode,
        "output": (process.stdout + process.stderr)[-4000:],
    }


def normalize(text: str) -> str:
    return NON_ALNUM.sub(" ", (text or "").lower()).strip()


def adjudicate(task, answer: str):
    """Rule-based, condition-blind adjudication against the frozen answer key."""
    lines = [line.strip() for line in (answer or "").splitlines()]
    root_cause_lines = [
        line.split("ROOT_CAUSE:", 1)[1].strip()
        for line in lines
        if "ROOT_CAUSE:" in line.upper()
    ]
    root_cause_text = " ".join(root_cause_lines)
    body = normalize(answer)
    claim = normalize(root_cause_text) if root_cause_text else ""
    keys = [normalize(phrase) for phrase in task.get("adjudication_key", []) if normalize(phrase)]
    matched = [phrase for phrase in keys if phrase in claim]
    if not matched and not root_cause_text:
        matched = [phrase for phrase in keys if phrase in body]
    return {
        "diagnostic_accurate": bool(matched),
        "matched_phrases": matched,
        "root_cause_statement": root_cause_text[:600],
    }


def run_trial(task, condition, repeat, fixtures_dir, validation_file, client, model, max_iterations, temperature):
    workspace_dir = Path(tempfile.mkdtemp(prefix="papertrack-eval-"))
    store, case_id, key = seed_store(task, condition)
    previous_domain = os.environ.get("TELEMETRY_DOMAIN")
    previous_key = os.environ.get("TELEMETRY_TOOL_KEY")
    backend = FixtureBackend(store)
    try:
        prepare_workspace(fixtures_dir, workspace_dir)
        url = backend.start()
        if not url.startswith("http://127.0.0.1"):
            raise RuntimeError("The evaluation refuses to run against a non-loopback endpoint.")
        os.environ["TELEMETRY_DOMAIN"] = url
        os.environ["TELEMETRY_TOOL_KEY"] = key
        workspace = Workspace(workspace_dir)
        transcript = run_agent_trial(
            task,
            case_id,
            workspace,
            client,
            model,
            max_iterations=max_iterations,
            temperature=temperature,
        )
        shutil.copyfile(validation_file, workspace_dir / "tests" / "test_validation.py")
        validation = run_validation_test(workspace_dir, task["validation_test"])
        public = run_public_tests(workspace_dir)
    finally:
        if previous_domain is None:
            os.environ.pop("TELEMETRY_DOMAIN", None)
        else:
            os.environ["TELEMETRY_DOMAIN"] = previous_domain
        if previous_key is None:
            os.environ.pop("TELEMETRY_TOOL_KEY", None)
        else:
            os.environ["TELEMETRY_TOOL_KEY"] = previous_key
        backend.stop()
        shutil.rmtree(workspace_dir, ignore_errors=True)

    adjudication = adjudicate(task, transcript["answer"])
    return {
        "task_id": task["task_id"],
        "repeat": repeat,
        "condition": condition,
        "model": model,
        "case_id": case_id,
        "resolution_success": bool(validation["passed"]),
        "public_tests_passed": bool(public["passed"]),
        "validation_test": task["validation_test"],
        "diagnostic_accurate": adjudication["diagnostic_accurate"],
        "matched_phrases": adjudication["matched_phrases"],
        "root_cause_statement": adjudication["root_cause_statement"],
        "tool_call_count": transcript["tool_call_count"],
        "tool_errors": transcript["tool_errors"],
        "telemetry_fetches": transcript["telemetry_fetches"],
        "edits": transcript["edits"],
        "total_tokens": transcript["total_tokens"],
        "prompt_tokens": transcript["prompt_tokens"],
        "completion_tokens": transcript["completion_tokens"],
        "duration_seconds": transcript["duration_seconds"],
        "termination": transcript["termination"],
        "answer": transcript["answer"][:4000],
    }


def mcnemar_exact(b, c):
    """Two-sided exact McNemar test on the discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def bootstrap_mean_ci(values, seed, iterations=10000):
    if not values:
        return {"mean": None, "low": None, "high": None}
    rng = random.Random(seed)
    means = []
    size = len(values)
    for _ in range(iterations):
        sample = [values[rng.randrange(size)] for _ in range(size)]
        means.append(sum(sample) / size)
    means.sort()
    low = means[int(0.025 * (iterations - 1))]
    high = means[int(0.975 * (iterations - 1))]
    return {"mean": sum(values) / size, "low": low, "high": high}


def summarize(runs, seed):
    pairs = {}
    for run in runs:
        pairs.setdefault((run["task_id"], run["repeat"]), {})[run["condition"]] = run

    both = [pair for pair in pairs.values() if "A" in pair and "B" in pair]
    b_only = sum(1 for pair in both if pair["B"]["resolution_success"] and not pair["A"]["resolution_success"])
    a_only = sum(1 for pair in both if pair["A"]["resolution_success"] and not pair["B"]["resolution_success"])
    both_pass = sum(1 for pair in both if pair["A"]["resolution_success"] and pair["B"]["resolution_success"])
    neither = sum(1 for pair in both if not pair["A"]["resolution_success"] and not pair["B"]["resolution_success"])

    diagnostic_b_only = sum(1 for pair in both if pair["B"]["diagnostic_accurate"] and not pair["A"]["diagnostic_accurate"])
    diagnostic_a_only = sum(1 for pair in both if pair["A"]["diagnostic_accurate"] and not pair["B"]["diagnostic_accurate"])
    diagnostic_both = sum(1 for pair in both if pair["A"]["diagnostic_accurate"] and pair["B"]["diagnostic_accurate"])

    token_deltas = [pair["B"]["total_tokens"] - pair["A"]["total_tokens"] for pair in both]
    duration_deltas = [pair["B"]["duration_seconds"] - pair["A"]["duration_seconds"] for pair in both]

    per_task = {}
    for pair in both:
        bucket = per_task.setdefault(pair["A"]["task_id"], {"pairs": 0, "a_success": 0, "b_success": 0, "a_accurate": 0, "b_accurate": 0})
        bucket["pairs"] += 1
        bucket["a_success"] += int(pair["A"]["resolution_success"])
        bucket["b_success"] += int(pair["B"]["resolution_success"])
        bucket["a_accurate"] += int(pair["A"]["diagnostic_accurate"])
        bucket["b_accurate"] += int(pair["B"]["diagnostic_accurate"])

    return {
        "pairs": len(both),
        "resolution": {
            "a_success": sum(1 for pair in both if pair["A"]["resolution_success"]),
            "b_success": sum(1 for pair in both if pair["B"]["resolution_success"]),
            "both_pass": both_pass,
            "neither": neither,
            "b_only": b_only,
            "a_only": a_only,
            "mcnemar_exact_p": mcnemar_exact(b_only, a_only),
        },
        "diagnostic_accuracy": {
            "a_accurate": sum(1 for pair in both if pair["A"]["diagnostic_accurate"]),
            "b_accurate": sum(1 for pair in both if pair["B"]["diagnostic_accurate"]),
            "both_accurate": diagnostic_both,
            "b_only": diagnostic_b_only,
            "a_only": diagnostic_a_only,
            "mcnemar_exact_p": mcnemar_exact(diagnostic_b_only, diagnostic_a_only),
        },
        "token_delta_b_minus_a": bootstrap_mean_ci(token_deltas, seed),
        "duration_delta_b_minus_a": bootstrap_mean_ci(duration_deltas, seed),
        "telemetry_fetches": {
            "a": sum(pair["A"]["telemetry_fetches"] for pair in both),
            "b": sum(pair["B"]["telemetry_fetches"] for pair in both),
        },
        "edits": {
            "a": sum(pair["A"]["edits"] for pair in both),
            "b": sum(pair["B"]["edits"] for pair in both),
        },
        "per_task": per_task,
    }


def write_markdown(summary, path: Path, model, seed, repeats):
    resolution = summary["resolution"]
    diagnostic = summary["diagnostic_accuracy"]
    tokens = summary["token_delta_b_minus_a"]
    lines = [
        "# Paired telemetry evaluation",
        "",
        f"- model: `{model}`",
        f"- seed: `{seed}`",
        f"- repeats per task: `{repeats}`",
        f"- paired trials: `{summary['pairs']}`",
        "- isolation: local fixture backend, synthetic case ids and rows only",
        "",
        "| Outcome | Condition A (no diagnostic events) | Condition B (diagnostic events) |",
        "| --- | --- | --- |",
        f"| Validation test passed | {resolution['a_success']}/{summary['pairs']} | {resolution['b_success']}/{summary['pairs']} |",
        f"| Root cause matched rubric | {diagnostic['a_accurate']}/{summary['pairs']} | {diagnostic['b_accurate']}/{summary['pairs']} |",
        f"| Telemetry fetches | {summary['telemetry_fetches']['a']} | {summary['telemetry_fetches']['b']} |",
        f"| File edits | {summary['edits']['a']} | {summary['edits']['b']} |",
        "",
        f"- discordant repair pairs: B only {resolution['b_only']}, A only {resolution['a_only']}, exact McNemar p = {resolution['mcnemar_exact_p']:.3f}",
        f"- discordant diagnosis pairs: B only {diagnostic['b_only']}, A only {diagnostic['a_only']}, exact McNemar p = {diagnostic['mcnemar_exact_p']:.3f}",
        f"- token delta (B - A): {tokens['mean']:.1f} (95% bootstrap CI {tokens['low']:.1f} to {tokens['high']:.1f})",
        "",
        "| Task | Pairs | A repaired | B repaired | A diagnosed | B diagnosed |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for task_id, bucket in summary["per_task"].items():
        lines.append(
            f"| {task_id} | {bucket['pairs']} | {bucket['a_success']} | {bucket['b_success']} | {bucket['a_accurate']} | {bucket['b_accurate']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description="Run the paired telemetry evaluation against the local fixture backend")
    parser.add_argument("--model", default="iandiii/gemma4:e4b-64k")
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/v1"))
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--max-iterations", type=int, default=12)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=20261028)
    parser.add_argument("--tasks", default="", help="Comma separated task ids to run")
    parser.add_argument("--out-dir", default=str(ROOT / "eval" / "results"))
    args = parser.parse_args()

    if args.repeats < 1 or args.max_iterations < 1:
        raise SystemExit("--repeats and --max-iterations must be positive.")

    fixtures_dir = ROOT / "eval" / "fixtures"
    tasks = load_tasks(fixtures_dir)
    if args.tasks:
        wanted = {item.strip() for item in args.tasks.split(",") if item.strip()}
        tasks = [task for task in tasks if task["task_id"] in wanted]
        if not tasks:
            raise SystemExit("No fixture task matched --tasks.")
    validation_file = validation_source(fixtures_dir)

    client = OpenAI(base_url=args.ollama_url, api_key="ollama", timeout=300)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    schedule = []
    for task in tasks:
        for repeat in range(1, args.repeats + 1):
            for condition in CONDITIONS:
                schedule.append((task, repeat, condition))
    random.Random(args.seed).shuffle(schedule)

    runs = []
    started = time.perf_counter()
    for index, (task, repeat, condition) in enumerate(schedule, start=1):
        print(f"[{index}/{len(schedule)}] {task['task_id']} repeat {repeat} condition {condition}", flush=True)
        try:
            result = run_trial(
                task,
                condition,
                repeat,
                fixtures_dir,
                validation_file,
                client,
                args.model,
                args.max_iterations,
                args.temperature,
            )
        except Exception as exc:
            result = {
                "task_id": task["task_id"],
                "repeat": repeat,
                "condition": condition,
                "model": args.model,
                "error": f"{type(exc).__name__}: {exc}",
                "resolution_success": False,
                "diagnostic_accurate": False,
                "total_tokens": 0,
                "duration_seconds": 0.0,
                "tool_call_count": 0,
                "tool_errors": 0,
                "telemetry_fetches": 0,
                "edits": 0,
            }
        runs.append(result)
        print(
            f"    repaired={result.get('resolution_success')} diagnosed={result.get('diagnostic_accurate')} "
            f"tokens={result.get('total_tokens')} tools={result.get('tool_call_count')} "
            f"seconds={result.get('duration_seconds')}",
            flush=True,
        )
        (out_dir / "ab_runs.json").write_text(
            json.dumps({
                "status": "paired_pilot",
                "model": args.model,
                "seed": args.seed,
                "repeats": args.repeats,
                "isolation": "local fixture backend with synthetic case ids and rows",
                "run_at_utc": datetime.now(timezone.utc).isoformat(),
                "runs": runs,
            }, indent=2),
            encoding="utf-8",
            newline="\n",
        )

    summary = summarize(runs, args.seed)
    summary["model"] = args.model
    summary["seed"] = args.seed
    summary["repeats"] = args.repeats
    summary["wall_clock_seconds"] = round(time.perf_counter() - started, 1)
    (out_dir / "ab_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8", newline="\n")
    write_markdown(summary, out_dir / "ab_summary.md", args.model, args.seed, args.repeats)
    print(json.dumps(summary["resolution"], indent=2))
    print(f"Saved runs and summary to {out_dir}")


if __name__ == "__main__":
    main()
