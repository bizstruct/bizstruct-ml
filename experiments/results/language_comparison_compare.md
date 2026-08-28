# Comparison across runs

_(no --input-price-per-1k/--output-price-per-1k given — cost column omitted)_

| results_dir | configuration | deployment | model_version | completed | failed | timeout | avg_duration_s | input_tokens | output_tokens | total_retries | avg_retries_per_block | avg_latency_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| language_comparison__gpt-5.6-terra__uk | language_comparison | gpt-5.6-terra | None | 9 | 1 | 0 | 447 | 511,647 | 106,736 | 3 | 0.04 | 15239 |
| language_comparison__gpt-5.6-terra__en | language_comparison | gpt-5.6-terra | None | 10 | 0 | 0 | 363 | 410,348 | 76,580 | 1 | 0.01 | 12233 |
