# Remote Telemetry Tool: Research Prototype

## Overview
This workspace contains an early-stage research prototype for the **Google - The Gemma 4 Developer Agent Paper Track**. It explores bridging remote client telemetry (iOS/Edge apps) with coding agents. The dashboard now has a custom Google OAuth backend and session-scoped key model; live Google/Supabase deployment and agent integration still require configuration and end-to-end validation.

---

## Package Contents & File Index

1. **`PROJECT_PLAN.md`**
   - High-level analysis of the Gemma 4 Developer Agent Paper Track, evaluation criteria, and step-by-step roadmap.

2. **`TELEMETRY_TOOL_IDEA.md`**
   - Core research concept: Solving remote client blind spots for local autonomous agents using cloud telemetry.

3. **`telemetry_tool_poc/supabase_setup.sql`**
   - SQL setup for app-owned `public.users` and app sessions, per-user tool keys/AI sessions, and session-scoped log RPCs. Does not rely on Supabase Auth. Review/migrate existing data before applying.

4. **`telemetry_tool_poc/SUPABASE_SCHEMA.md`**
   - Google OAuth configuration, key/session flow, security notes, and Python agent-tool setup.

5. **`telemetry_tool_poc/telemetry_tool.py`**
   - Python proof-of-concept agent tool library: session-scoped log read/write, plus the new case-scoped debugging-loop tools (`list_debug_cases`, `fetch_case_logs`, `request_instrumentation`, `await_user_recheck`, `finalize_case`, `abandon_case`, `cleanup_case`).

6. **`telemetry_tool_poc/agent.yaml`**
   - Illustrative agent/tool configuration; not verified against the competition harness.

7. **`telemetry_tool_poc/TOOL_CALLING_EXPLAINED.md`**
   - Technical breakdown of how Gemma 4 autonomously triggers tool calls based on context and task prompts.

8. **`telemetry_tool_poc/AI_ERROR_INSTRUMENTATION.md`**
   - Explanation of proactive error instrumentation where the agent injects Supabase logging code into patches to prevent future blind spots.

9. **`telemetry_tool_poc/IOS_HIGHLIGHT_SCENARIO.md`**
   - Real-world end-to-end debugging scenario: resolving an un-opening iOS highlight color palette using the closed-loop telemetry protocol.

10. **`telemetry_tool_poc/PAPER_DRAFT.md`**
    - Research draft; it still needs implementation evidence, experiments, and references before submission.

11. **`telemetry_tool_poc/lint_schema.py`**
    - Static checker that verifies the Supabase migration's foreign-key column ordering before it is applied.

12. **`telemetry_tool_poc/web_demo/`**
    - Management server: Google OAuth, app-owned account, separate ingest/developer keys, AI session management, and the full case lifecycle (`/api/client/cases/*`, `/api/tool/cases/*`).

13. **`ai_client_demo/`**
    - Separate AI-client example that writes a simulated client error and reads back logs scoped to its assigned session.

14. **`ai_client_demo/debug_loop_demo.py`**
    - Scripted proof-of-concept that drives the 7-step closed debugging loop against the live management API.

---

## Current Status
- Vite dashboard and custom OAuth backend build; Google OAuth/Supabase production configuration has not been exercised end-to-end.
- Python tool unit tests pass (12 tests); Node server unit tests pass (17 tests); live scoped RPC calls have not been tested against the project.
- The closed-loop debugging protocol (debug_cases, case_probes, runtime-selectable probes, cleanup) is implemented in code but not yet run end-to-end against a deployed project.
- No Gemma 4/ADK harness run, controlled evaluation, or paper results have been produced.
- Treat this as a prototype and research proposal, not a submission-ready paper or production system.
