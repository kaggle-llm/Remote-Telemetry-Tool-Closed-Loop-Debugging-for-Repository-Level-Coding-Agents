# How Does the Gemma 4 Agent Call a Tool? (Tool Calling Mechanics)

Open-weight agent models such as Gemma 4 run external tools (functions) autonomously through the **Google Agent Development Kit (ADK)** and the standard **function calling** mechanism. The process works step by step as follows:

## 1. Configuration Definition (`agent.yaml`)
All tools the agent can access are declared in `agent.yaml`, with their function signatures and descriptions:
```yaml
tools:
  - name: fetch_client_logs
    description: Fetch runtime crash logs and telemetry from remote iOS/client applications stored in Supabase.
    entrypoint: telemetry_tool.py:fetch_client_logs
```

## 2. User Prompt
The user gives the agent this task:
> *"Find why the iOS app is crashing and fix the bug."*

## 3. Intent Detection by the Model (Tool Call Generation)
The Gemma 4 model reads the system prompt and the tool definitions, realizes it needs the remote client logs, and generates a tool call in the background:
```json
{
  "tool": "fetch_client_logs",
  "arguments": {
    "limit": 5
  }
}
```

## 4. Execution and Feedback by the Harness
* The Google ADK harness intercepts this JSON request.
* It runs the `fetch_client_logs(limit=5)` function from `telemetry_tool.py` in the Python environment.
* The log data returned by the function (in JSON format) is fed back into the model's context:
  ```json
  [
    {
      "id": 1,
      "client": "ios_app_v1.0",
      "level": "ERROR",
      "message": "Crash in UserProfileView: force unwrap optional nil at line 42"
    }
  ]
  ```

## 5. Autonomous Action (Action and Patch)
The agent reads the error message in the log, locates the relevant view file in the codebase (`grep` / `read`), applies the required fix and completes the solution.
