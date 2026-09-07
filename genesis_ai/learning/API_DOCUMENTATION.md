# Learning API Documentation

Genesis AI Learning System ke liye Flask-based REST API.

**Base URL:** `/learning`

**Local-only:** Ye API sirf localhost par chalti hai. External access by default nahi hota.

---

## Table of Contents

1. [Experience Ingestion](#experience-ingestion)
2. [Knowledge & Skills](#knowledge--skills)
3. [Intent Patterns](#intent-patterns)
4. [Learning Status & Progress](#learning-status--progress)
5. [Learning Sessions](#learning-sessions)
6. [Curriculum](#curriculum)
7. [Firewall](#firewall)
8. [Knowledge Evolution](#knowledge-evolution)
9. [Teaching](#teaching)

---

## Experience Ingestion

### POST `/learning/experience`

Ek learning experience ingest karo. Ye primary API hai Genesis ko teach karne ke liye.

**Request Body:**
```json
{
    "task": "string (required)",
    "goal": "string",
    "context": {},
    "observations": [],
    "actions": [],
    "tools_used": [],
    "errors": [],
    "attempts": [],
    "result": {
        "claim": "optional - knowledge claim store karne ke liye",
        "concept": "optional - claim ka concept",
        "confidence": 0.8
    },
    "success": true,
    "evidence": [],
    "reflection": "string",
    "metadata": {}
}
```

**Response (201):**
```json
{
    "experience_id": "exp_xxx",
    "learning_result": {
        "success": true,
        "lessons_learned": [],
        "generalizations": [],
        "knowledge_created": 0,
        "skills_created": 0,
        "skills_updated": 0,
        "contradictions_found": 0,
        "confidence_delta": 0.0,
        "steps_completed": [],
        "error": null,
        "duration": 0.123
    }
}
```

---

### POST `/learning/observation`

Lightweight observation submit karo (full experience ki zaroorat nahi).

**Request Body:**
```json
{
    "observation": "string (required)",
    "context": { "task": "optional task name" },
    "metadata": {}
}
```

**Response (201):**
```json
{ "experience_id": "exp_xxx", "status": "observed" }
```

---

### POST `/learning/result`

Task ka outcome submit karo.

**Request Body:**
```json
{
    "task": "string",
    "goal": "string",
    "result": {},
    "success": true,
    "errors": [],
    "metadata": {}
}
```

**Response (201):**
```json
{
    "experience_id": "exp_xxx",
    "processed": true,
    "lessons": []
}
```

---

### POST `/learning/error`

Error report submit karo failure learning ke liye.

**Request Body:**
```json
{
    "error": "string (required)",
    "task": "string",
    "goal": "string",
    "actions": [],
    "tools_used": [],
    "reflection": "string",
    "metadata": {}
}
```

**Response (201):**
```json
{
    "experience_id": "exp_xxx",
    "failure_learned": true,
    "lessons": [],
    "generalizations": []
}
```

---

### POST `/learning/feedback`

Previous response par feedback submit karo.

**Request Body:**
```json
{
    "task": "string",
    "feedback": "string",
    "rating": 1-5,
    "comment": "string",
    "metadata": {}
}
```

**Response (201):**
```json
{ "experience_id": "exp_xxx", "status": "feedback_received" }
```

---

### POST `/learning/reflection`

Learning session par reflection submit karo.

**Request Body:**
```json
{
    "task": "string",
    "reflection": "string",
    "lessons": [],
    "generalizations": [],
    "metadata": {}
}
```

**Response (201):**
```json
{ "experience_id": "exp_xxx", "status": "reflection_recorded" }
```

---

## Knowledge & Skills

### POST `/learning/knowledge`

Knowledge claim submit karo verification ke liye.

**Request Body:**
```json
{
    "claim": "string (required)",
    "concept": "string",
    "source": "string",
    "evidence": [],
    "confidence": 0.5,
    "status": "UNCERTAIN" | "VERIFIED" | "OUTDATED"
}
```

**Response (201):**
```json
{ "status": "knowledge_submitted" }
```

---

### GET `/learning/knowledge`

Saari learned knowledge retrieve karo.

**Query Params:**
- `status` (optional) - Filter by status: `UNCERTAIN`, `VERIFIED`, `OUTDATED`

**Response:**
```json
{
    "knowledge": [
        {
            "id": 1,
            "concept": "string",
            "claim": "string",
            "confidence": 0.8,
            "status": "VERIFIED",
            "usage_count": 5,
            "created_at": 1234567890.0
        }
    ],
    "total": 1
}
```

---

### POST `/learning/skill`

Skill definition submit karo.

**Request Body:**
```json
{
    "name": "string (required)",
    "description": "string",
    "purpose": "string",
    "procedure": [],
    "confidence": 0.5
}
```

**Response (201):**
```json
{ "skill_id": "skill_xxxxxxxx", "status": "skill_created" }
```

---

### GET `/learning/skills`

Saare learned skills retrieve karo.

**Response:**
```json
{
    "skills": [
        {
            "skill_id": "string",
            "name": "string",
            "description": "string",
            "confidence": 0.8,
            "success_rate": 0.9,
            "experience_count": 10,
            "last_used": 1234567890.0
        }
    ],
    "total": 1
}
```

---

## Intent Patterns

### POST `/learning/intent-pattern`

Learned intent pattern submit karo (Learning → Inference Bridge ke liye).

**Request Body:**
```json
{
    "pattern_text": "salaam alaikum (required)",
    "intent": "greeting (required)",
    "concept": "greeting",
    "conditions": ["hinglish", "arabic_greeting"],
    "positive_examples": ["salaam", "assalamu alaikum"],
    "negative_examples": ["what is salaam"],
    "confidence": 0.8
}
```

**Response (201):**
```json
{ "status": "intent_pattern_submitted" }
```

---

### GET `/learning/intent-patterns`

Saare learned intent patterns retrieve karo.

**Response:**
```json
{
    "patterns": [
        {
            "id": 1,
            "pattern_text": "salaam",
            "intent": "greeting",
            "concept": "greeting",
            "confidence": 0.8,
            "status": "ACTIVE",
            "use_count": 5
        }
    ]
}
```

---

## Learning Status & Progress

### GET `/learning/status`

Current learning system status retrieve karo.

**Response:**
```json
{
    "status": "active",
    "learning_pipeline": { ... },
    "experience_memory": { ... },
    "timestamp": 1234567890.0
}
```

---

### GET `/learning/progress`

Learning progress over time retrieve karo.

**Response:**
```json
{
    "total_experiences": 100,
    "recent_success_rate": 0.85,
    "knowledge_items": 50,
    "skills": 10,
    "generalizations": 5,
    "verified_knowledge": 30,
    "recent_experiences": [
        {
            "task": "string",
            "success": true,
            "duration": 1.23,
            "timestamp": 1234567890.0
        }
    ]
}
```

---

### GET `/learning/gaps`

Identified knowledge gaps retrieve karo.

**Response:**
```json
{
    "uncertain_knowledge": [
        { "concept": "string", "claim": "string", "confidence": 0.3 }
    ],
    "outdated_knowledge": [
        { "concept": "string", "claim": "string", "confidence": 0.2 }
    ]
}
```

---

### GET `/learning/experiences`

Recent experiences retrieve karo.

**Query Params:**
- `limit` (default: 20) - Kitni experiences chahiye

**Response:**
```json
{
    "experiences": [
        {
            "experience_id": "string",
            "task": "string",
            "success": true,
            "confidence": 0.8,
            "duration": 1.23,
            "lessons": [],
            "timestamp": 1234567890.0
        }
    ],
    "total": 1
}
```

---

### GET `/learning/generalizations`

Saare learned generalizations retrieve karo.

**Response:**
```json
{
    "generalizations": [
        {
            "id": 1,
            "pattern": "string",
            "description": "string",
            "confidence": 0.8,
            "scope": "string",
            "usage_count": 5,
            "success_rate": 0.9,
            "created_at": 1234567890.0
        }
    ],
    "total": 1
}
```

---

### POST `/learning/evaluate`

Check karo ki koi generalization naye task par apply hota hai ya nahi.

**Request Body:**
```json
{ "task": "string (required)" }
```

**Response:**
```json
{
    "task": "string",
    "similar_experiences": 3,
    "applicable_generalizations": [
        {
            "pattern": "string",
            "description": "string",
            "confidence": 0.8,
            "overlap": ["word1", "word2"]
        }
    ]
}
```

---

### POST `/learning/generalize`

Recent successful experiences par generalization trigger karo.

**Response:**
```json
{
    "recent_successful": 10,
    "potential_generalizations": [
        { "source": "exp_xxx", "lesson": "string" }
    ]
}
```

---

## Learning Sessions

### POST `/learning/session/start`

Naya learning session start karo.

**Request Body:**
```json
{
    "user_id": 1,
    "topic": "general",
    "session_type": "guided",
    "goals": []
}
```

**Response (201):**
```json
{ "session_id": "learn_1234567890_xxx", "status": "started" }
```

---

### POST `/learning/session/stop`

Current learning session stop karo.

**Request Body:**
```json
{ "session_id": "string" }
```

**Response:**
```json
{ "status": "stopped" }
```

---

### POST `/learning/session/pause`

Current learning session pause karo.

**Request Body:**
```json
{ "session_id": "string" }
```

**Response:**
```json
{ "status": "paused" }
```

---

### POST `/learning/session/resume`

Paused learning session resume karo.

**Request Body:**
```json
{ "session_id": "string" }
```

**Response:**
```json
{ "status": "resumed" }
```

---

## Curriculum

### GET `/learning/curriculum/profile`

Domain ka skill profile retrieve karo.

**Query Params:**
- `domain` (default: "general")

**Response:**
```json
{
    "domain": "general",
    "level": "BEGINNER",
    "success_score": 0.7,
    "total_tasks": 20,
    "successful_tasks": 14,
    "failed_tasks": 6,
    "streak": 3,
    "best_streak": 5
}
```

---

### GET `/learning/curriculum/recommend`

Domain ke liye recommended next tasks retrieve karo.

**Query Params:**
- `domain` (default: "general")

**Response:**
```json
{
    "domain": "general",
    "current_level": "BEGINNER",
    "recommended_tasks": [],
    "reason": "string",
    "difficulty": "easy",
    "estimated_time_minutes": 15
}
```

---

### GET `/learning/curriculum/profiles`

Saare skill profiles retrieve karo.

**Response:**
```json
{
    "profiles": [
        {
            "domain": "general",
            "level": "BEGINNER",
            "score": 0.7,
            "total": 20,
            "success_rate": 70.0,
            "streak": 3
        }
    ]
}
```

---

### GET `/learning/curriculum/stats`

Domain ke liye detailed stats retrieve karo.

**Query Params:**
- `domain` (default: "general")

**Response:**
```json
{
    "domain_stats": { ... }
}
```

---

### POST `/learning/curriculum/reset`

Domain ka progress reset karo (dangerous - confirmation chahiye).

**Request Body:**
```json
{ "domain": "string (required)" }
```

**Response:**
```json
{ "status": "reset", "domain": "string" }
```

> **Note:** Ye operation firewall check se guzarta hai. Agar approval chahiye to 403 return hoga.

---

## Firewall

### GET `/learning/firewall/log`

Recent firewall log entries retrieve karo.

**Query Params:**
- `limit` (default: 50)

**Response:**
```json
{ "log": [ ... ] }
```

---

### GET `/learning/firewall/approvals`

Pending approvals retrieve karo.

**Response:**
```json
{ "approvals": [ ... ] }
```

---

### POST `/learning/firewall/approve`

Pending action approve karo.

**Request Body:**
```json
{ "action": "string (required)" }
```

**Response:**
```json
{ "status": "approved", "action": "string" }
```

---

### POST `/learning/firewall/deny`

Pending action deny karo.

**Request Body:**
```json
{ "action": "string (required)" }
```

**Response:**
```json
{ "status": "denied", "action": "string" }
```

---

### GET `/learning/firewall/stats`

Firewall statistics retrieve karo.

**Response:**
```json
{ "stats": { ... } }
```

---

## Knowledge Evolution

### GET `/learning/evolution/contradictions`

Detected contradictions retrieve karo.

**Query Params:**
- `resolved` (default: "false") - "true" karo resolved contradictions dekhne ke liye

**Response:**
```json
{
    "contradictions": [
        {
            "knowledge_a_id": 1,
            "knowledge_b_id": 2,
            "claim_a": "string",
            "claim_b": "string",
            "type": "string",
            "severity": "high",
            "resolved": false,
            "resolution": null
        }
    ]
}
```

---

### GET `/learning/evolution/versions/<knowledge_id>`

Knowledge item ka version history retrieve karo.

**Response:**
```json
{
    "versions": [
        {
            "version": 1,
            "claim": "string",
            "confidence": 0.8,
            "status": "VERIFIED",
            "source": "string",
            "created_at": 1234567890.0,
            "superseded_by": null
        }
    ]
}
```

---

### GET `/learning/evolution/freshness/<knowledge_id>`

Knowledge item ki freshness info retrieve karo.

**Response:**
```json
{
    "freshness": "string",
    "last_verified": 1234567890.0,
    "decay_rate": 0.01
}
```

---

### POST `/learning/evolution/verify/<knowledge_id>`

Knowledge item ko manually verify karo.

**Response:**
```json
{ "status": "verified", "knowledge_id": 1 }
```

---

### POST `/learning/evolution/decay`

Stale knowledge ka decay trigger karo.

**Request Body:**
```json
{ "max_age_days": 30 }
```

**Response:**
```json
{ "status": "decay_applied", "max_age_days": 30 }
```

---

### GET `/learning/evolution/stats`

Knowledge evolution statistics retrieve karo.

**Response:**
```json
{ "stats": { ... } }
```

---

## Retrieval & Inference

### GET `/learning/retrieval/stats`

Learning → Inference Bridge retrieval statistics retrieve karo.

**Response:**
```json
{ "stats": { ... } }
```

---

### GET `/learning/inference/outcomes`

Recent inference outcomes retrieve karo (feedback loop ke liye).

**Query Params:**
- `limit` (default: 20)

**Response:**
```json
{
    "outcomes": [
        {
            "session_id": "string",
            "message": "string",
            "classified_intent": "string",
            "final_intent": "string",
            "outcome": "string",
            "created_at": 1234567890.0
        }
    ]
}
```

---

## Teaching

### POST `/learning/teach/greeting`

Genesis ko batch mein greetings sikhaao.

**Request Body:**
```json
{
    "greetings": [
        {
            "text": "salaam (required)",
            "language": "hinglish",
            "response_hint": "Waleikum assalam!"
        }
    ]
}
```

**Response (201):**
```json
{
    "status": "greetings_taught",
    "count": 2,
    "details": [
        { "text": "salaam", "intent": "greeting", "status": "taught" }
    ]
}
```

> **Note:** Ye convenience endpoint hai. Ye automatically knowledge item, intent pattern, aur generalization create karta hai.

---

## Error Responses

Sab errors is format mein aate hain:

```json
{ "error": "Error message" }
```

Common HTTP Status Codes:
- `400` - Bad Request (missing required fields)
- `403` - Forbidden (firewall blocked)
- `503` - Service Unavailable (pipeline not initialized)

---

## Initialization

API ko initialize karne ke liye:

```python
from genesis_ai.learning.api import init_learning_api

init_learning_api(
    app=flask_app,
    db=database,
    learning_pipeline=pipeline,
    experience_memory=memory,
    session_manager=session_mgr
)
```

---

## Architecture

```
Learning API
├── Experience Ingestion (experience, observation, result, error, feedback)
├── Knowledge Management (knowledge, skill)
├── Intent Patterns (intent-pattern)
├── Status & Progress (status, progress, gaps, experiences, generalizations)
├── Sessions (session/start, stop, pause, resume)
├── Curriculum (profile, recommend, profiles, stats, reset)
├── Firewall (log, approvals, approve, deny, stats)
├── Evolution (contradictions, versions, freshness, verify, decay, stats)
└── Teaching (teach/greeting)
```

---

*Last Updated: September 2026*
