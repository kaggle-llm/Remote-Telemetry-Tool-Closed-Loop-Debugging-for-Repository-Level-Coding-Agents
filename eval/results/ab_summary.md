# Paired telemetry evaluation

- model: `iandiii/gemma4:e4b-64k`
- seed: `20261028`
- repeats per task: `5`
- paired trials: `30`
- isolation: local fixture backend, synthetic case ids and rows only

| Outcome | Condition A (no diagnostic events) | Condition B (diagnostic events) |
| --- | --- | --- |
| Validation test passed | 12/30 | 10/30 |
| Root cause matched rubric | 14/30 | 18/30 |
| Named the responsible module | 24/30 | 25/30 |
| Telemetry fetches | 18 | 14 |
| File edits | 47 | 47 |

- discordant repair pairs: B only 4, A only 6, exact McNemar p = 0.754
- discordant diagnosis pairs: B only 7, A only 3, exact McNemar p = 0.344
- discordant localization pairs: B only 2, A only 1, exact McNemar p = 1.000
- token delta (B - A): -164.9 (95% bootstrap CI -6883.2 to 6568.8)

| Task | Pairs | A repaired | B repaired | A diagnosed | B diagnosed |
| --- | --- | --- | --- | --- | --- |
| t5_auth_cache_stale_entry | 5 | 1 | 1 | 0 | 2 |
| t1_palette_presentation_context | 5 | 3 | 5 | 2 | 4 |
| t4_retry_idempotency_key | 5 | 0 | 0 | 2 | 2 |
| t3_anchor_page_out_of_range | 5 | 3 | 0 | 3 | 2 |
| t2_imageloader_request_timeout | 5 | 4 | 3 | 5 | 5 |
| t6_media_player_decoder_error | 5 | 1 | 1 | 2 | 3 |
