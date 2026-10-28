# Paired telemetry evaluation

- model: `iandiii/gemma4:e4b-64k`
- seed: `20261028`
- repeats per task: `3`
- paired trials: `18`
- isolation: local fixture backend, synthetic case ids and rows only

| Outcome | Condition A (no diagnostic events) | Condition B (diagnostic events) |
| --- | --- | --- |
| Validation test passed | 10/18 | 10/18 |
| Root cause matched rubric | 5/18 | 6/18 |
| Named the responsible module | 14/18 | 13/18 |
| Telemetry fetches | 10 | 7 |
| File edits | 20 | 21 |

- discordant repair pairs: B only 2, A only 2, exact McNemar p = 1.000
- discordant diagnosis pairs: B only 3, A only 2, exact McNemar p = 1.000
- discordant localization pairs: B only 0, A only 1, exact McNemar p = 1.000
- token delta (B - A): 896.8 (95% bootstrap CI -2443.1 to 4475.4)

| Task | Pairs | A repaired | B repaired | A diagnosed | B diagnosed |
| --- | --- | --- | --- | --- | --- |
| t6_media_player_decoder_error | 3 | 1 | 1 | 0 | 0 |
| t5_auth_cache_stale_entry | 3 | 0 | 2 | 1 | 2 |
| t2_imageloader_request_timeout | 3 | 3 | 2 | 0 | 1 |
| t3_anchor_page_out_of_range | 3 | 3 | 2 | 3 | 1 |
| t4_retry_idempotency_key | 3 | 0 | 0 | 0 | 0 |
| t1_palette_presentation_context | 3 | 3 | 3 | 1 | 2 |
