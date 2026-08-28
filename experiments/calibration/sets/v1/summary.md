# Baseline experiment — summary

## Run conditions

- run_id: `calibration__gpt-5.6-terra__v1__1787931788`
- configuration: **calibration**
- deployment: **gpt-5.6-terra** (model_version: None)
- endpoint: https://bizstruct-manual.openai.azure.com
- guardrails: None
- domain_version: 0.9.0
- dataset: /home/ubuntu/projects/personal/bizstruct/bizstruct-ml/experiments/dataset.json (sha256 5326ce768930…, 74130 bytes)
- bizstruct-domain: `bbee62b`
- bizstruct-be: `3063fd5`
- bizstruct-ml: `fffe084` (dirty)
- bizstruct-fe: `afef7d8`
- concurrency: 5, project_timeout: 1200.0s, poll_interval: 5.0s
- worker_replicas: 1
- mode: calibration, started_at: 2026-08-28T15:43:08.989447+00:00, finished_at: 2026-08-28T15:50:40.255052+00:00

**meta_warnings** (fields that couldn't be determined, and why):
- azure_deployment_info: --azure-resource-group/--azure-account-name not given, skipping model_version/guardrails lookup
- temperature/generation_params: bizstruct_ml.llm.client.LLMClient does not set temperature or any other sampling parameter — the API default applies, unrecorded anywhere in the worker's own config.

Total runs recorded: **5**

## Outcomes

| status | count |
|---|---|
| completed | 5 |
| failed | 0 |
| timeout | 0 |

Average duration: **432s** (7.2 min)

## Tokens & retries (from metrics.csv / Langfuse)

- Block rows exported: 40
- Input tokens: 204,922
- Output tokens: 38,535
- Total generation retries: 0 (0/40 blocks needed at least one)
- Average retries per block: 0.00
- Average LLM call latency: 11052ms
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
