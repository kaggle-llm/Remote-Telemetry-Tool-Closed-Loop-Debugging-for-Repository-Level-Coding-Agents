# Remote Client Telemetry for Repository-Level Coding Agents: A Closed-Loop Debugging Protocol

*Consent-scoped device telemetry, withdrawable instrumentation, and server-enforced separation of evidence from repair validation for small local coding agents*

## Abstract

Repository-level coding agents can read source code and run local tests, but they cannot observe failures on a user's remote device. We present **Remote Telemetry Tool**, a prototype architecture that gives a coding agent task-scoped client telemetry and closes the loop between diagnosis, repair, and device-side verification. It combines bounded, redacted event retrieval; a server-enforced case state machine that the agent cannot skip and cannot approve on the user's behalf; and runtime-selectable instrumentation probes published as data and withdrawn at cleanup, so a client emits nothing until an agent asks for evidence. We report a paired evaluation in which the same local Gemma 4 model, the same prompts, the same tools and the same repository copies were run with and without diagnostic telemetry on six synthetic client failures, with repair decided by a held-out test the agent never saw and run order randomized. We also ship the missing client half: a probe runtime that applies published probes, emits case-scoped bounded events, withdraws them when a case closes, and stops collecting when the probe set cannot be confirmed. The artifact contains a Python tool library, a Supabase schema with security-definer RPCs, a Google OAuth backend, a dashboard, an agent runner, a synthetic evaluation harness with a fixture backend, and an offline adversarial suite. Verification covers 54 unit tests over mocked tool behavior, 37 harness tests, 21 adversarial tests, and the paired pilot; no deployment-security or production-reliability claim is made.

## 1. Introduction

Coding agents operate inside a repository sandbox that supports file inspection, code edits and local test execution, but it does not expose runtime behavior from a user's phone or another remote client. A report such as "the highlight palette does not open" is under-specified: the failure could arise from a missing state transition, a presentation-context issue, an authorization response, or a device-specific condition.

Remote telemetry could narrow that search, but giving an agent broad database access is unsafe and can flood a limited context window with noisy or sensitive events. The central question is therefore:

> **Can a constrained, task-scoped telemetry tool give repository-level coding agents actionable remote-client evidence without widening data exposure, and does that evidence improve debugging outcomes?**

Our contribution is a protocol, its client and server halves, and a controlled measurement of what the evidence is worth.

1. **A closed debugging loop.** A case object carries evidence from a user's report to an agent's proposal, and a server-enforced state machine separates *evidence collected* from *repair validated*. The agent cannot skip the user, and it cannot approve a fix on the user's behalf.
2. **Reversible, runtime-selectable instrumentation.** Probes are declared as data and published to a case, so an agent can refine what it observes without shipping a new build per iteration, and instrumentation can be withdrawn when the case closes. The default client emits nothing.
3. **An explicit verification boundary.** We separate what the artifact implements from what it has not been shown to do, and we report a paired pilot, an invalid earlier run kept for audit, and an adversarial suite rather than a claim.

The artifact is implemented in Python, SQL, JavaScript and JSON. Everything below was produced by the harness in this repository; where a result is missing we say so.

## 2. Related Work

The references below are representative, and are chosen to locate the contribution against the work a reviewer is most likely to compare it with.

*Repository-level agents and benchmarks.* SWE-bench [1] evaluates whether models resolve real GitHub issues from an issue description and a repository snapshot; SWE-agent [2] shows that the agent-computer interface, not only the model, materially changes performance; Agentless [3] shows that a simple localization-repair-validation pipeline can beat complex scaffolds. All three observe failures through the repository and the test harness. Mobile agent work gets closer to the device: AppAgent [13] operates smartphone applications through a tap-and-swipe action space, Mobile-Agent-v2 [12] adds planning, decision and reflection over screen history, and AndroidWorld [14] validates task success by inspecting device system state. Those systems read the device through pixels or a benchmark harness; none lets an agent *select runtime instrumentation* on a user's device and read back the structured result.

*Closed-loop repair and runtime evidence.* The monitor-analyze-plan-execute loop of autonomic computing [9] is the canonical closed-loop architecture, and RepairAgent [10] drives an LLM repair agent with a finite state machine that interleaves evidence gathering, repair and validation, while RCAgent [11] diagnoses a deployed cloud system from runtime evidence collected with tools. On instrumentation, TaintDroid [15] records information-flow facts on a real device, Sage [16] localizes root causes from distributed traces and applies corrective actions, and fault-injection tools inject runtime faults and tear them down afterwards [17]. Our claim is narrower: we do not propose a new event format, control loop or analysis technique. We propose the *protocol* that joins them for an agent debugging one user's device under a human approval gate, in which instrumentation is published as data by the agent, scoped to one case, and withdrawn when the case closes.

*Untrusted tool output and small local models.* Retrieved or tool-returned content can hijack an agent's instructions [18], and AgentDojo [19] is the standard benchmark for that risk; our tool output is therefore evidence, never instructions, and the harness asserts this. AgentBench [20] reports that open models trail much larger ones, which is why our measurement uses a small local Gemma 4 build, and SWE-Gym [21] shows that execution feedback can train agents and verifiers, the natural direction for case-scoped telemetry as a training signal. RULER [22] reports that claimed context windows overstate usable context for small open models, and vLLM [23] makes local runs reproducible.

The gap we claim is narrow and testable: **no reviewed system treats the end user's device as an explicit participant in an agentic debugging loop with agent-selected, withdrawable instrumentation, a server-enforced separation between evidence collection and repair validation, a human approval gate before telemetry deletion, and a paired measurement of the evidence's value.**

## 3. System Design and Method

### 3.1 Client event capture

An instrumented client emits a compact event when a relevant operation fails: a bounded event name, a bounded error category, app and build version, OS version, and a correlation identifier. It excludes raw user content, access tokens, and unrestricted device data. By default the client collects nothing; capture is attached to an active probe for a specific case.

### 3.2 Storage and access control

The Supabase schema defines app-owned `public.users`, `public.app_sessions`, `public.client_logs`, `public.debug_cases`, `public.case_probes`, `public.case_reports`, `public.tool_api_keys` and `public.ai_sessions`. A `client_logs` row carries a bounded `level`, a bounded `event` name, a JSONB `detail` object, optional user-agent metadata, a server-generated timestamp, and a nullable `case_id` linking the event to the debugging attempt that requested it; a composite `(user_id, created_at DESC)` index supports recent-event queries, and `case_id` filtering keeps case reads cheap.

The schema is not by itself a security boundary. Every access goes through security-definer RPCs that hash the presented key, resolve it to an owning `user_id`, and verify that the requested case belongs to that user before returning or mutating anything; the functions pin `search_path = ''` and revoke execute privileges from `public`, `anon` and `authenticated` before targeted grants. The backend holds a server-only Supabase secret key that bypasses RLS, so the rules currently live in application code and RPC bodies; a deployment must add independent defense in depth and must never expose that key to a client or to model context.

### 3.3 Agent tool boundary

The agent never receives arbitrary SQL or unrestricted credentials. `telemetry_tool.py` exposes one agent-facing function per capability; each validates its arguments locally, calls the management API with a developer key, and returns JSON to the model (Table 1).

| Tool (agent-facing function) | Bounds enforced before the call |
| --- | --- |
| `list_debug_cases_for_agent(limit, state)` | `limit` 1..100; known `state` |
| `fetch_case_logs_for_agent(case_id, limit)` | UUID `case_id`; `limit` 1..100 |
| `fetch_recent_client_logs_for_agent(limit, client_session_id)` | `limit` 1..100; optional session filter |
| `request_instrumentation_for_agent(case_id, instructions, probes)` | <=20 probes; `probe_id` <=80 chars; `target` <=200; `level` in {info, warn, error}; `capture` an object |
| `await_user_recheck_for_agent(case_id, instructions, probes)` | Same probe bounds; probes optional |
| `finalize_case_for_agent(case_id)` | Only from `rechecked` |
| `abandon_case_for_agent(case_id)` | Only from non-terminal states |
| `cleanup_case_for_agent(case_id)` | Only from `approved`; deletes telemetry and deactivates probes |

Output is bounded as well as input. Detail objects are redacted recursively against a fixed set of sensitive keys; free-text fields are scrubbed for e-mail addresses and long digit runs and truncated at 4000 characters; row count and total response size are capped at 256 KB. These are defense-in-depth measures, not a privacy guarantee.

Tool output is untrusted diagnostic data: log strings can contain secrets or prompt-injection text, so the agent must treat retrieved events as evidence, never instructions. Every call is authenticated by key and scoped to one account, and the model cannot widen that scope because filters are validated and ownership re-checked server-side.

Figure 1 shows the surface the agent can reach and the boundary it cannot cross.

![Figure 1: Trust boundaries between the agent and the server.](figure_trust_boundaries.png)

### 3.4 The closed debugging loop

Read access alone does not close the loop: an agent can observe an event but cannot ask the device for better evidence, cannot know whether the reproduction attempt succeeded, and cannot verify that a patch fixed the symptom. The protocol is therefore bidirectional, stateful, and human-in-the-loop.

![Figure 2: The closed debugging loop.](figure_closed_loop.png)

1. **Report.** The client creates a `debug_cases` row with the failure title and the user's own description. No telemetry is captured by default.
2. **Instrument.** The agent publishes probes (`probe_id`, `target`, bounded `capture` object, `level`) plus instructions; the client applies them at runtime and links every resulting event to the case, so evidence is scoped to one attempt.
3. **Await re-check.** The agent tells the user what to try and the case moves to `awaiting_recheck`; the client polls case state with a version counter, so no push infrastructure is required.
4. **Re-check.** The client reports its outcome through `report_case_progress`, which appends a bounded entry to `case_reports` and moves the case to `rechecked`; a timeline table keeps repeated re-checks from overflowing the report column.
5. **Analyze and patch.** The agent reads only case-scoped evidence, separates observation from inference, inspects the repository, and proposes a minimal patch. Without a faithful client test, it reports that limitation instead of claiming the remote issue is fixed.
6. **Finalize.** The agent calls `finalize_case`, moving the case to `patch_ready`; it cannot skip this state and cannot approve on the user's behalf.
7. **Approve and clean up.** The user approves or rejects through `approve_case`. Only after approval may the agent call `cleanup_case`, which deletes the case's telemetry, deactivates its probes so the device stops collecting, and marks the case `resolved`.

Table 2 gives the state machine, enforced twice in the Express layer and in the RPCs, so a disallowed transition yields an error rather than an inconsistent record.

| State | Meaning | Allowed next states |
| --- | --- | --- |
| `reported` | Failure reported | `instrumenting`, `abandoned` |
| `instrumenting` | Probes live | `awaiting_recheck`, `instrumenting`, `abandoned` |
| `awaiting_recheck` | Reproduction asked | `rechecked`, `instrumenting`, `abandoned` |
| `rechecked` | Outcome in | `patch_ready`, `instrumenting`, `abandoned` |
| `patch_ready` | Fix ready | `approved`, `rejected`, `instrumenting`, `abandoned` |
| `approved` | Fix accepted | `resolved` |
| `rejected` | Fix refused | `instrumenting`, `abandoned` |
| `resolved` | Cleaned up | none (terminal) |
| `abandoned` | Ended | none (terminal) |

Figure 3 draws the same machine as a transition graph, including the returns to `instrumenting` and the terminal states.

![Figure 3: The server-enforced case state machine.](figure_state_machine.png)

Two properties carry the contribution. **Runtime-selectable probes** decouple instrumentation from the deployment cycle, so diagnostic iterations do not require a new build and the baseline client emits nothing until a probe is active. **Reversible instrumentation** follows from probes being data rather than inlined source: they can be withdrawn when the case closes, which is what makes cleanup meaningful rather than aspirational.

### 3.5 The client probe runtime

The device half is a library, not a script. `ai_client_demo/probe_runtime.py` polls the case endpoint, receives the active probe set, applies probes to instrumentation points in the app, and emits bounded events linked to that case. Four behaviors are enforced and tested. *Silence by default*: with no probe set, no event is emitted. *Selection at runtime*: probes are fetched as data, so a new diagnostic needs no client build. *Allow-listed capture*: only the fields named in a probe's `capture` object are recorded, and detail size is capped. *Withdrawal*: when the case reaches a terminal state the probes are dropped and the client stops collecting; when the probe set cannot be confirmed, for example because the management API is unreachable, the runtime fails closed and emits nothing. `probe_runtime_demo.py` prints the whole lifecycle without a backend.

### 3.6 Illustrative scenario: iOS highlight palette

A user selects text and taps the highlight control, but the color palette never appears. The client records a structured event such as:

```json
{"level": "error", "event": "highlight_palette_presentation_failed",
 "detail": {"view": "HighlightPaletteView", "failure_code": "missing_presentation_context",
            "app_version": "1.2.0", "os_version": "iOS 18"}}
```

The agent retrieves only events authorized for that case, searches the repository for the palette presentation path, examines state transitions and presentation context, and updates a regression test where feasible. The event guides the search but does not prove the root cause: instrumentation may be incomplete, the event may be stale, or the failure may have another cause. A valid repair claim requires a test or a controlled reproduction.

## 4. Implementation

The artifact has five implementation parts.

*Agent tool library and database.* `telemetry_tool.py` validates arguments (UUIDs, limits, probe shapes), posts to the management API and returns JSON strings; it never receives a Supabase key, and session keys stay hidden from model-visible output. `supabase_setup.sql` and `migration_debug_cases.sql` define the schema, RPCs, grants and case tables; `lint_schema.py` checks foreign-key column ordering before a migration is applied, and `check_schema.py` probes a deployed schema for the expected objects.

*Backend and dashboard.* `web_demo/server/server.js` is an Express server with Google OAuth, app-owned users and opaque sessions, separate developer and ingest keys (distinct prefixes, hashed at rest, individually revocable), and the case lifecycle over HTTP: `/api/client/cases/*` for the client and `/api/tool/cases/*` for the agent. `web_demo/src/main.js` is a Vite dashboard for sign-in, keys, case listing, probe inspection, re-check feedback and approval.

*Agent and client.* `ollama_agent.py` exposes the protocol as OpenAI-compatible function tools for an Ollama-hosted agent with workspace read, patch and test tools; `ai_client_demo/probe_runtime.py` is the client probe runtime, and `ai_client_demo/debug_loop_demo.py` drives the full loop against a running backend.

*Evaluation.* `eval/` contains the paired harness: a synthetic six-task application, a fixture backend serving owner-scoped synthetic cases and telemetry rows, an agent loop with a read-only telemetry surface, and the statistics. No production data, no live case identifiers and no network endpoint other than the local model are involved.

## 5. Experiments and Evaluation

### 5.1 Verification performed

Table 3 reports the test suites. The first four are deterministic unit tests over mocked clients; the last three are the evaluation harness, the adversarial suite and the client probe runtime.

| Suite | Command | Tests | Result |
| --- | --- | --- | --- |
| `web_demo/src/case_actions.test.js` | `npm run test:ui` | 7 | pass |
| `web_demo/server/server.test.js` | `npm run test:api` | 21 | pass |
| `telemetry_tool_poc/test_telemetry_tool.py` | `python -m unittest discover -s telemetry_tool_poc` | 12 | pass |
| `test_ollama_agent.py` | `python -m unittest test_ollama_agent` | 14 | pass |
| `eval/test_eval_harness.py` | `python -m unittest eval.test_eval_harness` | 19 | pass |
| `eval/test_adversarial.py` | `python -m unittest eval.test_adversarial` | 21 | pass |
| `ai_client_demo/test_probe_runtime.py` | `python -m unittest discover -s ai_client_demo` | 9 | pass |

These suites are not a security audit, not a proof of correctness under concurrency or network partitions, and not evidence that a deployed system behaves as the mocks do; the loop has been driven against a local backend, not a deployed Supabase project with production OAuth.

### 5.2 An exploratory run that we do not report as evidence

A three-task exploratory run with `gemma4:31b:cloud` is retained in `eval/results/eval_summary.json` for auditability only and is marked invalid for publication: the first runner counted any tool call as a resolution, inferred accuracy with a substring heuristic, reused live case identifiers, and allowed state-mutating tools, so it cannot establish diagnosis accuracy, repair, protocol compliance, or a paired comparison. We kept it in the repository because deleting an inconvenient result is itself a methodological failure.

### 5.3 Paired evaluation: task-scoped telemetry against none

<<RESULTS_SECTION>>

### 5.4 Adversarial and safety evaluation

The same harness runs an offline adversarial suite that exercises the attack surfaces named above: cross-user and cross-case reads, ingest keys attempting agent endpoints, revoked and unknown keys, malformed and oversized probe payloads, oversized responses, prompt-injection text inside telemetry fields, and the read-only tool surface of the evaluation itself. A separate set of checks reads the SQL sources and asserts that the case functions are security-definer with a pinned `search_path`, that client-facing functions revoke public execution, that agent-only functions are granted only to the service role, and that case ownership is checked in both the ingest and the tool paths. These are invariant tests over the artifact, not a penetration test of a deployment.

## 6. Limitations and Risks

Telemetry can be absent, delayed, duplicated, misleading, or too coarse to reproduce a UI defect. Identifiers, user descriptions and stack traces may be sensitive, and redaction is a mitigation rather than a guarantee. Remote storage adds network dependency, latency, cost, retention obligations and an attack surface, and log content is attacker-controllable, so it must never be treated as trusted instructions. A retrieval tool is not an autonomous repair system: reliable repair also needs repository access, tests, authorization controls and validation. The evaluation uses six synthetic tasks and one small local model, so its numbers describe this artifact rather than the class of systems it resembles. The probe runtime is a library with a deterministic offline demo, not a shipped mobile application, and the server-side rules have been exercised only against mocks and a fixture backend.

## 7. Conclusion

Task-scoped remote telemetry closes the information gap between a local coding agent and a failure that only happens on the user's device. The design combines bounded, redacted retrieval with a server-enforced protocol that separates evidence collection from repair validation, and with instrumentation that can be added and withdrawn at runtime. The artifact now implements that protocol end to end: tool library, schema, OAuth backend, dashboard, agent runner, client probe runtime, paired evaluation harness and adversarial suite, with 54 artifact unit tests, 49 harness and adversarial tests and 9 probe-runtime tests passing. What the evidence is worth is reported in Section 5.3 without exaggeration; next steps are a deployment review of the OAuth and key model, a real client with a shipped probe runtime, larger task sets, and turning case-scoped telemetry into a training signal as SWE-Gym does for repository execution.

## References

1. C. E. Jimenez et al., "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?" ICLR 2024. arXiv:2310.06770.
2. J. Yang et al., "SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering." NeurIPS 2024. arXiv:2405.15793.
3. C. S. Xia, Y. Deng, S. Dunn and L. Zhang, "Agentless: Demystifying LLM-based Software Engineering Agents." FSE 2025. arXiv:2407.01489.
4. S. Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models." ICLR 2023. arXiv:2210.03629.
5. Google, "Agent Development Kit (ADK) documentation." https://google.github.io/adk-docs/
6. Gemma Team, "Gemma 4 Technical Report," 2026. arXiv:2607.02770.
7. Supabase, "Row Level Security." https://supabase.com/docs/guides/database/postgres/row-level-security
8. Supabase, "Database functions." https://supabase.com/docs/guides/database/functions
9. J. O. Kephart and D. M. Chess, "The vision of autonomic computing." Computer 36(1), 2003. doi:10.1109/MC.2003.1160055.
10. I. Bouzenia, P. Devanbu and M. Pradel, "RepairAgent: An Autonomous, LLM-Based Agent for Program Repair." ICSE 2025. arXiv:2403.17134.
11. Z. Wang et al., "RCAgent: Cloud Root Cause Analysis by Autonomous Agents with Tool-Augmented Large Language Models." CIKM 2024. arXiv:2310.16340.
12. J. Wang et al., "Mobile-Agent-v2: Mobile Device Operation Assistant with Effective Navigation via Multi-Agent Collaboration." NeurIPS 2024. arXiv:2406.01014.
13. C. Zhang et al., "AppAgent: Multimodal Agents as Smartphone Users." CHI 2025. arXiv:2312.13771.
14. C. Rawles et al., "AndroidWorld: A Dynamic Benchmarking Environment for Autonomous Agents." ICLR 2025. arXiv:2405.14573.
15. W. Enck et al., "TaintDroid." ACM Trans. Comput. Syst. 38(3), 2014. doi:10.1145/2619091.
16. Y. Gan et al., "Sage: practical and scalable ML-driven performance debugging in microservices." ASPLOS 2021. arXiv:2101.00267.
17. M. Assad et al., "Can My Microservice Tolerate an Unreliable Database? Resilience Testing with Fault Injection and Visualization." ICSE-Companion 2024. arXiv:2404.01886.
18. K. Greshake et al., "Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection." ACM AISec 2023. arXiv:2302.12173.
19. E. Debenedetti et al., "AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents." NeurIPS 2024 Datasets and Benchmarks. arXiv:2406.13352.
20. X. Liu et al., "AgentBench: Evaluating LLMs as Agents." ICLR 2024. arXiv:2308.03688.
21. J. Pan et al., "Training Software Engineering Agents and Verifiers with SWE-Gym." ICML 2025. arXiv:2412.21139.
22. C.-P. Hsieh et al., "RULER: What's the Real Context Size of Your Long-Context Language Models?" COLM 2024. arXiv:2404.06654.
23. W. Kwon et al., "Efficient Memory Management for Large Language Model Serving with PagedAttention." SOSP 2023. arXiv:2309.06180.

## Reproducibility

The artifact ships the tool library, schema and migrations, linter and checker, Express backend, Vite dashboard, agent runner, client probe runtime, evaluation harness, synthetic task fixtures, adversarial suite, and this write-up with its source. Test suites run with `npm run test:api` and `npm run test:ui` in `web_demo/`, `python -m unittest discover -s telemetry_tool_poc`, `python -m unittest test_ollama_agent`, `python -m unittest eval.test_eval_harness eval.test_adversarial` and `python -m unittest discover -s ai_client_demo`. The paired pilot runs with `python eval/eval_runner.py --repeats 3`, which starts its own fixture backend on a loopback port and never contacts a deployed service.
