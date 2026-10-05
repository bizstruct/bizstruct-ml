# BizStruct ML Service

Stateless Azure Service Bus worker that generates the artifacts of a business model, one stage row per message, on the `bizstruct-domain` wire contract (ADR-0011). Architecture: [docs/adr/0001-ml-core-architecture.md](docs/adr/0001-ml-core-architecture.md).

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

| Variable | Description | Example |
|----------|-------------|---------|
| `SERVICE_BUS_CONNECTION_STRING` | Azure Service Bus namespace connection string | `Endpoint=sb://...` |
| `SERVICE_BUS_QUEUE_NAME` | Queue name | `generation-tasks` |
| `BACKEND_BASE_URL` | Backend API base URL | `https://api.bizstruct.app` |
| `BACKEND_API_KEY` | API key for backend requests | secret |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI resource endpoint | `https://xxx.openai.azure.com` |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | secret |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name | `gpt-4o` |
| `AZURE_OPENAI_API_VERSION` | API version | `2024-10-21` |
| `JUDGE_PROVIDER` | Judge implementation, a key of the registry in `judge/factory.py` (`azure_foundry_chat`, `fake`) | `azure_foundry_chat` |
| `JUDGE_ENDPOINT` | Base URL of the judge's OpenAI-compatible chat endpoint | `https://xxx.services.ai.azure.com/openai/v1` |
| `JUDGE_API_KEY` | Judge API key (separate from the generator's) | secret |
| `JUDGE_DEPLOYMENT` | Judge deployment name (Mistral Large 3 on Azure Foundry) | `mistral-large-3` |
| `JUDGE_TIMEOUT_SECONDS` | Timeout of one judge call | `60` |
| `JUDGE_JSON_MODE` | Send `response_format=json_object` to the judge. Leave `false` until `scripts/judge_smoke.py` shows the deployment accepts it | `false` |
| `JUDGE_MAX_TOKENS` | Optional `max_tokens` for judge calls; unset = provider default | `800` |
| `LOCK_RENEWAL_SECONDS` | How long a message lock is auto-renewed. Must cover the slowest row | `900` |
| `LLM_MAX_RETRIES` | LLM generation retry count | `2` |
| `LOG_LEVEL` | Log level | `INFO` |

The judge must be a different model family from the generator (`openai`). The worker **refuses to start** if the families are equal, or if the judge settings are missing or name an unknown provider. `WEBPUBSUB_*` are no longer used (be publishes status events); leftovers in `.env` are ignored.

Add the following to `.env.example` (kept out of this change because it was not editable here):

```
# ── Judge (consistency checks): a different model family from the generator ──
JUDGE_PROVIDER=azure_foundry_chat
JUDGE_ENDPOINT=https://your-resource.services.ai.azure.com/openai/v1
JUDGE_API_KEY=your-judge-api-key
JUDGE_DEPLOYMENT=mistral-large-3
JUDGE_TIMEOUT_SECONDS=60
# JUDGE_JSON_MODE=false
# JUDGE_MAX_TOKENS=800
LOCK_RENEWAL_SECONDS=900
```

## Local Development

```bash
# Install uv
pip install uv

# Create virtual env and install deps
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Set env vars
cp .env.example .env
# Edit .env with your values

# Run the service
python -m bizstruct_ml

# Run tests
pytest
```

## Message shape

The body is the domain's `QueueMessage` (snake_case JSON). The pipeline sends exactly one target:

```json
{
  "project_id": "project_001",
  "language": "en",
  "targets": [{"stage_row_id": "row_empathy_map_0", "stage": "empathy_map", "attempt_id": "attempt_001"}]
}
```

Stages that have no generator yet are dead-lettered with reason `NoGenerator`. Use Service Bus Explorer (Portal → Queue → **Send messages**, content type `application/json`) or `az servicebus message send --body '<json>'` to place one.

Live check of the judge deployment (makes real API calls, run by hand):

```bash
JUDGE_ENDPOINT=... JUDGE_API_KEY=... JUDGE_DEPLOYMENT=... uv run python scripts/judge_smoke.py
JUDGE_ENDPOINT=... JUDGE_API_KEY=... JUDGE_DEPLOYMENT=... uv run pytest -m live   # same call as a test
```

## Queue Configuration Requirements

The Service Bus queue **must** be configured with:

| Setting | Required Value | Reason |
|---------|---------------|--------|
| `lockDuration` | ≥ 2 minutes (`PT2M`) | Generation + retries can take >60s. `LOCK_RENEWAL_SECONDS` extends it while a row runs; what the broker does if the lock still expires is **not verified** (ADR-0001) |
| `maxDeliveryCount` | `5` | Allows redelivery before DLQ |
| Dead Letter Queue | Monitored (alert on non-zero length) | Catches invalid messages and deleted projects |

## KEDA Scale Rule (Azure Container Apps)

```yaml
scale:
  minReplicas: 0
  maxReplicas: 5
  rules:
    - name: servicebus-queue
      custom:
        type: azure-servicebus
        metadata:
          queueName: generation-tasks
          messageCount: "1"
        auth:
          - secretRef: servicebus-connection
            triggerParameter: connection
```

`messageCount: "1"` — each message spins up a separate replica. Ingress must be disabled (service receives no inbound HTTP).

## Architecture

```
Backend ──► Azure Service Bus (queue)
                  │  KEDA scale 0→N
                  ▼
          ML Worker (Azure Container Apps)
                  │
                  ├──► GET  {BACKEND}/api/internal/projects/{id}?row=<row_id>   (snapshot of the row's closure)
                  ├──► Azure OpenAI (generator, structured output)
                  ├──► Judge model on Azure Foundry (consistency checks)
                  └──► POST {BACKEND}/api/internal/hook                         (StageResult)
```

Packages under `src/bizstruct_ml/`: `core/` (stage runner, context, consistency; no knowledge of queues or HTTP), `judge/` (provider abstraction, protocol layer, family guard), `strategies/` (pipeline; the agent comes later), `adapters/` (Service Bus consumer, backend client), `llm/` (generator client, retry helper).

Processing flow per message (`strategies/pipeline.py`):
1. Parse `QueueMessage` → dead-letter if invalid; more than one target → dead-letter; stage without generator → dead-letter
2. `GET …?row=<id>` → dead-letter on 404/other 4xx, abandon on 5xx/timeout
3. `attempt_id` ≠ the row's → complete without work (stale); row `DONE` with the same `attempt_id` → complete (already applied)
4. Generate, convert, check consistency, regenerate on deterministic errors (≤ 2, inside the message)
5. `POST /api/internal/hook` with `StageResult` (retry 3×): 200 complete · 409 complete (stale) · 404/422 dead-letter · 5xx/timeout abandon

ml never writes row statuses; be applies the transitions and publishes `StageEvent`.
