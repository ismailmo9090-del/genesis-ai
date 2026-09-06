# Genesis AI — cURL Examples

## Setup

Set your API key:
```bash
export GENESIS_API_KEY="gen_YOUR_KEY_HERE"
```

## Health Check

```bash
curl http://localhost:5000/v1/health
```

## List Models

```bash
curl http://localhost:5000/v1/models
```

## Chat

```bash
curl -X POST http://localhost:5000/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GENESIS_API_KEY" \
  -d '{"message": "Hello Genesis!"}'
```

## Chat with Conversation ID

```bash
# First message (creates conversation)
curl -X POST http://localhost:5000/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GENESIS_API_KEY" \
  -d '{"message": "Who is Salman Khan?"}'

# Follow-up (use conversation_id from above)
curl -X POST http://localhost:5000/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GENESIS_API_KEY" \
  -d '{"message": "What are his top films?", "conversation_id": "gen_abc123"}'
```

## Streaming Chat

```bash
curl -X POST http://localhost:5000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GENESIS_API_KEY" \
  -d '{"message": "Explain quantum computing"}' \
  --no-buffer
```

## Evaluate Response

```bash
curl -X POST http://localhost:5000/v1/evaluate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GENESIS_API_KEY" \
  -d '{
    "input": "Explain what an HTTP request is.",
    "expected": {
      "contains_concepts": ["client", "server", "request", "response"],
      "min_length": 50
    }
  }'
```

## Get System Status

```bash
curl http://localhost:5000/v1/status \
  -H "Authorization: Bearer $GENESIS_API_KEY"
```

## Create API Key (Admin)

```bash
curl -X POST http://localhost:5000/v1/apikeys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -d '{
    "name": "My App",
    "scopes": ["chat", "evaluate"],
    "requests_per_minute": 30,
    "requests_per_hour": 500
  }'
```

## Error Response Format

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Message is required"
  },
  "request_id": "req_abc123",
  "status": "error"
}
```

## Rate Limit Response

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded (30 requests per minute). Retry after 45s."
  },
  "request_id": "req_def456",
  "status": "error"
}
```
