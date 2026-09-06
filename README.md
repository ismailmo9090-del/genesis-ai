# Genesis AI

**Learn by Experience, Not by Retraining.**

Genesis AI is a self-learning AI assistant that improves through every conversation, research session, and user interaction. Unlike traditional LLMs that require retraining, Genesis builds its own knowledge graph, develops skills, and refines its understanding autonomously.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Genesis AI Orchestrator                         │
│                          (main.py - GenesisAI)                          │
├─────────┬──────────┬──────────┬──────────┬──────────┬─────────────────┤
│         │          │          │          │          │                  │
│  ┌──────▼──────┐ ┌─▼────────┐│ ┌────────▼────┐ ┌──▼───────────┐    │
│  │ Conversation │ │  Memory   ││ │  Knowledge   │ │  Reasoning   │    │
│  │   Engine     │ │  Engine   ││ │   Graph      │ │   Engine     │    │
│  └──────┬──────┘ └─┬────────┘│ └────────┬────┘ └──┬───────────┘    │
│         │          │          │          │          │                  │
│  ┌──────▼──────┐ ┌─▼────────┐│ ┌────────▼────┐ ┌──▼───────────┐    │
│  │   Intent     │ │  Decay &  ││ │  Knowledge   │ │   Planning   │    │
│  │   Engine     │ │  Promote  ││ │  Storage     │ │   Engine     │    │
│  └─────────────┘ └──────────┘│ └─────────────┘ └──────────────┘    │
│                               │                                       │
│  ┌─────────────┐ ┌──────────┐│ ┌─────────────┐ ┌──────────────┐    │
│  │  Learning    │ │  Skill    ││ │ Verification │ │  Reflection  │    │
│  │  Engine      │ │  Engine   ││ │  Engine      │ │  Engine      │    │
│  └──────┬──────┘ └──────────┘│ └─────────────┘ └──────────────┘    │
│         │                     │                                       │
│  ┌──────▼──────┐ ┌──────────┐│ ┌─────────────┐ ┌──────────────┐    │
│  │  Feedback    │ │  Curiosity││ │  Privacy     │ │    Tool      │    │
│  │  Engine      │ │  Engine   ││ │  Engine      │ │    Engine    │    │
│  └─────────────┘ └──────────┘│ └─────────────┘ └──────────────┘    │
│                               │                                       │
├───────────────────────────────┴───────────────────────────────────────┤
│                        SQLite Database (WAL mode)                      │
│                     Thread-safe with connection pooling                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Core Modules (17 Total)

### 1. Conversation Engine (`core/conversation/engine.py`)
Processes user messages, classifies intent (GREETING, QUESTION, TASK_REQUEST, COMMAND, REFLECTION, FEEDBACK), maintains context, and generates responses. Supports Hinglish (Hindi-English mix).

### 2. Memory Engine (`core/memory/engine.py`)
Stores and retrieves memories with TF-IDF relevance scoring. Supports memory types: SHORT_TERM, LONG_TERM, EPISODIC, SEMANTIC, PROCEDURAL, SKILL. Implements automatic decay and promotion from short-term to long-term.

### 3. Knowledge Graph (`knowledge/graph/engine.py`)
Manages concepts and relationships as a graph structure. Supports concept creation, relationship typing (is_a, used_for, has, supports, requires, contradicts, etc.), path finding, subgraph extraction, and contradiction detection.

### 4. Knowledge Storage (`knowledge/storage/engine.py`)
Stores knowledge claims with TF-IDF search scoring. Tracks verification status (VERIFIED, PROBABLE, UNCERTAIN, CONTRADICTED, OUTDATED).

### 5. Knowledge Retrieval (`knowledge/retrieval/engine.py`)
Combines graph traversal and text search to find relevant knowledge. Merges results from both methods with confidence-weighted scoring.

### 6. Reasoning Engine (`core/reasoning/engine.py`)
Multi-strategy reasoning: query decomposition, rule-based reasoning, concept reasoning, task planning, and comparison analysis.

### 7. Verification Engine (`core/verification/engine.py`)
Evaluates claims against multiple sources. Calculates confidence based on agreement ratio, source reliability, and recency. Detects contradictions between claims.

### 8. Learning Engine (`core/learning/engine.py`)
Full learning pipeline: OBSERVE → UNDERSTAND → EXTRACT → COMPARE → VERIFY → GENERALIZE → STORE → CONNECT → TEST → IMPROVE. Handles duplicate detection and contradiction detection.

### 9. Skill Engine (`skills/engine.py`)
Creates and manages reusable procedural knowledge (skills). Supports skill adaptation for different contexts, proficiency tracking, and step-by-step execution.

### 10. Reflection Engine (`core/reflection/engine.py`)
Meta-cognitive analysis of tasks and conversations. Identifies knowledge gaps, tracks what worked/failed, and generates improvement suggestions.

### 11. Feedback Engine (`core/feedback/engine.py`)
Processes user feedback (positive, negative, correction, preference, rating). Applies confidence adjustments to knowledge and records correction events.

### 12. Tool Engine (`tools/engine.py`)
Manages tool registration and execution with safety controls. Built-in tools: calculator, python_exec, file_read, file_write, text_process, web_search. Includes rate limiting and danger level classification.

### 13. Curiosity Engine (`core/curiosity/engine.py`)
Identifies knowledge gaps and suggests learning topics. Manages a curiosity queue with priority-based processing and resource limits.

### 14. Planning Engine (`core/planning/engine.py`)
Task decomposition, execution tracking, and re-planning. Creates step-by-step plans from goal descriptions and tracks progress.

### 15. Privacy Engine (`privacy/engine.py`)
Enforces data protection: no telemetry, no background uploads, minimal web data. Sanitizes sensitive data, logs external requests, and provides data export/deletion.

### 16. Intent Engine (`core/conversation/intent.py`)
Classifies user messages into intent categories using keyword matching and pattern recognition.

### 17. Context Engine (`core/conversation/context.py`)
Tracks conversation context including topic, mode, and entity state across messages.

---

## Setup Instructions

### Prerequisites
- Python 3.8+
- pip

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd "Genesis AI"

# Install dependencies
pip install -r requirements.txt

# Run Genesis AI
python run.py
```

### Environment Variables (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `GENESIS_DB_PATH` | `genesis_data.db` | SQLite database file path |
| `GENESIS_UI_PORT` | `8080` | Web UI port |
| `GENESIS_PRIVACY_LEVEL` | `high` | Privacy level (high/medium/low) |
| `GENESIS_AUTONOMOUS_LEARNING` | `false` | Enable autonomous learning |
| `GENESIS_LOG_LEVEL` | `INFO` | Logging level |

---

## API Documentation

### Chat
```
POST /api/chat
Body: { "message": "Hello", "user_id": "user1" }
Response: { "response_text": "...", "intent": "GREETING", "confidence": 0.95, ... }
```

### Status
```
GET /api/status
Response: { "status": "online", "memory_count": 42, "knowledge_count": 15, ... }
```

### Memory
```
GET /api/memory
Response: { "stats": {...}, "recent_memories": [...] }
```

### Knowledge
```
GET /api/knowledge
Response: { "stats": {...}, "graph": [...] }
```

### Skills
```
GET /api/skills
Response: { "stats": {...}, "skills": [...] }
```

### Learning
```
GET /api/learning
Response: { "stats": {...}, "timeline": [...] }
```

### Feedback
```
POST /api/feedback
Body: { "user_id": 1, "type": "positive", "details": {...} }
Response: { "success": true, "feedback_type": "positive", ... }
```

### Reflection
```
GET /api/reflection
Response: { "what_learned": [...], "knowledge_gaps": [...], ... }
```

### Privacy
```
GET /api/privacy
Response: { "privacy_level": "high", "data_stored": {...}, ... }
```

### Research
```
GET /api/research/<query>
Response: { "query": "...", "sources_found": 3, "findings": [...], ... }
```

---

## Database Schema

Genesis AI uses SQLite with WAL mode for concurrent access. Key tables:

- **users** - User profiles and preferences
- **conversations** - Conversation sessions
- **messages** - Individual messages
- **memories** - All memory types with decay tracking
- **concepts** - Knowledge graph nodes
- **relationships** - Knowledge graph edges
- **knowledge** - Verified/unverified claims
- **skills** - Procedural knowledge with steps
- **experiences** - Task execution records
- **feedback** - User feedback entries
- **learning_sessions** - Autonomous learning tracking
- **research_sessions** - Web research records
- **contradictions** - Detected knowledge conflicts
- **curiosity_queue** - Learning queue
- **privacy_log** - External request audit log

---

## How Self-Learning Works

Genesis AI learns through a continuous pipeline:

### 1. Interaction Learning
```
User: "What is Python?"
System: "Python is a programming language..."
↓
OBSERVE → UNDERSTAND → EXTRACT knowledge → STORE in knowledge base
```

### 2. Research Learning
```
Query: "Latest Python features"
↓
Web Search → Extract facts → Verify against sources → Store verified knowledge
```

### 3. Feedback Learning
```
User: "That was wrong. Python was created by Guido van Rossum."
↓
CORRECTION → Update knowledge → Adjust confidence → Learn from correction
```

### 4. Experience Learning
```
Task: "Deploy web app" → Success/Failure
↓
Record experience → Extract lessons → Build skill → Improve future performance
```

### 5. Curiosity-Driven Learning
```
Knowledge gap detected: "No relationships for concept X"
↓
Add to curiosity queue → Research when idle → Fill knowledge gaps
```

---

## Demonstration Scenario

### Question 1: "What is Python?"
Genesis looks up its knowledge graph, finds the concept "Python", retrieves related knowledge claims, and responds with verified information. If no knowledge exists, it searches the web, extracts facts, verifies them, and stores the result.

### Question 2: "Help me build a web app"
Genesis creates a plan (decompose goal → gather resources → implement → test), checks for existing skills, and guides through each step. After completion, it records the experience and builds a reusable skill.

### Question 3: "What did we discuss before?"
Genesis retrieves recent memories, shows conversation history, and identifies recurring topics. It can reflect on past interactions and suggest continuations.

---

## Limitations

- **No real-time web browsing**: Web search uses simulated results unless connected to a real search API
- **No actual code execution**: The python_exec tool runs safe sandboxed expressions only
- **Knowledge quality depends on inputs**: Self-learning accuracy improves with quality feedback
- **No multi-user isolation in this version**: Single-user mode by default
- **SQLite limitations**: Not suitable for massive concurrent workloads
- **No GPU/ML inference**: All reasoning is rule-based and pattern-matching, not neural network based

---

## Future Roadmap

- [ ] Real web search integration (DuckDuckGo, Google Custom Search)
- [ ] Multi-user support with proper isolation
- [ ] File system integration for document understanding
- [ ] Plugin system for custom tools and skills
- [ ] REST API authentication
- [ ] Conversation export/import
- [ ] Knowledge graph visualization
- [ ] Scheduled autonomous learning tasks
- [ ] Integration with external databases
- [ ] Voice input/output support

---

## Privacy Commitment

Genesis AI is designed with privacy first:

- **No telemetry**: Zero data sent to external servers without explicit consent
- **No background uploads**: All data stays local
- **Minimal web data**: Only sanitized queries sent for search
- **User control**: Export or delete all your data anytime
- **Transparent logging**: All external requests are auditable
- **Sensitive data filtering**: Automatic detection and redaction of passwords, API keys, SSNs, etc.

---

## License

MIT License

Copyright (c) 2026 Genesis AI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
