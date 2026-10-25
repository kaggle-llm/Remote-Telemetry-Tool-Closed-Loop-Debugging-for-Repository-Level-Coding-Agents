"""Run full agent tool-calling loop with local model and telemetry tools."""

import json
import os
import sys
from pathlib import Path
from openai import OpenAI

sys.path.append(str(Path(__file__).resolve().parent.parent))

from telemetry_tool_poc.telemetry_tool import (
    start_ai_session_for_agent,
    fetch_session_logs_for_agent,
    write_session_log_for_agent,
)

def load_client_env():
    env_path = Path("ai_client_demo/.env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip("\"'"))

def main():
    load_client_env()
    client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    model_name = "gemma4:31b:cloud"

    tools = [
        {
            "type": "function",
            "function": {
                "name": "start_ai_session",
                "description": "Start a fresh telemetry session for this AI run.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Short session label"}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_session_log",
                "description": "Write a diagnostic log event to the active AI telemetry session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "level": {"type": "string", "enum": ["info", "warn", "error"]},
                        "event": {"type": "string", "description": "Event name"},
                        "detail": {"type": "object", "description": "Context dict"}
                    },
                    "required": ["level", "event", "detail"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_session_logs",
                "description": "Fetch recent client logs for this AI session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Max records"}
                    }
                }
            }
        }
    ]

    messages = [
        {"role": "system", "content": "You are an autonomous software engineering agent. First start an AI session named 'gemma-execution-test', then write a test error log about highlight palette failing, and finally fetch the session logs to verify."},
        {"role": "user", "content": "Investigate the iOS highlight palette bug using telemetry tools."}
    ]

    print(f"Running agent loop with model {model_name}...")
    for turn in range(4):
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            print("Agent finished execution:", msg.content)
            break

        print(f"--- Turn {turn + 1}: Model requested {len(msg.tool_calls)} tool call(s) ---")
        for call in msg.tool_calls:
            fn_name = call.function.name
            args = json.loads(call.function.arguments or "{}")
            print(f"Executing tool '{fn_name}' with args {args}...")

            result_str = ""
            try:
                if fn_name == "start_ai_session":
                    result_str = start_ai_session_for_agent(name=args.get("name", "AI run"))
                elif fn_name == "write_session_log":
                    result_str = write_session_log_for_agent(
                        level=args.get("level", "error"),
                        event=args.get("event", "unknown_error"),
                        detail=args.get("detail", {})
                    )
                elif fn_name == "fetch_session_logs":
                    result_str = fetch_session_logs_for_agent(limit=args.get("limit", 20))
                else:
                    result_str = json.dumps({"error": f"Unknown tool {fn_name}"})
            except Exception as exc:
                result_str = json.dumps({"error": str(exc)})

            print(f"Tool result: {result_str}")
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "name": fn_name,
                "content": result_str,
            })

if __name__ == "__main__":
    main()
