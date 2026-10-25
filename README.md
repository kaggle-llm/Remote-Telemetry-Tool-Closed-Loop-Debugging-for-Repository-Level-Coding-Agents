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
   - Python proof-of-concept script simulating the remote telemetry fetch tool (`fetch_client_logs`) for agent integration.

6. **`telemetry_tool_poc/agent.yaml`**
   - Illustrative agent/tool configuration; not verified against the competition harness.

7. **`telemetry_tool_poc/TOOL_CALLING_EXPLAINED.md`**
   - Technical breakdown of how Gemma 4 autonomously triggers tool calls based on context and task prompts.

8. **`telemetry_tool_poc/AI_ERROR_INSTRUMENTATION.md`**
   - Explanation of proactive error instrumentation where the agent injects Supabase logging code into patches to prevent future blind spots.

9. **`telemetry_tool_poc/IOS_HIGHLIGHT_SCENARIO.md`**
   - Real-world end-to-end debugging scenario: Resolving an un-opening iOS highlight color palette using remote telemetry.

10. **`telemetry_tool_poc/PAPER_DRAFT.md`**
   - Research draft; it still needs implementation evidence, experiments, and references before submission.

11. **`telemetry_tool_poc/web_demo/`**
    - Vite dashboard prototype with Google OAuth and API key/session management.

---

## Current Status
- Vite dashboard and custom OAuth backend build; Google OAuth/Supabase production configuration has not been exercised end-to-end.
- Python tool unit tests pass; live scoped RPC calls have not been tested against the project.
- No Gemma 4/ADK harness run, controlled evaluation, or paper results have been produced.
- Treat this as a prototype and research proposal, not a submission-ready paper or production system.
