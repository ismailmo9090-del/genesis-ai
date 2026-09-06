# Genesis AI — Inference API Documentation

**Version:** v1  
**Base URL:** `http://localhost:5000/v1`

Genesis AI is a local-first AI assistant with experience-based learning, web research, and a multi-stage cognitive pipeline. This API exposes the REAL Genesis intelligence to external applications.

---

## Authentication

All endpoints (except `/health` and `/models`) require an API key:

```
Authorization: Bearer gen_YOUR_API_KEY_HERE
```

API keys are created through the `/v1/apikeys` endpoint (admin scope required).

### Permission Scopes

| Scope | Description |
|-------|-------------|
| `chat` | Use `/v1/chat` and `/v1/chat/stream` |
| `evaluate` | Use `/v1/evaluate` |
| `learning` | Use `/learning/*` endpoints |
| `admin` | Create API keys, full access |

---

## Rate Limiting

Default limits per API key:
- **30 requests per minute**
- **500 requests per hour**

Rate limits are configurable per key. When exceeded:

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded (30 requests per minute). Retry after 45s."
  },
  "status": "error"
}
```

---

## Endpoints

### `POST /v1/chat`

Send a message to Genesis and receive a response.

**Request:**
```json
{
  "message": "Hello Genesis",
  "conversation_id": "optional-conversation-id"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | The message to send |
| `conversation_id` | string | No | Conversation ID for multi-turn context |

**Response:**
```json
{
  "response": "Hello! How can I help you?",
  "conversation_id": "gen_abc123def456",
  "request_id": "req_91ac...",
  "status": "success",
  "intent": "CONVERSATION",
  "confidence": 0.95,
  "processing_time_ms": 1234,
  "sources_used": [],
  "pipeline_stages": {}
}
```

---

### `POST /v1/chat/stream`

Stream Genesis response using Server-Sent Events (SSE).

**Request:** Same as `/v1/chat`

**Response:** `text/event-stream`

**Events:**

| Event | Description |
|-------|-------------|
| `status` | Pipeline stage update |
| `chunk` | Response text chunk |
| `done` | Completion with metadata |
| `error` | Error occurred |

**Example SSE stream:**
```
event: status
data: {"stage": "perceiving"}

event: status
data: {"stage": "understanding"}

event: status
data: {"stage": "reasoning"}

event: status
data: {"stage": "generating_response"}

event: chunk
data: {"text": "Hello! I'm Genesis AI"}

event: chunk
data: {"text": " — your personal assistant."}

event: done
data: {"conversation_id": "gen_abc123", "request_id": "req_...", "intent": "CONVERSATION", "confidence": 0.95, "processing_time_ms": 1234}
```

---

### `POST /v1/evaluate`

Evaluate a Genesis response against expected criteria. Uses the SAME inference pipeline as `/v1/chat`.

**Request:**
```json
{
  "input": "Explain what an HTTP request is.",
  "test_type": "direct",
  "expected": {
    "contains_concepts": ["client", "server", "request", "response"],
    "must_contain": ["HTTP"],
    "must_not_contain": ["I don't know"],
    "min_length": 100,
    "max_length": 5000
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `input` | string | Yes | Question/task to test |
| `expected` | object | No | Evaluation criteria |
| `test_type` | string | No | `direct`, `paraphrase`, `novel`, `cross-domain`, `multi-step` |

**Expected Criteria:**

| Key | Type | Description |
|-----|------|-------------|
| `contains_concepts` | string[] | Response must contain these concepts |
| `must_contain` | string[] | Response must contain these exact phrases |
| `must_not_contain` | string[] | Response must NOT contain these |
| `min_length` | int | Minimum character length |
| `max_length` | int | Maximum character length |

**Response:**
```json
{
  "response": "An HTTP request is a message sent by a client to a server...",
  "evaluation": {
    "status": "PASS",
    "score": 0.91,
    "test_type": "direct",
    "criteria": {
      "required_concepts": {"pass": true, "found": 4, "total": 4, "ratio": 1.0},
      "must_contain": {"pass": true, "found": ["HTTP"], "missing": []},
      "min_length": {"pass": true, "actual": 245, "required": 100}
    }
  },
  "request_id": "req_...",
  "status": "success"
}
```

**Evaluation Status:**

| Status | Score Range | Description |
|--------|-------------|-------------|
| `PASS` | >= 0.7 | Response meets criteria |
| `PARTIAL` | 0.3 - 0.7 | Partially meets criteria |
| `FAIL` | < 0.3 | Does not meet criteria |

---

### `GET /v1/models`

List available Genesis models. No authentication required.

**Response:**
```json
{
  "data": [
    {
      "id": "genesis",
      "name": "Genesis AI",
      "type": "knowledge-first-ai",
      "version": "0.1.0-alpha",
      "description": "Local-first AI assistant with experience-based learning..."
    }
  ],
  "request_id": "req_...",
  "status": "success"
}
```

---

### `GET /v1/health`

Health check. No authentication required.

**Response:**
```json
{
  "status": "healthy",
  "genesis_core": "ready",
  "database": "ready",
  "learning_engine": "ready",
  "memory": "ready",
  "timestamp": 1693000000.0
}
```

---

### `GET /v1/status`

System status. Requires `chat` scope.

**Response:**
```json
{
  "system": {
    "status": "online",
    "memory_count": 150,
    "knowledge_count": 42,
    "concept_count": 18,
    "skill_count": 5
  },
  "api_version": "v1",
  "request_id": "req_...",
  "status": "success"
}
```

---

### `POST /v1/apikeys`

Create a new API key. Requires `admin` scope.

**Request:**
```json
{
  "name": "My Application",
  "scopes": ["chat", "evaluate"],
  "requests_per_minute": 30,
  "requests_per_hour": 500
}
```

**Response:**
```json
{
  "key": "gen_ABC123...",
  "key_prefix": "gen_ABC123",
  "name": "My Application",
  "scopes": ["chat", "evaluate"],
  "requests_per_minute": 30,
  "requests_per_hour": 500,
  "request_id": "req_...",
  "status": "success"
}
```

> **IMPORTANT:** The raw API key is shown only once. Store it securely.

---

## Conversation Handling

Conversations maintain context across multiple messages.

**Flow:**
1. Send first message without `conversation_id` → Genesis creates a new conversation
2. Use returned `conversation_id` in subsequent messages → Genesis maintains context
3. Each conversation has its own context window

**Example:**
```python
# Turn 1
r1 = client.chat("Who is Elon Musk?")
conv_id = r1["conversation_id"]

# Turn 2 — Genesis remembers context
r2 = client.chat("What companies does he run?", conversation_id=conv_id)
```

---

## Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `INVALID_REQUEST` | 400 | Malformed or missing required fields |
| `UNAUTHORIZED` | 401 | Missing or invalid API key |
| `FORBIDDEN` | 403 | API key lacks required scope |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |

---

## Architecture

The Inference API uses the SAME Genesis core as the UI:

```
External App → POST /v1/chat → Genesis Core → Response
Web UI       → POST /api/chat → Genesis Core → Response
```

**Pipeline:**
```
Request → Authentication → Validation → Genesis Core → Understanding → Context →
Memory → Knowledge → Reasoning → Decision → Research → Verification → Response
```

There is only ONE Genesis intelligence pipeline. The API is a thin interface to the same brain.

---

## Learning Integration

The external Learning Agent can use both APIs:

```
1. Teach Genesis    → POST /learning/experience
2. Wait for commit  → Learning Pipeline processes
3. Test Genesis     → POST /v1/chat (NEW question)
4. Evaluate         → POST /v1/evaluate
5. If FAIL          → Corrective experience → Retest
```

This validates that Genesis actually LEARNED, not just stored data.

---

## Client Examples

See `examples/` directory:
- `python_client.py` — Python client with all endpoints
- `curl_examples.md` — cURL command examples
