# Comparison across runs

_(no --input-price-per-1k/--output-price-per-1k given — cost column omitted)_

| results_dir | configuration | deployment | model_version | completed | failed | timeout | avg_duration_s | input_tokens | output_tokens | total_retries | avg_retries_per_block | avg_latency_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_pipeline__gpt-5.6-sol | A_pipeline | gpt-5.6-sol | 2026-07-09 | 5 | 0 | 0 | 1046 | 272,709 | 68,576 | 0 | 0.00 | 27512 |
| A_pipeline__gpt-5.6-terra | A_pipeline | gpt-5.6-terra | 2026-07-09 | 5 | 0 | 0 | 633 | 267,855 | 58,835 | 0 | 0.00 | 16546 |
| A_pipeline__gpt-5.4-mini | A_pipeline | gpt-5.4-mini | 2026-03-17 | 5 | 0 | 0 | 369 | 254,632 | 52,271 | 2 | 0.05 | 8809 |
| A_pipeline__gpt-5.4-nano | A_pipeline | gpt-5.4-nano | 2026-03-17 | 5 | 0 | 0 | 567 | 274,757 | 57,684 | 2 | 0.05 | 13950 |
