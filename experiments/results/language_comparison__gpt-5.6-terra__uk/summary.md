# Baseline experiment — summary

## Run conditions

- run_id: `language_comparison__gpt-5.6-terra__language_comparison__1787907291`
- configuration: **language_comparison**
- deployment: **gpt-5.6-terra** (model_version: None)
- endpoint: https://bizstruct-manual.openai.azure.com
- guardrails: None
- domain_version: 0.9.0
- dataset: /home/ubuntu/projects/personal/bizstruct/bizstruct-ml/experiments/dataset.json (sha256 5326ce768930…, 74130 bytes)
- bizstruct-domain: `bbee62b`
- bizstruct-be: `3063fd5`
- bizstruct-ml: `3cc970e`
- bizstruct-fe: `a4b3e73`
- concurrency: 4, project_timeout: 1200.0s, poll_interval: 5.0s
- worker_replicas: 1
- mode: language_comparison, started_at: 2026-08-28T08:54:52.033194+00:00, finished_at: 2026-08-28T09:16:00.779227+00:00

**meta_warnings** (fields that couldn't be determined, and why):
- azure_deployment_info: --azure-resource-group/--azure-account-name not given, skipping model_version/guardrails lookup
- temperature/generation_params: bizstruct_ml.llm.client.LLMClient does not set temperature or any other sampling parameter — the API default applies, unrecorded anywhere in the worker's own config.

Total runs recorded: **10**

## Outcomes

| status | count |
|---|---|
| completed | 9 |
| failed | 1 |
| timeout | 0 |

Average duration: **447s** (7.4 min)

## Tokens & retries (from metrics.csv / Langfuse)

- Block rows exported: 79
- Input tokens: 511,647
- Output tokens: 106,736
- Total generation retries: 3 (2/79 blocks needed at least one)
- Average retries per block: 0.04
- Average LLM call latency: 15239ms
- Estimated cost: n/a (no --input-price-per-1k/--output-price-per-1k given)

## Dataset label distribution (all recorded runs)

### expected_pattern

| value | count |
|---|---|
| free | 2 |
| long_tail | 2 |
| multi_sided_platform | 2 |
| open_business_model | 2 |
| unbundling | 2 |

### detail_level

| value | count |
|---|---|
| detailed | 4 |
| minimal | 4 |
| moderate | 2 |

### market_type

| value | count |
|---|---|
| b2b | 4 |
| b2b2c | 3 |
| b2c | 2 |
| b2g | 1 |

### industry

| value | count |
|---|---|
| автомобільні послуги | 1 |
| виробництво | 1 |
| екологія | 1 |
| культура | 1 |
| охорона здоров'я | 1 |
| спорт | 1 |
| сільське господарство | 1 |
| туризм | 1 |
| фінанси | 1 |
| юридичні послуги | 1 |
