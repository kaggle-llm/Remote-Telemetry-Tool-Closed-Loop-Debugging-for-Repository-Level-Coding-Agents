# Paired telemetry evaluation

- model: `iandiii/gemma4:e4b-64k`
- seed: `20261028`
- repeats per task: `5`
- paired trials: `30`
- isolation: local fixture backend, synthetic case ids and rows only

| Outcome | Condition A (no diagnostic events) | Condition B (diagnostic events) |
| --- | --- | --- |
| Validation test passed | 9/30 | 12/30 |
| Root cause matched rubric | 12/30 | 18/30 |
| Named the responsible module | 21/30 | 21/30 |
| Telemetry fetches | 15 | 14 |
| File edits | 40 | 32 |

- discordant repair pairs: B only 5, A only 2, exact McNemar p = 0.453
- discordant diagnosis pairs: B only 11, A only 5, exact McNemar p = 0.210
- discordant localization pairs: B only 3, A only 3, exact McNemar p = 1.000
- token delta (B - A): -11181.7 (95% bootstrap CI -19629.9 to -3390.8)

| Task | Pairs | A repaired | B repaired | A diagnosed | B diagnosed |
| --- | --- | --- | --- | --- | --- |
| t5_auth_cache_stale_entry | 5 | 0 | 0 | 1 | 0 |
| t1_palette_presentation_context | 5 | 1 | 1 | 3 | 5 |
| t4_retry_idempotency_key | 5 | 0 | 0 | 0 | 3 |
| t3_anchor_page_out_of_range | 5 | 0 | 5 | 0 | 5 |
| t2_imageloader_request_timeout | 5 | 5 | 4 | 5 | 4 |
| t6_media_player_decoder_error | 5 | 3 | 2 | 3 | 1 |
