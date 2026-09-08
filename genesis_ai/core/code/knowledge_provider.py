"""Knowledge provider interface — abstraction for accessing coding knowledge."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CodingKnowledge:
    """A piece of coding knowledge."""
    concept: str
    description: str
    language: Optional[str] = None
    framework: Optional[str] = None
    category: str = "general"
    examples: list[str] = field(default_factory=list)
    best_practices: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    confidence: float = 1.0
    source: str = "internal"


class KnowledgeProvider(ABC):
    """Abstract interface for accessing coding knowledge."""

    @abstractmethod
    def search_knowledge(self, query: str, language: Optional[str] = None,
                         category: Optional[str] = None, limit: int = 5) -> list[CodingKnowledge]:
        """Search for coding knowledge matching the query."""

    @abstractmethod
    def get_concept(self, concept: str, language: Optional[str] = None) -> Optional[CodingKnowledge]:
        """Get knowledge for a specific concept."""

    @abstractmethod
    def get_pattern(self, pattern_name: str, language: Optional[str] = None) -> Optional[CodingKnowledge]:
        """Get a specific design or code pattern."""

    @abstractmethod
    def get_skill(self, skill_name: str, language: Optional[str] = None) -> Optional[CodingKnowledge]:
        """Get knowledge about a specific coding skill."""

    @abstractmethod
    def get_examples(self, concept: str, language: Optional[str] = None, limit: int = 3) -> list[str]:
        """Get code examples for a concept."""

    @abstractmethod
    def get_best_practices(self, concept: str, language: Optional[str] = None) -> list[str]:
        """Get best practices for a concept."""

    @abstractmethod
    def get_constraints(self, concept: str, language: Optional[str] = None) -> list[str]:
        """Get constraints and limitations for a concept."""


class InternalKnowledgeProvider(KnowledgeProvider):
    """Knowledge provider backed by Genesis's internal knowledge and learned experience."""

    def __init__(self, db_manager=None):
        self._db = db_manager
        self._knowledge_store: dict[str, CodingKnowledge] = {}
        self._seed_knowledge()

    def _seed_knowledge(self) -> None:
        self._knowledge_store = {
            "rest_api": CodingKnowledge(
                concept="REST API",
                description="RESTful API with HTTP methods and JSON payloads",
                category="architecture",
                examples=[
                    "GET /api/resource — list resources",
                    "POST /api/resource — create resource",
                    "GET /api/resource/:id — get resource",
                    "PUT /api/resource/:id — update resource",
                    "DELETE /api/resource/:id — delete resource",
                ],
                best_practices=[
                    "Use proper HTTP status codes",
                    "Validate request input",
                    "Return consistent JSON structure",
                    "Handle errors gracefully",
                    "Use pagination for list endpoints",
                ],
                constraints=[
                    "Stateless server",
                    "Use standard HTTP methods",
                    "Resource-oriented URLs",
                ],
                patterns=["Repository Pattern", "Service Layer", "Middleware Chain"],
            ),
            "authentication": CodingKnowledge(
                concept="Authentication",
                description="User identity verification and session management",
                category="security",
                examples=[
                    "JWT token-based authentication",
                    "Session-based authentication",
                    "OAuth2 flow",
                ],
                best_practices=[
                    "Hash passwords with bcrypt/argon2",
                    "Use short-lived access tokens",
                    "Implement refresh token rotation",
                    "Rate limit login attempts",
                    "Log authentication events",
                ],
                constraints=[
                    "Never store plaintext passwords",
                    "Use HTTPS in production",
                    "Validate token signatures",
                ],
                patterns=["JWT", "Session Store", "OAuth2 Provider"],
            ),
            "database": CodingKnowledge(
                concept="Database Integration",
                description="Data persistence and retrieval patterns",
                category="data",
                examples=[
                    "SQLAlchemy ORM models",
                    "SQLite connection pooling",
                    "Migration scripts",
                ],
                best_practices=[
                    "Use parameterized queries",
                    "Implement connection pooling",
                    "Create proper indexes",
                    "Use migrations for schema changes",
                ],
                constraints=[
                    "ACID compliance",
                    "Foreign key constraints",
                    "Connection limits",
                ],
                patterns=["Repository", "Unit of Work", "Active Record"],
            ),
            "error_handling": CodingKnowledge(
                concept="Error Handling",
                description="Graceful error handling and recovery patterns",
                category="pattern",
                examples=[
                    "Try-except with specific exceptions",
                    "Custom exception classes",
                    "Error response middleware",
                ],
                best_practices=[
                    "Catch specific exceptions, not bare except",
                    "Log errors with context",
                    "Return meaningful error messages",
                    "Implement retry logic for transient failures",
                ],
                constraints=[
                    "Don't expose internal errors to users",
                    "Don't swallow exceptions silently",
                ],
                patterns=["Circuit Breaker", "Retry with Backoff", "Fallback"],
            ),
            "validation": CodingKnowledge(
                concept="Input Validation",
                description="Request and data validation patterns",
                category="security",
                examples=[
                    "Pydantic model validation",
                    "Schema-based validation",
                    "Sanitization functions",
                ],
                best_practices=[
                    "Validate on input, not output",
                    "Use schema validation",
                    "Sanitize user input",
                    "Reject invalid input early",
                ],
                constraints=[
                    "Never trust user input",
                    "Validate all external data",
                ],
                patterns=["Schema Validation", "Builder Pattern", "Chain of Responsibility"],
            ),
            "testing": CodingKnowledge(
                concept="Testing",
                description="Unit, integration, and end-to-end testing patterns",
                category="quality",
                examples=[
                    "pytest fixtures and parametrize",
                    "unittest.TestCase classes",
                    "API endpoint testing",
                ],
                best_practices=[
                    "Write tests before code (TDD)",
                    "Test edge cases and error paths",
                    "Use mocks for external dependencies",
                    "Keep tests fast and isolated",
                ],
                constraints=[
                    "Tests must be deterministic",
                    "Tests must not depend on external state",
                ],
                patterns=["AAA Pattern", "Given-When-Then", "Page Object Model"],
            ),
            "async": CodingKnowledge(
                concept="Async Programming",
                description="Asynchronous and concurrent programming patterns",
                category="pattern",
                examples=[
                    "asyncio event loop",
                    "aiohttp async HTTP client",
                    "concurrent.futures thread pool",
                ],
                best_practices=[
                    "Don't mix sync and async code",
                    "Use async HTTP clients for I/O",
                    "Implement proper shutdown",
                    "Handle cancellation gracefully",
                ],
                constraints=[
                    "Async functions must be awaited",
                    "Event loop must not be blocked",
                ],
                patterns=["Producer-Consumer", "Fan-Out/Fan-In", "Actor Model"],
            ),
            "logging": CodingKnowledge(
                concept="Logging",
                description="Structured logging and monitoring patterns",
                category="operations",
                examples=[
                    "Python logging module configuration",
                    "Structured JSON logging",
                    "Request ID propagation",
                ],
                best_practices=[
                    "Use structured logging",
                    "Include request context",
                    "Log at appropriate levels",
                    "Don't log sensitive data",
                ],
                constraints=[
                    "Logging must not block main thread",
                    "Log rotation needed for production",
                ],
                patterns=["Correlation ID", "Log Aggregation", "Health Check"],
            ),
            "flask": CodingKnowledge(
                concept="Flask Web Framework",
                description="Lightweight Python web framework patterns",
                language="python",
                framework="flask",
                category="framework",
                examples=[
                    "Route decorators",
                    "Blueprint organization",
                    "Template rendering",
                ],
                best_practices=[
                    "Use Blueprints for large apps",
                    "Use Flask-SQLAlchemy for ORM",
                    "Use Flask-Migrate for migrations",
                    "Configure via environment variables",
                ],
                constraints=["WSGI compliant", "Thread-local context"],
                patterns=["Blueprint", "Application Factory", "Before Request"],
            ),
            "fastapi": CodingKnowledge(
                concept="FastAPI Web Framework",
                description="Modern async Python web framework with automatic docs",
                language="python",
                framework="fastapi",
                category="framework",
                examples=[
                    "Pydantic request/response models",
                    "Dependency injection",
                    "Background tasks",
                ],
                best_practices=[
                    "Use Pydantic models for validation",
                    "Use dependency injection",
                    "Use async functions for I/O",
                    "Leverage automatic OpenAPI docs",
                ],
                constraints=["ASGI server required", "Pydantic v2 preferred"],
                patterns=["Dependency Injection", "Response Model", "Middleware"],
            ),
            "react": CodingKnowledge(
                concept="React Frontend",
                description="Component-based UI library patterns",
                language="javascript",
                framework="react",
                category="framework",
                examples=[
                    "Functional components with hooks",
                    "State management with useState/useReducer",
                    "Effect handling with useEffect",
                ],
                best_practices=[
                    "Use functional components",
                    "Keep components small and focused",
                    "Lift state up when needed",
                    "Use context for global state",
                ],
                constraints=["JSX required", "Virtual DOM limitations"],
                patterns=["Container/Presentational", "Render Props", "Hooks"],
            ),
            "express": CodingKnowledge(
                concept="Express.js Web Framework",
                description="Minimal Node.js web framework patterns",
                language="javascript",
                framework="express",
                category="framework",
                examples=[
                    "Route handlers",
                    "Middleware chains",
                    "Error handling middleware",
                ],
                best_practices=[
                    "Use express.Router for modular routes",
                    "Use helmet for security headers",
                    "Use morgan for logging",
                    "Validate request bodies",
                ],
                constraints=["Callback-based (use async for modern code)"],
                patterns=["Middleware", "Router", "Error Handler"],
            ),
        }

    def search_knowledge(self, query: str, language: Optional[str] = None,
                         category: Optional[str] = None, limit: int = 5) -> list[CodingKnowledge]:
        query_lower = query.lower()
        results: list[tuple[float, CodingKnowledge]] = []

        for kb in self._knowledge_store.values():
            score = 0.0
            if query_lower in kb.concept.lower():
                score += 1.0
            if query_lower in kb.description.lower():
                score += 0.5
            for word in query_lower.split():
                if word in kb.concept.lower():
                    score += 0.3
                if word in kb.description.lower():
                    score += 0.2
                if word in kb.category:
                    score += 0.1
            if language and kb.language == language:
                score += 0.2
            if category and kb.category == category:
                score += 0.1
            if score > 0:
                results.append((score, kb))

        results.sort(key=lambda x: x[0], reverse=True)
        return [kb for _, kb in results[:limit]]

    def get_concept(self, concept: str, language: Optional[str] = None) -> Optional[CodingKnowledge]:
        for kb in self._knowledge_store.values():
            if concept.lower() in kb.concept.lower():
                if language is None or kb.language is None or kb.language == language:
                    return kb
        return None

    def get_pattern(self, pattern_name: str, language: Optional[str] = None) -> Optional[CodingKnowledge]:
        for kb in self._knowledge_store.values():
            if any(pattern_name.lower() in p.lower() for p in kb.patterns):
                return kb
        return None

    def get_skill(self, skill_name: str, language: Optional[str] = None) -> Optional[CodingKnowledge]:
        return self.get_concept(skill_name, language)

    def get_examples(self, concept: str, language: Optional[str] = None, limit: int = 3) -> list[str]:
        kb = self.get_concept(concept, language)
        if kb:
            return kb.examples[:limit]
        return []

    def get_best_practices(self, concept: str, language: Optional[str] = None) -> list[str]:
        kb = self.get_concept(concept, language)
        if kb:
            return kb.best_practices
        return []

    def get_constraints(self, concept: str, language: Optional[str] = None) -> list[str]:
        kb = self.get_concept(concept, language)
        if kb:
            return kb.constraints
        return []
