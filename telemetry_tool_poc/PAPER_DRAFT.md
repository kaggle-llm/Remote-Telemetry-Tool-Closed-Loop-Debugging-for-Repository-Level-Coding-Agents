# Remote Client Telemetry for Repository-Level Coding Agents

## Abstract
Repository-level coding agents can inspect source code and run local tests, but they often lack access to failures observed on external clients such as iOS applications. This creates an observability gap: a developer may report that a feature failed, while the agent has neither the device state nor a structured diagnostic signal. We present **Remote Telemetry Tool**, a design and proof-of-concept (PoC) for exposing privacy-filtered client events to a coding agent through a narrowly scoped tool interface. The proposed system stores structured events in Supabase and lets an agent request recent, authorized records, correlate them with repository code, propose a patch, and validate it locally. The current artifact implements only an in-memory mock source; it demonstrates serialization and retrieval behavior, not a live Supabase connection or an evaluated Gemma 4 agent. We therefore frame this work as an architecture and testable research proposal, and specify an evaluation protocol to measure whether telemetry improves diagnosis and patch success without unacceptable privacy exposure, latency, or cost.

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
1. The developer asks the agent to investigate a reported client failure.
2. The agent calls the telemetry tool with a bounded query; the tool authenticates and applies server-side scope and redaction.
3. The agent summarizes relevant events and identifies hypotheses, explicitly separating observed evidence from inference.
4. The agent inspects the local repository and tests the most plausible cause.
5. The agent proposes a minimal patch and runs available local tests. If the repository lacks a faithful client test, it reports that limitation rather than claiming the remote issue is fixed.
6. After deployment, newly captured events can be checked through a separate, authorized follow-up query.

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
The included `telemetry_tool.py` calls session-scoped Supabase RPCs using a publishable key plus an AI tool key and session key. Python unit tests mock the RPC client and validate key shape, bounds, redaction, and forwarding behavior. The Vite dashboard calls a Node backend that implements Google OAuth, app-owned sessions, key/session management, and test log routes. This code has not yet been deployed or tested end-to-end with Google OAuth and the Supabase project. The artifact does not implement native ADK runtime integration, an iOS repository patch, or a Gemma 4 run. The included `agent.yaml` is illustrative and must be validated against the exact competition harness/configuration before being described as executable ADK configuration.

The SQL schema is a starting point rather than a production security review. The current design avoids Supabase Auth: a custom Node backend validates Google OAuth and creates app-owned `public.users` and opaque application sessions. API keys and AI sessions reference the app user UUID. The backend uses a server-only Supabase secret key, which bypasses RLS; route-level ownership checks, CSRF/origin defenses, rate limits, audit logging, and deployment hardening therefore require careful live review. The Python tests validate local behavior only; they do not validate network, authorization, database policies, concurrency, or end-to-end agent behavior. These items remain requirements for a live prototype.

## 5. Evaluation Plan
We propose a controlled paired study on reproducible client-side debugging tasks. For each task, run the same agent/model, repository snapshot, compute budget, and prompt in two conditions: (A) repository and issue description only; (B) the same inputs plus access to scoped telemetry. Randomize run order and repeat tasks to account for model variability. Do not use private production user logs; use synthetic or consented, anonymized events.

Primary outcomes:
- **Issue resolution rate:** fraction of tasks whose independent validation tests pass.
- **Diagnostic accuracy:** whether the agent's stated root-cause hypothesis matches the task's adjudicated cause.
- **Time and tool efficiency:** wall-clock time, model tokens, and tool calls until a validated patch or stop.
- **Telemetry utility:** fraction of returned events judged relevant by blinded reviewers.
- **Safety and privacy:** unauthorized records returned, sensitive-field leakage, and injection-induced unsafe actions; target is zero for unauthorized access and leakage.

Report task count, model and harness versions, agent configuration, query limits, exclusions, failure cases, confidence intervals, and raw aggregate results where rules permit. Compare paired outcomes and provide ablations (for example, event metadata removed, or telemetry access disabled). Until these experiments are run, no performance gain should be claimed.

## 6. Limitations and Risks
Telemetry can be absent, delayed, duplicated, misleading, or too coarse to reproduce a UI defect. User/session identifiers and stack traces may be sensitive. Remote storage introduces network dependency, latency, cost, retention obligations, and an additional attack surface. Logs may contain attacker-controlled strings, so they must not be treated as trusted instructions. A tool that merely retrieves logs is not an autonomous repair system; reliable repair also requires repository access, tests or reproduction, authorization controls, and careful validation. Generalization beyond the evaluated app, event schema, model, and harness remains an empirical question.

## 7. Conclusion
Remote Client Telemetry for Repository-Level Coding Agents is a practical design for reducing the information gap between a local coding agent and failures observed on external clients. The artifact includes a custom Google OAuth backend, a Vite dashboard, an app-owned user/session model, and an AI-session-scoped RPC tool, but live integration remains unverified. Its research value depends on demonstrating that relevant telemetry improves diagnosis or validated repair compared with repository-only debugging. The next steps are to deploy and test OAuth/session security and scoped RPC behavior, validate the tool in the target agent harness, create reproducible client-debugging tasks, and run the paired evaluation described above.

## References and Reproducibility
Add primary references for the target coding-agent benchmark, Google ADK/harness documentation, Supabase Row Level Security, and relevant software telemetry/privacy work before submission. Record exact source versions and provide scripts, synthetic fixtures, and evaluation instructions. Do not redistribute competition data or artifacts unless the competition rules explicitly permit it.
