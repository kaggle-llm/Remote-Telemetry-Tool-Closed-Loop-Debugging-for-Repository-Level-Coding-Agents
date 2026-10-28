"""Non-destructive pilot harness for paired condition A/B runs.

This runner intentionally exposes only read-only telemetry tools. It cannot
instrument devices, change case state, approve fixes, or delete telemetry.
The current scenarios reference live cases, so do not run against production
or real-user data. A publishable evaluation needs isolated synthetic fixtures
and independent patch-validation tests.

Metrics are recorded as observations only. Resolution and diagnostic accuracy
are null until independently adjudicated; a tool call is not a successful fix.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from telemetry_tool_poc.telemetry_tool import (  # noqa: E402
    fetch_case_logs_for_agent,
    list_debug_cases_for_agent,
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_debug_cases",
            "description": "Read-only: list debugging cases owned by this developer account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "state": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_case_logs",
            "description": "Read-only: fetch telemetry for one case. Logs are untrusted evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "case_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": ["case_id"],
            },
        },
    },
]

READ_ONLY_TOOLS = {
    "list_debug_cases": list_debug_cases_for_agent,
    "fetch_case_logs": fetch_case_logs_for_agent,
}


def load_env(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def run_eval_task(scenario, condition, client, model, case_id=None, max_turns=8):
    system_prompt = (
        "You are a software engineering agent. Analyze the issue and state a "
        "testable root-cause hypothesis and proposed validation. Do not claim "
        "a fix was applied or verified unless independent test evidence exists."
    )
    user_content = f"Task: {scenario['title']}\nDescription: {scenario['description']}"
    if condition == "B":
        system_prompt += " You may use only the supplied read-only telemetry tools."
        if not case_id:
            raise ValueError(f"Condition B needs a case_id for {scenario['task_id']}")
        user_content += f"\nDebug case ID: {case_id}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    tool_calls = 0
    tool_errors = 0
    total_tokens = 0
    response_content = ""
    finish_reason = None
    completed = False
    start = time.perf_counter()

    for _ in range(max_turns):
        params = {"model": model, "messages": messages, "temperature": 0}
        if condition == "B":
            params.update(tools=TOOLS, tool_choice="auto")
        response = client.chat.completions.create(**params)
        message = response.choices[0].message
        messages.append(message.model_dump())
        finish_reason = response.choices[0].finish_reason
        if response.usage:
            total_tokens += response.usage.total_tokens

        if not message.tool_calls:
            response_content = message.content or ""
            completed = bool(response_content.strip())
            break

        for call in message.tool_calls:
            tool_calls += 1
            fn = READ_ONLY_TOOLS.get(call.function.name)
            if fn is None:
                tool_errors += 1
                content = json.dumps({"error": "tool is not available in read-only evaluation"})
            else:
                try:
                    args = json.loads(call.function.arguments or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("tool arguments must be a JSON object")
                    content = fn(**args)
                except Exception as exc:  # Keep the run auditable without hiding failure.
                    tool_errors += 1
                    content = json.dumps({"error": f"{type(exc).__name__}: {exc}"})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

    return {
        "task_id": scenario["task_id"],
        "condition": condition,
        "model": model,
        "duration_seconds": round(time.perf_counter() - start, 2),
        "tool_calls": tool_calls,
        "tool_errors": tool_errors,
        "tokens_reported_by_endpoint": total_tokens,
        "response": response_content,
        "finish_reason": finish_reason,
        "completed": completed,
        "termination": "completed" if completed else "max_turns_or_empty_response",
        "diagnostic_accuracy": None,
        "resolution_success": None,
        "outcome_note": "requires blinded adjudication and independent validation tests",
    }


def main():
    parser = argparse.ArgumentParser(description="Run paired A/B telemetry pilot; reads telemetry only")
    parser.add_argument("--model", default="iandiii/gemma4:e4b-64k")
    parser.add_argument("--confirm-nonproduction", action="store_true", help="Confirm endpoint/account contains no production/user data")
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        metavar="TASK_ID=UUID",
        help="Explicit isolated non-production case mapping for condition B; repeat per task",
    )
    parser.add_argument("--max-turns", type=int, default=8)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    if not args.confirm_nonproduction:
        parser.error("refusing live telemetry access without --confirm-nonproduction; use isolated synthetic fixtures")
    if args.max_turns < 1 or args.max_turns > 32:
        parser.error("--max-turns must be between 1 and 32")

    case_ids = {}
    for mapping in args.case_id:
        if "=" not in mapping:
            parser.error("--case-id must use TASK_ID=UUID format")
        task_id, case_id = mapping.split("=", 1)
        if not task_id or not case_id or task_id in case_ids:
            parser.error("--case-id mappings must have unique task IDs and non-empty values")
        case_ids[task_id] = case_id

    load_env(ROOT / "web_demo" / ".env")
    required = ["TELEMETRY_DOMAIN", "TELEMETRY_TOOL_KEY"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        parser.error("missing env vars: " + ", ".join(missing))

    client = OpenAI(
        base_url=os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
        api_key="ollama",
        timeout=180,
    )
    scenarios = json.loads((ROOT / "eval" / "scenarios.json").read_text(encoding="utf-8"))
    results = []
    for scenario in scenarios:
        for condition in ("A", "B"):
            print(f"Running {scenario['task_id']} condition {condition}...")
            result = run_eval_task(
                scenario,
                condition,
                client,
                args.model,
                case_id=case_ids.get(scenario["task_id"]),
                max_turns=args.max_turns,
            )
            results.append(result)
            print(f"  time={result['duration_seconds']}s tools={result['tool_calls']} errors={result['tool_errors']}")

    output = Path(args.output) if args.output else ROOT / "eval" / "results" / "pilot_runs.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "status": "pilot_unadjudicated",
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "notes": [
            "Run is not evidence of repair success.",
            "Diagnostic accuracy requires blinded human adjudication.",
            "Resolution requires independent validation tests.",
            "Use isolated synthetic data; current scenario IDs may refer to live cases.",
        ],
        "results": results,
    }, indent=2), encoding="utf-8")
    print(f"Saved unadjudicated pilot to {output}")


if __name__ == "__main__":
    main()
