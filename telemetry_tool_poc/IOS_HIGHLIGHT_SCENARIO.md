# Example Scenario: The iOS Highlight Color Palette Does Not Open

This scenario describes, end to end, the problem of users in an iOS application being unable to open the text highlight color palette, and how the **closed-loop telemetry protocol** resolves it. Each step has a corresponding live endpoint and tool.

| # | Step | Actor | Endpoint / Tool |
|---|---|---|---|
| 1 | Normal state: no error, no logs | — | — |
| 2 | The user sees the error and reports it to the AI | User | `POST /api/client/cases` |
| 3 | The AI instruments the code smartly and tracks events on the device | AI | `request_instrumentation` |
| 4 | The AI sends instructions and waits for a retry | AI → User | `await_user_recheck` + `POST /api/client/cases/:id/state` |
| 5 | The user retries and reports back to the AI | User | `POST /api/client/cases/:id/report` |
| 6 | The AI analyzes the logs and applies a patch | AI | `fetch_case_logs` + `finalize_case` |
| 7 | Once the user approves, the logs are removed from the code and the database | User + AI | `approve_case` + `cleanup_case` |

## Step 1: Normal State

By default the device **logs nothing**. The application only collects events when there is an active probe in the `case_probes` table. This lowers the cost/retention footprint and technically enforces the "no log capture" default.

## Step 2: The User Reports the Error

The user (the person holding the device) reports the error from the application:

```json
POST /api/client/cases
{
  "session_key": "tcs_...",
  "title": "Highlight palette does not open",
  "user_report": "I select text and tap highlight, but the color palette never appears."
}
```

The server creates a `debug_cases` row and sets the state to `reported`. The user's text is free-form; both the server and the Python tool scrub e-mail and address patterns.

> Note: The end user has no account identity. The device's `tcs_` client session key represents that device (and therefore the person using it), and the approval authority comes from that key. The developer's account is the Google account in the `users` table; the two must not be mixed up.

## Step 3: The AI Instruments Smartly

The AI declares **as data** which event should be collected; it does not write blind inline logging code:

```json
request_instrumentation(
  case_id = "...",
  instructions = "Reproduce the highlight flow and confirm the palette opens after the guard is applied.",
  probes = [{
    "probe_id": "palette_context",
    "target": "HighlightPaletteView.presentPalette",
    "capture": { "presentation_context": "true", "viewmodel_state": "true" },
    "level": "warn"
  }]
)
```

The application applies the probes at runtime; every collected event is linked to this case through `client_logs.case_id`. The state becomes `instrumenting`.

**Why runtime probes?** Every time the AI changes the code it would need a new build and deployment, which breaks the autonomous loop. The probe model separates instrumentation from distribution.

## Step 4: The AI Sends Instructions

The AI tells the user what to do and waits for a retry:

```json
await_user_recheck(
  case_id = "...",
  instructions = "Please select text and tap highlight again. The palette should now open."
)
```

The state becomes `awaiting_recheck`. The device polls the state and instructions with `POST /api/client/cases/:id/state` (no push infrastructure is needed; changes are detected with a version counter). The user sees the instructions and repeats the action.

## Step 5: The User Retries

The user tries again on the device and reports the result:

```json
POST /api/client/cases/:id/report
{
  "session_key": "tcs_...",
  "report": "Re-checked: the palette now opens and shows the yellow highlight."
}
```

The server appends the report to the `case_reports` timeline and sets the state to `rechecked`. This RPC only runs from the `awaiting_recheck` state; the report cannot be sent before the agent asks for it. Because `case_reports` is kept in a separate table, repeated re-checks do not exceed the 4000-character limit of the original `user_report` column.

## Step 6: The AI Analyzes the Logs and Applies a Patch

The AI reads only the logs that belong to **this case**:

```json
fetch_case_logs(case_id = "...", limit = 50)
```

Case-scoped reads, instead of reading all account-wide logs, eliminate the risk of patching the wrong incident and the context pollution that comes with it. The AI inspects the repository, tests the most likely root cause and proposes a minimal patch.

Then:

```json
finalize_case(case_id = "...")
```

The state becomes `patch_ready`. This transition is only possible from the `rechecked` state; the AI cannot claim "fixed" without user verification.

## Step 7: Approval and Cleanup

The user approves the solution:

```json
POST /api/client/cases/:id/approve
{ "session_key": "tcs_...", "approved": true }
```

The state becomes `approved`. **Only after approval** can the AI clean up:

```json
cleanup_case(case_id = "...")
```

This operation:
1. Deletes only the `client_logs` rows belonging to that case,
2. Deactivates the case's `case_probes` records (the device stops collecting events),
3. Sets the case to the `resolved` state.

`purge_case_logs` only runs from the `approved` state; cleanup without approval is impossible. The `debug_cases` row remains as an audit trail.

## Summary: The Three Design Decisions the Loop Rests On

1. **The state machine is enforced on the server.** Both the Express layer and the Supabase RPCs validate transitions; if the agent tries to skip a stage it gets an error, and no inconsistent record is created.
2. **Instrumentation is reversible.** Because probes are defined as data, removing them is deterministic; the "clean the logs out of the code" step becomes a concrete operation.
3. **Evidence scope is bound to the case.** Thanks to `client_logs.case_id`, every read belongs to exactly one debugging attempt.

## End-to-End Run

The script that exercises the live loop:

```powershell
python -m ai_client_demo.debug_loop_demo
```

The script runs the seven steps in order, reports the number of case-linked logs before step 7 and the number of logs deleted after cleanup, and never prints any secret to the screen.
