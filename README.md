# BizStruct ML Service

Stateless Azure Service Bus worker that generates business model blocks using Azure OpenAI.

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
| `WEBPUBSUB_CONNECTION_STRING` | Azure Web PubSub connection string | `Endpoint=https://...` |
| `WEBPUBSUB_HUB` | Web PubSub hub name | `projects` |
| `LLM_MAX_RETRIES` | LLM generation retry count | `2` |
| `LOG_LEVEL` | Log level | `INFO` |

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

## Placing a Test Message in the Queue

### Using Azure Service Bus Explorer (GUI)

1. Open Azure Portal → Service Bus namespace → Queues → `generation-tasks`
2. Click **Service Bus Explorer** → **Send messages**
3. Set Content Type: `application/json`
4. Body:
   ```json
   {"project_id": "your-project-uuid", "block": "canvas"}
   ```

### Using Azure CLI

```bash
az servicebus message send \
  --connection-string "$SERVICE_BUS_CONNECTION_STRING" \
  --queue-name generation-tasks \
  --body '{"project_id": "your-project-uuid", "block": "canvas"}'
```

Valid block values: `models_options`, `canvas`, `empathy_map`, `hypotheses`, `pitch`, `scenario`, `what_if`, `architecture`

## Queue Configuration Requirements

The Service Bus queue **must** be configured with:

| Setting | Required Value | Reason |
|---------|---------------|--------|
| `lockDuration` | ≥ 2 minutes (`PT2M`) | Generation + retries can take >60s |
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
                  ├──► GET  {BACKEND}/api/projects/{id}      (context, API key)
                  ├──► Azure OpenAI (structured output)
                  ├──► POST {BACKEND}/api/internal/hook       (save result, API key)
                  └──► Azure Web PubSub                       (real-time event to frontend)
```

Processing flow per message:
1. Parse `QueueMessage` → dead-letter if invalid or unknown block
2. `GET /api/projects/{id}` → dead-letter on 404, abandon on 5xx/timeout
3. If block already non-null → complete (idempotent skip)
4. Generate block via Azure OpenAI with structured output + postprocessing
5. `POST /api/internal/hook` with result (retry 3×) → abandon if hook keeps failing
6. Publish PubSub notification (non-blocking)
7. Complete message
