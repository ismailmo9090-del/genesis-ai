# Genesis Learning System — Current State

## Test Results: 213/213 passing

| Test Suite | Count | Status |
|------------|-------|--------|
| test_all.py (original) | 115 | PASS |
| test_generalization.py (regression/anti-hardcoding) | 41 | PASS |
| test_learning.py (experience/pipeline/API) | 27 | PASS |
| test_curriculum_firewall.py (adaptive/safety) | 30 | PASS |
| **Total** | **213** | **ALL PASS** |

## What's Built

### Phase 1: Cognitive Architecture
- `core/cognitive/state.py` — CognitiveState dataclass + enums
- `core/cognitive/decision.py` — DecisionOrchestrator (dynamic scoring)
- `core/cognitive/engine.py` — CognitiveEngine (7-stage pipeline: PERCEIVE → UNDERSTAND → ASSESS → DECIDE → ACT → VERIFY → LEARN)
- `main.py` chat() rewritten: ~350 lines of if/elif → ~60 lines using CognitiveEngine

### Phase 2: Learning System
- `learning/experience_memory.py` — Experience dataclass + ExperienceMemory (ingest, find_similar, stats)
- `learning/pipeline.py` — LearningPipeline (14-stage processing, 4 DB tables)
- `learning/curriculum.py` — CurriculumEngine (adaptive difficulty, level progression, recommendations)
- `learning/firewall.py` — LearningFirewall (risk levels, approval flow, logging)
- `learning/api.py` — Flask Blueprint with 30+ endpoints

### Integration
- CognitiveEngine's `learn()` method feeds chat interactions into LearningPipeline
- Learning API registered in Flask app with curriculum + firewall endpoints
- All systems tested end-to-end

## New API Endpoints (30+)

### Experience Ingestion
- `POST /learning/experience` — Ingest structured experience
- `POST /learning/observation` — Submit observation
- `POST /learning/result` — Submit task result
- `POST /learning/error` — Submit error report
- `POST /learning/feedback` — Submit feedback

### Knowledge & Skills
- `GET /learning/knowledge` — List learned knowledge
- `GET /learning/skills` — List learned skills
- `GET /learning/generalizations` — List generalizations
- `POST /learning/evaluate` — Check applicable generalizations

### Curriculum
- `GET /learning/curriculum/profile?domain=X` — Get skill profile
- `GET /learning/curriculum/recommend?domain=X` — Get next tasks
- `GET /learning/curriculum/profiles` — All profiles
- `GET /learning/curriculum/stats?domain=X` — Detailed stats
- `POST /learning/curriculum/reset` — Reset domain progress

### Firewall
- `GET /learning/firewall/log` — Firewall check log
- `GET /learning/firewall/approvals` — Pending approvals
- `POST /learning/firewall/approve` — Approve action
- `POST /learning/firewall/deny` — Deny action
- `GET /learning/firewall/stats` — Firewall statistics

### Sessions
- `POST /learning/session/start` — Start learning session
- `POST /learning/session/stop` — Stop session
- `POST /learning/session/pause` — Pause session
- `POST /learning/session/resume` — Resume session

### Status
- `GET /learning/status` — System status
- `GET /learning/progress` — Learning progress
- `GET /learning/experiences` — Recent experiences

## What's Next

1. **Knowledge Evolution** — versioning, contradiction detection, freshness tracking
2. **Checkpoint/Rollback** — save/restore learning state
3. **GENESIS_LEARNING_PROTOCOL.md** — external coding agent protocol
4. **GENESIS_LEARNING_AGENT_PROMPT.md** — agent prompt for submitting experiences
5. **End-to-end learning experiment** — test real learning loops

## Architecture Summary

```
User Input → CognitiveEngine Pipeline
  ├── PERCEIVE → UNDERSTAND → ASSESS_KNOWLEDGE
  ├── DECIDE → ACT → VERIFY → RESPOND
  └── LEARN → LearningPipeline
        ├── OBSERVE → UNDERSTAND → REPRESENT
        ├── EXTRACT → GENERALIZE → VERIFY
        ├── CONNECT → CREATE_SKILL → REFLECT
        ├── CONFIDENCE → STORE → TEST_REUSE
        └── Firewall (safety checks) + Curriculum (difficulty tracking)
```
