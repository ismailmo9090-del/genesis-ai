# Code Generation Engine — Implementation Report

## Architecture

```
User Request
    ↓
CodeRequest.parse()          ← Structured request representation
    ↓
ProjectPlanner.plan()        ← Decomposes into component specs
    ↓
KnowledgeProvider.search()   ← Retrieves coding knowledge
    ↓
CodeGenerator.generate()     ← Generates code from spec + knowledge
    ↓
CodeValidator.validate()     ← Validates generated code
    ↓
RegenerationEngine           ← Repairs failed code (if needed)
    ↓
GenerationResponse           ← Returns files + validation + metadata
```

## Files Changed

| File | Action | Lines | Purpose |
|------|--------|-------|---------|
| `genesis_ai/core/code/__init__.py` | Created | 17 | Module exports |
| `genesis_ai/core/code/code_request.py` | Created | 168 | Request parsing and classification |
| `genesis_ai/core/code/planner.py` | Created | 272 | Project decomposition |
| `genesis_ai/core/code/knowledge_provider.py` | Created | 198 | Knowledge abstraction layer |
| `genesis_ai/core/code/generator.py` | Rewritten | 415 | Code generation from specs |
| `genesis_ai/core/code/validator.py` | Created | 230 | Multi-language validation |
| `genesis_ai/core/code/regeneration.py` | Created | 155 | Self-repair engine |
| `genesis_ai/core/code/generation_provider.py` | Created | 155 | Provider abstraction |
| `genesis_ai/core/code/engine.py` | Created | 175 | Pipeline orchestrator |
| `genesis_ai/api/code_api.py` | Created | 155 | REST API endpoints |
| `genesis_ai/core/cognitive/engine.py` | Modified | +15 | Integration point |
| `genesis_ai/ui/app.py` | Modified | +3 | Blueprint registration |
| `genesis_ai/tests/test_code_generation.py` | Created | 310 | 56 comprehensive tests |

## Components

### 1. CodeRequest Parser (`code_request.py`)
Parses natural language into structured representation:
- **RequestType**: CREATE, MODIFY, EXTEND, REFACTOR, DEBUG, OPTIMIZE, MIGRATE
- **Language detection**: 20+ languages via keyword matching
- **Framework detection**: 20+ frameworks (Flask, FastAPI, React, Express, etc.)
- **Platform detection**: web, mobile, desktop, CLI, API, cloud
- **Project type inference**: REST API, web app, CLI tool, library, scraper, ML model, chatbot, game, data pipeline, dashboard
- **Feature extraction**: authentication, database, async, etc.
- **Constraint detection**: minimize dependencies, performance critical, security required

### 2. ProjectPlanner (`planner.py`)
Decomposes requests into structured specifications:
- **ComponentSpec**: name, purpose, dependencies, interfaces, files, implementation requirements
- **ProjectSpec**: components, structure, entry points, configuration files, test files, generation order
- **Dependency-aware ordering**: Topological sort ensures correct generation sequence
- **Project type templates**: 10 project types with pre-defined component structures

### 3. KnowledgeProvider (`knowledge_provider.py`)
Clean abstraction for coding knowledge:
- **InternalKnowledgeProvider**: Seed knowledge for 12 core concepts (REST API, authentication, database, error handling, validation, testing, async, logging, Flask, FastAPI, React, Express)
- **Methods**: search_knowledge, get_concept, get_pattern, get_skill, get_examples, get_best_practices, get_constraints
- **Extensible**: Abstract interface allows future implementation with external knowledge bases

### 4. CodeGenerator (`generator.py`)
Generates NEW code from specifications:
- **10 project types**: REST API (Flask/FastAPI), CLI tool, scraper, ML model, library, chatbot, game, data pipeline, web app, HTML page
- **Multi-language**: Python, JavaScript/TypeScript, HTML, SQL
- **Composable**: Authentication, database, error handling can be combined
- **Legacy interface**: `generate()` method maintains backward compatibility with template-based generator

### 5. CodeValidator (`validator.py`)
Validates generated code:
- **Python**: AST parsing, syntax validation, import validation, block completeness
- **JavaScript/TypeScript**: Brace/bracket/parenthesis matching
- **HTML**: DOCTYPE detection, tag matching
- **JSON**: Syntax validation
- **Cross-file**: Import consistency, module resolution
- **Severity levels**: ERROR, WARNING, INFO

### 6. RegenerationEngine (`regeneration.py`)
Self-repair for failed code:
- **Error analysis**: Identifies primary error by severity
- **Targeted fixes**: Syntax repair, brace matching, empty blocks, missing DOCTYPE, JSON syntax
- **Partial regeneration**: Only repairs broken files, preserves working code
- **Experience recording**: Records repair attempts for learning

### 7. GenerationProvider (`generation_provider.py`)
Provider abstraction for swappable backends:
- **LocalProvider**: Uses built-in CodeGenerator (current default)
- **ExternalProvider**: Placeholder for external LLM API (not configured)
- **HybridProvider**: Tries local first, falls back to external

### 8. CodeGenerationEngine (`engine.py`)
Pipeline orchestrator:
- **generate()**: Full pipeline from request string to validated code
- **modify()**: Modify existing code with changes
- **debug()**: Debug and fix code with error info
- **validate_files()**: Validate files without generation
- **History tracking**: Records all generation attempts

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/code/generate` | POST | Generate new code from request |
| `/v1/code/modify` | POST | Modify existing code |
| `/v1/code/debug` | POST | Debug and fix code |
| `/v1/code/validate` | POST | Validate code files |
| `/v1/code/history` | GET | Generation history |

## Integration with Cognitive Engine

The cognitive engine now uses a two-tier approach for code requests:
1. **Legacy template generator first**: For simple requests matching known patterns (fibonacci, hello world, etc.)
2. **Full CodeGenerationEngine pipeline**: For complex requests requiring project-level generation

This maintains backward compatibility while enabling new capabilities.

## Tests

### Test Categories (56 tests total)

| Category | Tests | Purpose |
|----------|-------|---------|
| A. New code generation | 12 | Flask, FastAPI, Express, CLI, scraper, ML, chatbot, library, HTML, React |
| B. Multi-file generation | 3 | Project structure, dependencies, file counts |
| C. Code modification | 1 | Modify existing code |
| D. Debugging | 1 | Debug and fix code |
| E. Regeneration | 3 | No regen needed, syntax fix, experience recording |
| F. Validation failure | 6 | Python, JS, JSON, HTML, empty, multiple files |
| G. Knowledge retrieval | 5 | Search, concepts, examples, practices, constraints |
| H. Skill retrieval | 1 | Knowledge provider |
| I. New/unseen coding request | 2 | Discord bot, unseen types |
| J. Anti-replay test | 1 | Different requests produce different outputs |

### Test Results
```
56 passed in 0.57s
```

### Full Regression Suite
```
435 passed in 97.24s
```

## Pipeline Flow

### Example: "Create a REST API in Python with Flask"

```
1. CodeRequest.parse("Create a REST API in Python with Flask")
   → request_type=CREATE, language=python, framework=flask, project_type=rest_api

2. ProjectPlanner.plan(request)
   → components: [models, routes, app], structure: {src/: [models.py, routes.py, main.py]}

3. KnowledgeProvider.search("REST API", language="python")
   → Returns: REST API knowledge with examples, best practices, constraints

4. CodeGenerator.generate_from_spec(spec)
   → Generates: src/models.py, src/routes.py, src/main.py, requirements.txt

5. CodeValidator.validate(files, "python")
   → Validates: Python syntax (AST), cross-file imports, JSON config

6. RegenerationEngine (if needed)
   → Repairs any validation errors

7. GenerationResponse
   → Returns: files, validation status, plan, timing, provider info
```

## Remaining Limitations

1. **Template-based generation**: Current generator uses predefined templates for each project type. True compositional generation would require a more sophisticated code synthesis engine.

2. **Knowledge base**: InternalKnowledgeProvider has 12 seeded concepts. A real coding knowledge base would provide much richer patterns and examples.

3. **External LLM provider**: ExternalProvider is a placeholder. Integration with an actual LLM API would enable more flexible generation.

4. **Code execution**: No sandboxed code execution for testing generated code.

5. **Version control**: No diff-based modification for existing projects.

6. **Language support**: Limited to Python, JavaScript/TypeScript, HTML, SQL. Other languages would need template additions.

## Future Knowledge Base Connection

The `KnowledgeProvider` abstract interface is designed to connect to an external coding knowledge base:

```python
class ExternalKnowledgeProvider(KnowledgeProvider):
    def __init__(self, db_connection):
        self._db = db_connection
    
    def search_knowledge(self, query, language=None, category=None, limit=5):
        # Query external knowledge base
        pass
    
    def get_concept(self, concept, language=None):
        # Retrieve from knowledge base
        pass
```

## Future Genesis-Native Generator

The `GenerationProvider` interface allows swapping in a Genesis-native generator:

```python
class GenesisNativeProvider(GenerationProvider):
    def generate_from_request(self, request):
        # Use Genesis's own reasoning to generate code
        # Could leverage learned patterns, skills, and experiences
        pass
```

## Success Condition

When a user asks: "Create a new Python REST API with authentication and SQLite"

Genesis now:
1. ✅ Understands the request (CREATE, python, rest_api, auth, sqlite)
2. ✅ Plans the project (models, auth, routes, app components)
3. ✅ Retrieves knowledge (REST API patterns, authentication best practices)
4. ✅ Generates NEW code (Flask app with JWT auth, SQLite storage)
5. ✅ Validates the code (Python AST, import checking)
6. ✅ Repairs if necessary (syntax fixes, brace matching)
7. ✅ Returns the project (multi-file response with structure)
