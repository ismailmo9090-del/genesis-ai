# Genesis AI - Technical Architecture

## System Diagram

```
                            ┌──────────────────────┐
                            │      User Input       │
                            │   (Chat / API Call)    │
                            └──────────┬───────────┘
                                       │
                            ┌──────────▼───────────┐
                            │    GenesisAI.main      │
                            │    (Orchestrator)      │
                            └──────────┬───────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
           ┌────────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
           │  Conversation    │ │  Planning   │ │   Privacy       │
           │  Engine          │ │  Engine     │ │   Engine        │
           │  - IntentClass   │ │  - Create   │ │   - Check       │
           │  - ContextTrack  │ │  - Execute  │ │   - Sanitize    │
           │  - ResponseGen   │ │  - Replan   │ │   - Log         │
           └────────┬────────┘ └──────┬──────┘ └────────┬────────┘
                    │                  │                  │
           ┌────────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
           │  Memory Engine   │ │  Reasoning  │ │   Tool Engine   │
           │  - Store         │ │  Engine     │ │   - Register    │
           │  - Retrieve      │ │  - Decompose│ │   - Execute     │
           │  - Decay/Promote │ │  - Rules    │ │   - Rate Limit  │
           │  - TF-IDF Search │ │  - Concepts │ │   - Builtins    │
           └────────┬────────┘ └──────┬──────┘ └────────┬────────┘
                    │                  │                  │
           ┌────────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
           │  Knowledge       │ │ Verification│ │   Feedback      │
           │  Graph           │ │ Engine      │ │   Engine        │
           │  - Concepts      │ │ - Verify    │ │   - Positive    │
           │  - Relationships │ │ - Compare   │ │   - Negative    │
           │  - Path Finding  │ │ - Consistency│ │   - Correction  │
           │  - Subgraph      │ │ - Confidence│ │   - Rating      │
           └────────┬────────┘ └──────┬──────┘ └────────┬────────┘
                    │                  │                  │
           ┌────────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
           │  Knowledge       │ │  Learning   │ │   Curiosity     │
           │  Storage         │ │  Engine     │ │   Engine        │
           │  - TF-IDF        │ │ - Pipeline  │ │   - Gaps        │
           │  - Search        │ │ - Duplicate │ │   - Queue       │
           │  - Status Mgmt   │ │ - Contradict│ │   - Suggest     │
           └────────┬────────┘ │ - Confidence│ └────────┬────────┘
                    │          └──────┬──────┘          │
           ┌────────▼────────┐       │          ┌───────▼────────┐
           │  Knowledge       │       │          │  Reflection    │
           │  Retrieval       │       │          │  Engine        │
           │  - Text Search   │       │          │  - Task Reflect│
           │  - Graph Search  │       │          │  - Conv Reflect│
           │  - Merge Results │       │          │  - Gap Identify│
           └────────┬────────┘       │          └───────┬────────┘
                    │                │                  │
                    └────────────────┼──────────────────┘
                                     │
                            ┌────────▼────────┐
                            │  Skill Engine    │
                            │  - Create        │
                            │  - Search        │
                            │  - Reuse         │
                            │  - Adapt         │
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │  SQLite Database │
                            │  (WAL Mode)      │
                            └─────────────────┘
```

---

## Data Flow

### Chat Flow

```
User Message
     │
     ▼
┌─────────────┐     ┌──────────────┐
│ Intent      │────▶│ Context      │
│ Classifier  │     │ Tracker      │
└──────┬──────┘     └──────┬───────┘
       │                   │
       ▼                   ▼
┌──────────────────────────────────┐
│        Response Generator        │
│  - Greeting → Welcome message    │
│  - Question → Knowledge lookup   │
│  - Task → Plan creation          │
│  - Command → Execute action      │
│  - Reflection → History/gaps     │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│        Memory Storage            │
│  - Store user message            │
│  - Store assistant response      │
│  - Update access counts          │
└──────────────────────────────────┘
```

### Question Handling Flow

```
Question
     │
     ▼
┌────────────────────┐
│ Knowledge Retrieval │
│ - Text search       │
│ - Graph traversal   │
│ - Merge & rank      │
└────────┬───────────┘
         │
    ┌────▼────┐
    │ Found?  │
    └────┬────┘
    Yes  │  No
    │    │
    ▼    ▼
┌──────┐ ┌──────────────┐
│Reply │ │ Web Search    │
│from  │ │ - Search      │
│local │ │ - Extract     │
│knowl.│ │ - Verify      │
└──────┘ │ - Store       │
         └──────┬───────┘
                │
                ▼
         ┌──────────────┐
         │ Response with │
         │ sources       │
         └──────────────┘
```

### Learning Pipeline

```
New Information (interaction/research/feedback)
     │
     ▼
┌──────────┐   ┌──────────┐   ┌──────────┐
│ OBSERVE  │──▶│UNDERSTAND│──▶│ EXTRACT  │
│ Capture  │   │ Analyze  │   │ Identify │
│ raw data │   │ context  │   │ knowledge│
└──────────┘   └──────────┘   └────┬─────┘
                                    │
     ┌──────────────────────────────┘
     ▼
┌──────────┐   ┌──────────┐   ┌──────────┐
│ COMPARE  │──▶│ VERIFY   │──▶│GENERALIZE│
│ Check for│   │ Check    │   │ Remove   │
│ duplicates│  │ contradict│  │ specifics│
└──────────┘   └──────────┘   └────┬─────┘
                                    │
     ┌──────────────────────────────┘
     ▼
┌──────────┐   ┌──────────┐   ┌──────────┐
│  STORE   │──▶│ CONNECT  │──▶│   TEST   │
│ Insert   │   │ Link to  │   │ Validate │
│ knowledge│   │ concepts │   │ against  │
└──────────┘   └──────────┘   │ existing │
                               └────┬─────┘
                                    │
                                    ▼
                             ┌──────────┐
                             │ IMPROVE  │
                             │ Adjust   │
                             │ confidence│
                             └──────────┘
```

---

## Knowledge Representation

### Concept
```json
{
  "id": 1,
  "name": "Python",
  "type": "programming_language",
  "description": "A high-level programming language",
  "definition": "Python is an interpreted, high-level programming language...",
  "examples": ["print('hello')", "def func(): ..."],
  "confidence": 0.85
}
```

### Relationship
```json
{
  "id": 1,
  "source_concept_id": 1,
  "target_concept_id": 2,
  "relation_type": "used_for",
  "strength": 0.8,
  "metadata": {}
}
```

### Knowledge Claim
```json
{
  "id": 1,
  "concept_id": 1,
  "claim": "Python was created by Guido van Rossum",
  "claim_type": "fact",
  "confidence": 0.95,
  "verification_status": "verified",
  "source_id": 1
}
```

### Skill
```json
{
  "id": 1,
  "name": "Deploy Web App",
  "description": "Deploy a web application to production",
  "skill_type": "deployment",
  "proficiency": 0.7,
  "usage_count": 5,
  "steps": [
    {"step_number": 1, "action": "Build production bundle", "description": "..."},
    {"step_number": 2, "action": "Run tests", "description": "..."},
    {"step_number": 3, "action": "Deploy to server", "description": "..."}
  ]
}
```

---

## Reasoning Approach

Genesis AI uses **multiple reasoning strategies** rather than neural inference:

### 1. Rule-Based Reasoning
Pattern matching against predefined rules:
```
IF claim contains "verified" THEN confidence_boost
IF claim contains "peer-reviewed" THEN source_reliability
IF claim contains "contradicts" THEN contradiction_warning
```

### 2. Concept Reasoning
Graph traversal to find related concepts and their relationships:
```
Query: "Python web frameworks"
→ Find concept "Python"
→ Traverse relationships (used_for → Flask, Django)
→ Analyze relationship types and strengths
→ Generate insights
```

### 3. Deductive Reasoning
Syllogistic logic from knowledge base:
```
Premise 1: "All mammals are warm-blooded"
Premise 2: "A dog is a mammal"
Conclusion: "A dog is warm-blooded"
```

### 4. Abductive Reasoning
Inference to best explanation:
```
Observation: "Verified claim X exists on topic T"
Observation: "Disputed claim Y exists on topic T"
Inference: "Disputed claim Y may be false"
```

### 5. Query Decomposition
Breaking complex queries into sub-queries:
```
"What is Python and how to use Flask?"
→ "What is Python"
→ "How to use Flask"
→ "Relationship between Python and Flask"
```

---

## Module Communication

### Direct Dependencies
```
GenesisAI (orchestrator)
├── DatabaseManager (shared database)
├── ConversationEngine
│   ├── IntentEngine (internal)
│   ├── ContextEngine (internal)
│   └── MemoryEngine
├── MemoryEngine
├── KnowledgeGraph
├── KnowledgeStorage
├── KnowledgeRetrieval
│   ├── KnowledgeGraph
│   └── KnowledgeStorage
├── ReasoningEngine
│   ├── KnowledgeGraph
│   └── KnowledgeRetrieval
├── WebSearchEngine (external)
├── InformationExtraction (external)
├── SourceManager
├── VerificationEngine
├── LearningEngine
├── SkillEngine
├── ReflectionEngine
│   └── KnowledgeGraph
├── PrivacyEngine
├── FeedbackEngine
├── ToolEngine
├── CuriosityEngine
└── PlanningEngine
```

### Communication Patterns

1. **Orchestrated Flow**: GenesisAI routes messages through appropriate engines
2. **Shared Database**: All engines share a single DatabaseManager instance
3. **Event-Driven**: Feedback triggers knowledge updates; learning triggers skill creation
4. **Pipeline Processing**: Learning follows a fixed pipeline (OBSERVE→IMPROVE)
5. **Graph Traversal**: Knowledge retrieval combines text search with graph walking

---

## Database Design

### Threading Model
- **Connection Pooling**: Thread-local connections via `threading.local()`
- **WAL Mode**: Enables concurrent reads during writes
- **Foreign Keys**: Enforced with `PRAGMA foreign_keys=ON`
- **Busy Timeout**: 5-second timeout for locked database

### Schema Highlights
- **17 tables** covering all data types
- **JSON fields** for flexible metadata storage
- **Timestamps** on all records for audit trail
- **Cascade deletes** for data integrity
- **Indexes** on all frequently queried columns

### Data Retention
- Short-term memories: Auto-decayed, max 100 entries
- Long-term memories: Persist until manually deleted
- Knowledge claims: Permanent with verification status
- Privacy log: Retained per FEEDBACK_RETENTION_DAYS setting
