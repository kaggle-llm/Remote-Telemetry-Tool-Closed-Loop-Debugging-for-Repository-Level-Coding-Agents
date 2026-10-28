# Paired telemetry evaluation

- model: `iandiii/gemma4:e4b-64k`
- seed: `20261028`
- repeats per task: `3`
- paired trials: `18`
- isolation: local fixture backend, synthetic case ids and rows only

| Outcome | Condition A (no diagnostic events) | Condition B (diagnostic events) |
| --- | --- | --- |
| Validation test passed | 6/18 | 5/18 |
| Root cause matched rubric | 13/18 | 10/18 |
| Named the responsible module | 14/18 | 11/18 |
| Telemetry fetches | 5 | 9 |
| File edits | 29 | 22 |

- discordant repair pairs: B only 3, A only 4, exact McNemar p = 1.000
- discordant diagnosis pairs: B only 2, A only 5, exact McNemar p = 0.453
- discordant localization pairs: B only 1, A only 4, exact McNemar p = 0.375
- token delta (B - A): -4171.1 (95% bootstrap CI -14009.3 to 4965.3)

| Task | Pairs | A repaired | B repaired | A diagnosed | B diagnosed |
| --- | --- | --- | --- | --- | --- |
| t6_media_player_decoder_error | 3 | 1 | 1 | 3 | 2 |
| t5_auth_cache_stale_entry | 3 | 1 | 0 | 2 | 1 |
| t2_imageloader_request_timeout | 3 | 3 | 2 | 3 | 3 |
| t3_anchor_page_out_of_range | 3 | 0 | 2 | 2 | 2 |
| t4_retry_idempotency_key | 3 | 1 | 0 | 1 | 0 |
| t1_palette_presentation_context | 3 | 0 | 0 | 2 | 2 |
