# Remote Client Telemetry for Repository-Level Coding Agents

## Abstract
Repository-level coding agents can inspect source code and run local tests, but they often lack access to failures observed on external clients such as iOS applications. This creates an observability gap: a developer may report that a feature failed, while the agent has neither the device state nor a structured diagnostic signal. We present **Remote Telemetry Tool**, a design and proof-of-concept (PoC) for exposing privacy-filtered client events to a coding agent through a narrowly scoped tool interface, extended into a **bidirectional, stateful, human-in-the-loop debugging protocol**. The system stores structured events in Supabase and lets an agent request recent, authorized records, correlate them with repository code, propose a patch, and validate it locally. Its distinguishing feature is a server-enforced case state machine (`reported → instrumenting → awaiting_recheck → rechecked → patch_ready → approved/rejected → resolved`) together with **runtime-selectable instrumentation probes**: the agent declares *what* the device should observe as data, rather than shipping blind logging code, and can withdraw that instrumentation deterministically when the case closes. The artifact implements this protocol against live Supabase RPCs with a custom Google OAuth backend; the end-to-end loop has not yet been exercised against a deployed project, and no Gemma 4 agent run has been evaluated. We therefore frame this work as an architecture and testable research proposal, and specify an evaluation protocol to measure whether the closed loop improves diagnosis and patch success without unacceptable privacy exposure, latency, or cost.

## 1. Introduction
Coding agents commonly operate inside a repository sandbox. That setting supports file inspection, code edits, and local test execution, but it does not automatically expose runtime behavior from a user's phone or another remote client. A report such as “the highlight palette does not open” is under-specified: the failure could arise from a missing state transition, a presentation-context issue, an authorization response, or a device-specific condition.

Remote telemetry may provide evidence that narrows this search. However, simply giving an agent broad database access is unsafe and can overwhelm its context with noisy or sensitive events. The central question is therefore: **Can a constrained, task-scoped telemetry tool provide coding agents with actionable remote-client evidence and improve debugging outcomes while limiting data exposure?**

Our contribution is an early prototype and evaluation proposal with three properties: (1) structured client events with explicit bounds and ownership, (2) a retrieval function with bounded filters and basic field redaction, and (3) an evaluation protocol that distinguishes diagnostic improvement from unsupported claims about end-to-end repair. We provide a mock Python data source, an optional PostgREST client implementation, unit tests, an illustrative Supabase schema, an iOS failure scenario, and a Vite presentation mock. The browser mock stores events only in memory and does not contact Supabase. The live service path and agent-harness integration have not yet been tested, and no repair-rate improvement is claimed.

## 2. System Design

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
4. **Re-check.** The user repeats the failing action and reports the outcome through `report_case_progress`, moving the case to `rechecked`.
5. **Analyze and patch.** The agent reads only case-scoped evidence through `read_case_logs`, separates observed evidence from inference, inspects the repository, and proposes a minimal patch. If the repository lacks a faithful client test, it reports that limitation rather than claiming the remote issue is fixed.
6. **Finalize.** The agent calls `finalize_case`, moving the case to `patch_ready`. The agent cannot skip this state, and it cannot mark a case approved on the user's behalf.
7. **Approve and clean up.** The user approves or rejects through `approve_case`. Only after approval may the agent call `cleanup_case`, which deletes the telemetry captured for that case and marks it `resolved`. The instrumentation probes are then removed from the client.

Two properties of this design are central to the paper's contribution. First, **runtime-selectable probes** decouple instrumentation from the deployment cycle: the agent can refine what it observes without requiring a new build to be shipped to the device for each diagnostic iteration, and the baseline client emits nothing until a probe is active. Second, **reversible instrumentation**: because probes are declared as data rather than inlined blindly into source, they can be withdrawn deterministically when the case closes, which is what makes the cleanup step meaningful rather than aspirational.

The state machine is enforced server-side in both the Express layer and the Supabase RPCs, so an agent that attempts to skip a stage receives an error rather than an inconsistent record.

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
## 4. Current Prototype and Artifact Status

The included `telemetry_tool.py` calls live session-scoped Supabase RPCs using a publishable key plus an AI tool key and session key. A custom Node backend validates Google OAuth, manages app-owned users and sessions, and exposes the full case lifecycle (`create_debug_case`, `request_instrumentation`, `await_user_recheck`, `report_case_progress`, `finalize_case`, `approve_case`, `cleanup_case`, `purge_case_logs`). Python unit tests mock the RPC client and validate key shape, bounds, redaction, and forwarding behavior. The Vite dashboard calls the Node backend that implements Google OAuth, app-owned sessions, key/session management, and test log routes. This code has not yet been deployed or tested end-to-end with Google OAuth and the Supabase project. The included `agent.yaml` is illustrative and must be validated against the exact competition harness/configuration before being described as executable ADK configuration.

The artifact now includes a full debugging state machine enforced server-side, runtime-selectable instrumentation probes whose capture objects are linked to the owning case, and reversible cleanup (`purge_case_logs` only runs after `approved`). New test cases validate state transitions, column/FK ordering, probe normalization, free-text scrubbing, and prompt-injection rejection. These items remain requirements for a live prototype: the RPC layer must be hardened against concurrent writes, network partitions, and malicious payload injection.

The SQL schema avoids Supabase Auth: a custom Node backend validates Google OAuth and creates app-owned `public.users` and opaque application sessions. API keys and AI sessions reference the app user UUID. The backend uses a server-only Supabase secret key, which bypasses RLS; route-level ownership checks, CSRF/origin defenses, rate limits, audit logging, and deployment hardening therefore require careful live review.

## 5. Evaluation Plan

We propose a controlled paired study on reproducible client-side debugging tasks. For each task, run the same agent/model, repository snapshot, compute budget, and prompt in two conditions: (A) repository and issue description only; (B) the same inputs plus access to the **full debugging loop** (case creation, instrumentation, re-check, approval, cleanup). Randomize run order and repeat tasks to account for model variability. Do not use private production user logs; use synthetic or consented, anonymized events.

Primary outcomes:
- **Issue resolution rate:** fraction of tasks whose independent validation tests pass.
- **Diagnostic accuracy:** whether the agent's stated root-cause hypothesis matches the task's adjudicated cause.
- **Time and tool efficiency:** wall-clock time, model tokens, and tool calls until a validated patch or stop.
- **Telemetry utility:** fraction of returned events judged relevant by blinded reviewers.
- **Safety and privacy:** unauthorized records returned, sensitive-field leakage, and injection-induced unsafe actions; target is zero for unauthorized access and leakage.
- **Protocol compliance:** fraction of cases that follow the intended state-transition sequence without manual SQL or out-of-band intervention.
- **Reversible-instrumentation overhead:** latency and extra tokens for probe declaration vs. blind inlined logging.

Report task count, model and harness versions, agent configuration, query limits, exclusions, failure cases, confidence intervals, and raw aggregate results where rules permit. Compare paired outcomes and provide ablations (for example, probe-based telemetry vs. blind logging, or access disabled entirely). Until these experiments are run, no performance gain should be claimed.
## 6. Limitations and Risks
Telemetry can be absent, delayed, duplicated, misleading, or too coarse to reproduce a UI defect. User/session identifiers and stack traces may be sensitive. Remote storage introduces network dependency, latency, cost, retention obligations, and an additional attack surface. Logs may contain attacker-controlled strings, so they must not be treated as trusted instructions. A tool that merely retrieves logs is not an autonomous repair system; reliable repair also requires repository access, tests or reproduction, authorization controls, and careful validation. Generalization beyond the evaluated app, event schema, model, and harness remains an empirical question.

## 7. Conclusion
Remote Client Telemetry for Repository-Level Coding Agents is a practical design for reducing the information gap between a local coding agent and failures observed on external clients. The artifact includes a custom Google OAuth backend, a Vite dashboard, an app-owned user/session model, and an AI-session-scoped RPC tool, but live integration remains unverified. Its research value depends on demonstrating that relevant telemetry improves diagnosis or validated repair compared with repository-only debugging. The next steps are to deploy and test OAuth/session security and scoped RPC behavior, validate the tool in the target agent harness, create reproducible client-debugging tasks, and run the paired evaluation described above.

## References and Reproducibility
Add primary references for the target coding-agent benchmark, Google ADK/harness documentation, Supabase Row Level Security, and relevant software telemetry/privacy work before submission. Record exact source versions and provide scripts, synthetic fixtures, and evaluation instructions. Do not redistribute competition data or artifacts unless the competition rules explicitly permit it.
