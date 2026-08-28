# Baseline experiment — summary

## Run conditions

- run_id: `A_pipeline_dataquality__gpt-5.6-terra__pilot__1787845635`
- configuration: **A_pipeline_dataquality**
- deployment: **gpt-5.6-terra** (model_version: 2026-07-09)
- endpoint: https://bizstruct-manual.openai.azure.com
- guardrails: Microsoft.DefaultV2
- domain_version: 0.9.0
- dataset: /home/ubuntu/projects/personal/bizstruct/bizstruct-ml/experiments/dataset.json (sha256 5326ce768930…, 74130 bytes)
- bizstruct-domain: `32e22dd`
- bizstruct-be: `f207330` (dirty)
- bizstruct-ml: `6328aa3` (dirty)
- bizstruct-fe: `a4b3e73`
- concurrency: 5, project_timeout: 1200.0s, poll_interval: 5.0s
- worker_replicas: 1
- mode: pilot, started_at: 2026-08-27T15:47:17.440933+00:00, finished_at: 2026-08-27T15:53:24.005700+00:00

**meta_warnings** (fields that couldn't be determined, and why):
- temperature/generation_params: bizstruct_ml.llm.client.LLMClient does not set temperature or any other sampling parameter — the API default applies, unrecorded anywhere in the worker's own config.

Total runs recorded: **3**

## Outcomes

| status | count |
|---|---|
| completed | 3 |
| failed | 0 |
| timeout | 0 |

Average duration: **351s** (5.9 min)

## Tokens & retries (from metrics.csv / Langfuse)

- Block rows exported: 24
- Input tokens: 163,080
- Output tokens: 35,339
- Total generation retries: 0 (0/24 blocks needed at least one)
- Average retries per block: 0.00
- Average LLM call latency: 15084ms
- Estimated cost: n/a (no --input-price-per-1k/--output-price-per-1k given)

## Dataset label distribution (all recorded runs)

### expected_pattern

| value | count |
|---|---|
| unbundling | 3 |

### detail_level

| value | count |
|---|---|
| detailed | 1 |
| minimal | 1 |
| moderate | 1 |

### market_type

| value | count |
|---|---|
| b2b | 2 |
| b2c | 1 |

### industry

| value | count |
|---|---|
| освіта | 1 |
| охорона здоров'я | 1 |
| сільське господарство | 1 |
