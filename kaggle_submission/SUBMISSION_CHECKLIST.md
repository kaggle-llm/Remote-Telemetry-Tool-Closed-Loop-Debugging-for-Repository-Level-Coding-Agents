# Kaggle Submission Checklist

Paper Track: *Google - The Gemma 4 Developer Agent Paper Track* (deadline **12 Nov 2026**).

## Package contents

| File | Purpose |
| --- | --- |
| `writeup.md` | Submission body, generated from `telemetry_tool_poc/PAPER_DRAFT.md`; figure links point at `figures/` |
| `figures/figure_trust_boundaries.png` | Figure 1, trust boundaries |
| `figures/figure_closed_loop.png` | Figure 2, closed debugging loop |
| `figures/figure_state_machine.png` | Figure 3, server-enforced case state machine |
| `figures/figure_ab_results.png` | Figure 4, paired A/B evaluation results |
| `word_count.txt` | Live word count against the 3,000-word limit |

Regenerate the package after any draft or figure change:

```powershell
python telemetry_tool_poc/build_kaggle_submission.py
```

## Before submitting

- [ ] Read `word_count.txt`; the writeup must stay under 3,000 words (prose count is the one Kaggle sees, raw count is the conservative check).
- [ ] Upload the four PNGs as Kaggle attachments and replace `figures/<name>.png` links in the pasted writeup with the returned attachment URLs.
- [ ] Paste `writeup.md` into the Paper Track writeup editor, keeping the title `Remote Client Telemetry for Repository-Level Coding Agents: A Closed-Loop Debugging Protocol`.
- [ ] Attach `telemetry_tool_poc/Remote_Telemetry_Tool_Paper.pdf` (7 pages, four figures, two tables, PDF outline) as the downloadable PDF.
- [ ] Publish the code somewhere reachable (repository link in the Reproducibility section) and check that the link opens without login.
- [ ] Confirm the reported test counts still match the suites in `telemetry_tool_poc/README.md` and the root `README.md`.
- [ ] Re-read the abstract and Section 5.3 against `eval/results/ab_summary.json` and `eval/results_large/ab_summary.json`; every number must match the stored runs.

## How the paper addresses the judging criteria

| Criterion | Where it is answered |
| --- | --- |
| Novelty | Section 2 gap paragraph and the sentence after it: agent-selected, withdrawable probes with a server-enforced approval gate; Section 1 contribution list |
| Quality | Sections 3-4 (protocol, client, server, tool surface) and Section 5.1 (seven deterministic suites, 104 tests) |
| Relevance | Section 1 (the gap between local agents and a user's remote device), Section 7 (protocol contribution over the telemetry channel) |
| Verifiability | Section 5.3 (paired design, frozen rubric, per-pair seeds), Section 5.2 (invalid run kept for audit), Reproducibility section, `eval/` harness and stored runs |
| Clarity | Section structure, Table 1 (tool bounds), Figures 1-4, one claim per paragraph, explicit limitations in Section 6 |

## Reporting discipline

- The pilot reports a negative result (telemetry did not improve repair); do not soften it in the Kaggle blurb.
- Do not describe the artifact as production-ready or security-audited; Section 6 states the opposite.
- Keep the invalid exploratory run in `eval/results/eval_summary.json` mentioned; removing it would weaken the verifiability claim.
