# Baseline experiment — summary

## Run conditions

- run_id: `A_pipeline__gpt-5.4-mini__pilot__1787831611`
- configuration: **A_pipeline**
- deployment: **gpt-5.4-mini** (model_version: 2026-03-17)
- endpoint: https://bizstruct-manual.openai.azure.com
- guardrails: Microsoft.DefaultV2
- domain_version: 0.8.1
- dataset: /home/ubuntu/projects/personal/bizstruct/bizstruct-ml/experiments/dataset.json (sha256 5326ce768930…, 74130 bytes)
- bizstruct-domain: `a0928e9`
- bizstruct-be: `f207330`
- bizstruct-ml: `6328aa3` (dirty)
- bizstruct-fe: `a4b3e73`
- concurrency: 5, project_timeout: 1200.0s, poll_interval: 5.0s
- worker_replicas: 1
- mode: pilot, started_at: 2026-08-27T11:53:32.706944+00:00, finished_at: 2026-08-27T12:00:04.680183+00:00

**meta_warnings** (fields that couldn't be determined, and why):
- temperature/generation_params: bizstruct_ml.llm.client.LLMClient does not set temperature or any other sampling parameter — the API default applies, unrecorded anywhere in the worker's own config.

Total runs recorded: **5**

## Outcomes

| status | count |
|---|---|
| completed | 5 |
| failed | 0 |
| timeout | 0 |

Average duration: **369s** (6.1 min)

## Tokens & retries (from metrics.csv / Langfuse)

- Block rows exported: 40
- Input tokens: 254,632
- Output tokens: 52,271
- Total generation retries: 2 (2/40 blocks needed at least one)
- Average retries per block: 0.05
- Average LLM call latency: 8809ms
- Estimated cost: n/a (no --input-price-per-1k/--output-price-per-1k given)

## Dataset label distribution (all recorded runs)

### expected_pattern

| value | count |
|---|---|
| unbundling | 5 |

### detail_level

| value | count |
|---|---|
| detailed | 1 |
| minimal | 2 |
| moderate | 2 |

### market_type

| value | count |
|---|---|
| b2b | 4 |
| b2c | 1 |

### industry

| value | count |
|---|---|
| виробництво | 1 |
| освіта | 1 |
| охорона здоров'я | 1 |
| роздрібна торгівля | 1 |
| сільське господарство | 1 |
