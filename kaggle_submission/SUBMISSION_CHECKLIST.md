# Kaggle Submission Checklist

Paper Track: *Google - The Gemma 4 Developer Agent Paper Track* (https://www.kaggle.com/competitions/gemma-4-developer-agent-paper).
Deadline **12 Nov 2026, 23:59 UTC**. Awards: Overall Best Paper ($15k), Best New Resource ($10k), Best New Application ($10k).

## Form fields, in order

| Field | What to paste | Source in this repo |
| --- | --- | --- |
| Tracks / award category | Overall Best Paper; add Best New Resource if the form allows more than one (the paired harness and the tool are the reusable resource) | – |
| Project Title | `Remote Client Telemetry for Repository-Level Coding Agents: A Closed-Loop Debugging Protocol` | `PAPER_DRAFT.md:1` |
| Project Subtitle | `Consent-scoped device telemetry, withdrawable instrumentation, and server-enforced separation of evidence from repair validation for small local coding agents` | `PAPER_DRAFT.md:3` (drop the `*`) |
| Project Description | The whole body: abstract, introduction, related work, method, implementation, experiments, limitations, conclusion, references, reproducibility | `kaggle_submission/writeup_body.md` |
| Media Gallery | Four PNGs below; one of them is the cover image | `kaggle_submission/figures/` |
| Cover image | `figure_closed_loop.png` (the protocol diagram); `figure_ab_results.png` is the alternative if the cover should show results | `kaggle_submission/figures/` |
| Project Links | Public repository URL (no login, no paywall). Optional second link: the paper PDF as a public asset. Do not link an arXiv preprint before checking the "unpublished" rule | repo root |
| Video Links | Leave empty; the paper track does not score a demo video | – |
| Team name / members | Team label plus every member's Kaggle username; each member must have joined the competition and accepted the rules | – |
| Final step | Save **and** press Submit. A saved draft is not judged | – |

## Media gallery contents

| File | Caption to reuse (from `build_paper_pdf.py`) |
| --- | --- |
| `figure_trust_boundaries.png` | Figure 1. Trust boundaries: the agent reaches only the tool surface, while ownership checks, redaction, and the database stay server-side. |
| `figure_closed_loop.png` | Figure 2. The closed debugging loop: evidence collection is separated from repair validation, and instrumentation is withdrawn at cleanup. |
| `figure_state_machine.png` | Figure 3. The server-enforced case state machine. Transitions are validated twice, in the Express layer and in the RPCs, and only the user can approve a fix. |
| `figure_ab_results.png` | Figure 4. Paired evaluation on the compact and the larger repository variant. The left and middle panels show repair and root-cause accuracy with and without diagnostic events; the right panel shows the per-trial context cost of condition B against condition A. |

In the body, upload each PNG through the Kaggle editor's attachment button and replace the `figures/<name>.png` links with the attachment URLs, or drop the `![Figure](...)` lines and rely on the gallery captions.

## Word budget

- Body without the reference list: 2,605 words. Reference list: 257. Total: 2,958 (limit 3,000).
- Live numbers: `kaggle_submission/word_count.txt` (regenerated with `python telemetry_tool_poc/build_kaggle_submission.py`).

## Before submitting

- [ ] `python telemetry_tool_poc/check_paper_numbers.py` prints "Paper numbers match the stored runs".
- [ ] `python telemetry_tool_poc/paper_word_count.py` stays under 3,000.
- [ ] `python -m unittest discover -s telemetry_tool_poc`, `python -m unittest test_ollama_agent`, `python -m unittest eval.test_eval_harness eval.test_adversarial`, `python -m unittest discover -s ai_client_demo`, and `npm test` in `web_demo/` all pass (106 tests).
- [ ] The public repository link opens in a private window without a login.
- [ ] The submitted body matches `kaggle_submission/writeup_body.md` (regenerated from `PAPER_DRAFT.md`).

## How the paper addresses the judging criteria

| Criterion | Where it is answered |
| --- | --- |
| Novelty | Section 2 gap paragraph and the sentence after it: agent-selected, withdrawable probes with a server-enforced approval gate; Section 1 contribution list |
| Quality | Sections 3-4 (protocol, client, server, tool surface) and Section 5.1 (seven deterministic suites, 106 tests) |
| Relevance | Section 1 (the gap between local agents and a user's remote device), Section 7 (protocol contribution over the telemetry channel) |
| Verifiability | Section 5.3 (paired design, per-pair seeds, frozen rubric), Section 5.2 (invalid run kept for audit), Reproducibility section, `eval/` harness and stored runs |
| Clarity | Section structure, Table 1 (tool bounds), Figures 1-4, one claim per paragraph, explicit limitations in Section 6 |

## Reporting discipline

- The pilot reports a negative result (telemetry did not improve repair); do not soften it in the Kaggle blurb.
- Do not describe the artifact as production-ready or security-audited; Section 6 states the opposite.
- Keep the invalid exploratory run in `eval/results/eval_summary.json` mentioned; removing it would weaken the verifiability claim.
- The three-repeat pilot is not reported; the paper reports the five-repeat run (30 pairs per variant). The earlier run stays in the git history.
