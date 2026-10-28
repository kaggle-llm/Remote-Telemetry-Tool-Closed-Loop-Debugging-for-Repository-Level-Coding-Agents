# Remote Client Telemetry for Repository-Level Coding Agents

## Abstract
Repository-level coding agents can inspect source code and run local tests but often lack evidence from failures observed on remote clients. We present **Remote Telemetry Tool**, a proof-of-concept architecture for task-scoped client telemetry and a human-in-the-loop debugging protocol. The design combines bounded event retrieval with server-enforced case transitions and runtime-selectable instrumentation probes that can be deactivated during cleanup. The artifact contains a Python tool client, Supabase schema and RPCs, a custom Google OAuth backend, and a read-only pilot evaluation harness. Unit tests exercise mocked tool behavior and state-machine rules; they do not establish deployment security, end-to-end reliability, or improved debugging outcomes. An earlier three-task exploratory run is invalid for efficacy claims because it reused live case identifiers, allowed state-mutating calls, and used unadjudicated heuristics. We report no diagnosis or repair benefit. We describe the implementation, safety boundaries, and a controlled evaluation protocol needed to test whether scoped telemetry improves diagnosis and validated repair.

## 1. Introduction
Coding agents commonly operate inside a repository sandbox. That setting supports file inspection, code edits, and local test execution, but it does not automatically expose runtime behavior from a user's phone or another remote client. A report such as “the highlight palette does not open” is under-specified: the failure could arise from a missing state transition, a presentation-context issue, an authorization response, or a device-specific condition.

Remote telemetry may provide evidence that narrows this search. However, simply giving an agent broad database access is unsafe and can overwhelm its context with noisy or sensitive events. The central question is therefore: **Can a constrained, task-scoped telemetry tool provide coding agents with actionable remote-client evidence and improve debugging outcomes while limiting data exposure?**

Our contribution is an early prototype and evaluation proposal: structured client events with bounds and ownership, case-scoped retrieval with basic field redaction, and a stateful protocol that distinguishes diagnostic evidence from verified repair. The repository includes a Python tool client, unit tests, Supabase schema and RPCs, an iOS failure scenario, and a Vite presentation mock. The browser mock stores events only in memory and does not contact Supabase. Mocked unit tests are not evidence of live deployment security or end-to-end behavior; neither has been validated here, and no repair-rate improvement is claimed.

## 2. System Design and Method

### 2.1 Client event capture
An instrumented client emits a compact event when a relevant operation fails or reaches an unexpected state. For the highlight-palette example, an event might include `event="highlight_palette_presentation_failed"`, a bounded error category, app/build version, operating-system version, and a correlation/session identifier. It should not include raw user content, access tokens, or unrestricted device data. Client-side instrumentation should report failures, not silently convert all ordinary UI states into errors.

### 2.2 Storage and access control
The proposed Supabase table uses an identity key, authenticated `user_id`, bounded `session_id` and `event`, a constrained severity level, a JSONB `detail` object, optional user-agent metadata, and a server-generated timestamp. A composite `(user_id, created_at DESC)` index supports user-scoped recent-event queries. The schema alone is not a security boundary: deployment must also enable Row Level Security (RLS), define policies for authenticated clients, and ensure the agent uses a server-side, short-lived, least-privilege identity. A Supabase service-role key must never be embedded in an iOS application or exposed to the model.

### 2.3 Agent tool boundary
The agent should not receive arbitrary SQL or unrestricted database credentials. The prototype's `fetch_client_logs` accepts a user ID, optional session and severity filters, a bounded lookback interval, and a capped result limit. It selects explicit columns, redacts a small set of sensitive JSON keys, truncates strings, and caps the response size. These are defense-in-depth measures, not comprehensive privacy protection. Authorization must come from a trusted host session and Supabase RLS, not from the model-provided `user_id` filter. The tool output is untrusted diagnostic data: log strings may contain secrets or prompt-injection text, so the agent must treat them as evidence rather than instructions. Every query should be auditable, and retention/deletion rules should be defined.

### 2.4 Debugging workflow
Read access alone does not close the loop with a remote client: an agent can observe an event but cannot ask the device to gather better evidence, cannot know whether the user's reproduction attempt succeeded, and cannot verify that a proposed patch actually fixed the reported symptom. The protocol implemented in this artifact is therefore a bidirectional, stateful, human-in-the-loop loop rather than a one-shot retrieval step.

1. **Report.** The client creates a `debug_cases` row through the management API, recording the failure title and the user's own description. No telemetry is captured by default; the baseline assumption is no error and no logging.
2. **Instrument.** The agent calls `request_instrumentation`, publishing runtime instrumentation probes (`probe_id`, `target`, `capture` object, `level`) and human-readable instructions. The instrumented client applies the probes at runtime and links every resulting event to the case, so evidence is scoped to one debugging attempt rather than to the whole account.
3. **Await re-check.** The agent calls `await_user_recheck`, which tells the user what to try and moves the case to `awaiting_recheck`. The client polls case state and instructions; the loop uses pull-based polling with a version counter, so no push infrastructure is required.
4. **Re-check.** The client reports its re-check outcome through `report_case_progress`, which records the report as a bounded entry in `case_reports` (a dedicated timeline table) and moves the case to `rechecked`. Storing re-check reports in their own table keeps the original `user_report` column's 4000-character limit from being exceeded by repeated re-checks.
5. **Analyze and patch.** The agent reads only case-scoped evidence through `read_case_logs`, separates observed evidence from inference, inspects the repository, and proposes a minimal patch. If the repository lacks a faithful client test, it reports that limitation rather than claiming the remote issue is fixed.
6. **Finalize.** The agent calls `finalize_case`, moving the case to `patch_ready`. The agent cannot skip this state, and it cannot mark a case approved on the user's behalf.
7. **Approve and clean up.** The user approves or rejects through `approve_case`. Only after approval may the agent call `cleanup_case`, which deletes the telemetry captured for that case, deactivates the case's instrumentation probes so the device stops collecting, and marks it `resolved`.

Two properties of this design are central to the paper's contribution. First, **runtime-selectable probes** decouple instrumentation from the deployment cycle: the agent can refine what it observes without requiring a new build to be shipped to the device for each diagnostic iteration, and the baseline client emits nothing until a probe is active. Second, **reversible instrumentation**: because probes are declared as data rather than inlined blindly into source, they can be withdrawn deterministically when the case closes, which is what makes the cleanup step meaningful rather than aspirational.

The intended state machine is enforced in both the Express layer and Supabase RPCs. Unit tests cover representative transition and validation behavior, but have not been supplemented with concurrency, fault-injection, or production deployment tests. An agent attempting a disallowed transition should receive an error rather than an inconsistent record.

## 3. Illustrative Scenario: iOS Highlight Palette
Suppose a user selects text and taps the highlight control, but the color palette does not appear. The client records a structured event such as:

```json
{
  "level": "error",
  "event": "highlight_palette_presentation_failed",
  "detail": {
    "view": "HighlightPaletteView",
    "action": "open_palette",
    "failure_code": "missing_presentation_context",
    "app_version": "1.2.0",
    "os_version": "iOS 18"
  }
}
```

The agent retrieves only events authorized for the debugging task. It searches the repository for the palette presentation path, examines state transitions and presentation context, and adds or updates a regression test where feasible. A log entry can guide investigation but does not prove the root cause: instrumentation may be incomplete, the event may be stale, and the reported failure may have another cause. A valid repair claim requires a test or a controlled reproduction that exercises the relevant behavior.
## 4. Implementation and Verification

The included `telemetry_tool.py` calls session-scoped Supabase RPCs using a publishable key, AI tool key, and session key. A custom Node backend is implemented to validate Google OAuth, manage app-owned users and sessions, and expose the case lifecycle (`create_debug_case`, `request_instrumentation`, `await_user_recheck`, `report_case_progress`, `finalize_case`, `approve_case`, `cleanup_case`, `purge_case_logs`). Python unit tests mock the RPC client and cover key shape, bounds, redaction, and forwarding behavior. The Vite dashboard calls the Node backend for OAuth, app-owned sessions, key/session management, and test log routes. The implementation has not been deployed or tested end-to-end with Google OAuth and Supabase. The included `agent.yaml` is illustrative and must be validated against the exact competition harness before being described as executable ADK configuration.

The schema and RPC implementation include case-linked instrumentation probes and cleanup logic intended to require approval before deleting case telemetry and deactivating its probes. Tests cover representative transitions, column/FK ordering, probe normalization, free-text scrubbing, and prompt-injection rejection. These checks are local tests, not a security audit or proof of transactional correctness under concurrent writes, network partitions, or malicious payloads.

The SQL schema avoids Supabase Auth: a custom Node backend validates Google OAuth and creates app-owned `public.users` and opaque application sessions. API keys and AI sessions reference the app user UUID. The backend uses a server-only Supabase secret key, which bypasses RLS; route-level ownership checks, CSRF/origin defenses, rate limits, audit logging, and deployment hardening therefore require careful live review.

## 5. Evaluation Protocol and Pilot Status

We have not yet conducted a controlled paired study and make no efficacy or repair-rate claim. An exploratory three-task run with `gemma4:31b:cloud` is retained in `eval/results/eval_summary.json` for auditability only; its measurements are explicitly marked invalid for publication. The first runner counted any tool call as a successful resolution, inferred diagnostic accuracy using a substring heuristic, reused live case IDs, and allowed state-mutating tools. Those measurements therefore do not establish diagnosis accuracy, repair, protocol compliance, or a valid paired comparison.

A valid follow-up study should use isolated synthetic cases and the same model, repository snapshot, prompt, and compute budget in both conditions: (A) issue and repository access only; (B) identical access plus read-only, case-scoped telemetry. Randomize run order and repeat each task to account for model variability. Freeze the task descriptions, known root causes, relevant evidence, and task-specific validation tests before running. Keep the agent away from answer keys and ensure both conditions have equivalent repository context and tool budgets. Repair success requires an independently executed task-specific test or controlled reproduction; root-cause accuracy requires blinded reviewer adjudication against a prespecified rubric. Analyze paired task outcomes, report uncertainty intervals and failures, and disclose exclusions. Until such a study is completed, no efficacy comparison is warranted.

The revised `eval/eval_runner.py` is a read-only pilot harness: it permits case listing and case-log retrieval only, records model-reported tokens, latency, and tool errors, and leaves `diagnostic_accuracy` and `resolution_success` unset for independent adjudication. It requires explicit confirmation before accessing telemetry and labels outputs `pilot_unadjudicated`. The existing scenarios still reference live case IDs, so use isolated fixtures and replace those IDs before running further experiments.

Planned outcomes include independently adjudicated diagnostic accuracy, validated repair rate, relevant-event fraction, unauthorized records or sensitive-field leakage, protocol compliance, tool-call count, wall-clock latency, and model-reported token usage. A separate security evaluation should test cross-user/cross-case access, oversized or malformed probe payloads, prompt injection in event fields, cleanup behavior, and authorization failures. Report task count, model and harness versions, run order, exclusions, uncertainty intervals, and failure cases. No performance gain is claimed until controlled experiments are completed.
## 6. Limitations and Risks
Telemetry can be absent, delayed, duplicated, misleading, or too coarse to reproduce a UI defect. User/session identifiers and stack traces may be sensitive. Remote storage introduces network dependency, latency, cost, retention obligations, and an additional attack surface. Logs may contain attacker-controlled strings, so they must not be treated as trusted instructions. A tool that merely retrieves logs is not an autonomous repair system; reliable repair also requires repository access, tests or reproduction, authorization controls, and careful validation. Generalization beyond the evaluated app, event schema, model, and harness remains an empirical question.

## 7. Conclusion
Remote Client Telemetry for Repository-Level Coding Agents is a practical design for reducing the information gap between a local coding agent and failures observed on external clients. The artifact includes a custom Google OAuth backend, a Vite dashboard, an app-owned user/session model, and an AI-session-scoped RPC tool, but live integration remains unverified. Its research value depends on demonstrating that relevant telemetry improves diagnosis or validated repair compared with repository-only debugging. The next steps are to deploy and test OAuth/session security and scoped RPC behavior, validate the tool in the target agent harness, create reproducible client-debugging tasks, and run the paired evaluation described above.

## References and Reproducibility
Add primary references for the target coding-agent benchmark, Google ADK/harness documentation, Supabase Row Level Security, and relevant software telemetry/privacy work before submission. Record exact source versions and provide scripts, synthetic fixtures, and evaluation instructions. Do not redistribute competition data or artifacts unless the competition rules explicitly permit it.
