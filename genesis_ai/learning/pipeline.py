"""Learning Pipeline — processes experiences through multi-stage learning.

Every experience passes through:
  EXPERIENCE → OBSERVE → UNDERSTAND → REPRESENT → EXTRACT → GENERALIZE →
  VERIFY → CONNECT → CREATE_SKILL → REFLECT → CONFIDENCE → STORE → TEST

This is NOT a simple Q&A storage system. It extracts reusable knowledge,
patterns, and skills from experiences.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from genesis_ai.database.db import DatabaseManager
from .experience_memory import Experience, ExperienceMemory

logger = logging.getLogger(__name__)


@dataclass
class LearningResult:
    """Result of processing an experience through the learning pipeline."""
    experience_id: str = ""
    success: bool = False
    lessons_learned: list[str] = field(default_factory=list)
    generalizations: list[str] = field(default_factory=list)
    knowledge_created: list[dict] = field(default_factory=list)
    skills_created: list[dict] = field(default_factory=list)
    skills_updated: list[dict] = field(default_factory=list)
    contradictions_found: list[dict] = field(default_factory=list)
    confidence_delta: float = 0.0
    steps_completed: list[str] = field(default_factory=list)
    error: Optional[str] = None
    duration: float = 0.0


class LearningPipeline:
    """Multi-stage learning pipeline that processes experiences into knowledge.

    This is the core learning engine. It does NOT simply store Q&A pairs.
    It extracts:
    - Facts and claims
    - Patterns and generalizations
    - Procedures and skills
    - Failure lessons
    - Success strategies
    """

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.experience_memory = ExperienceMemory(db)
        self._ensure_knowledge_tables()

    def _ensure_knowledge_tables(self):
        """Create tables for learned knowledge, skills, and generalizations."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS learned_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concept TEXT NOT NULL,
                claim TEXT NOT NULL,
                relationships TEXT DEFAULT '[]',
                source TEXT DEFAULT 'experience',
                evidence TEXT DEFAULT '[]',
                confidence REAL DEFAULT 0.5,
                created_at REAL NOT NULL,
                last_verified REAL,
                freshness REAL DEFAULT 1.0,
                scope TEXT DEFAULT 'general',
                exceptions TEXT DEFAULT '[]',
                status TEXT DEFAULT 'UNCERTAIN',
                usage_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0,
                experience_ids TEXT DEFAULT '[]'
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS learned_skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id TEXT UNIQUE,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                purpose TEXT DEFAULT '',
                requirements TEXT DEFAULT '[]',
                inputs TEXT DEFAULT '[]',
                outputs TEXT DEFAULT '[]',
                preconditions TEXT DEFAULT '[]',
                procedure TEXT DEFAULT '[]',
                failure_conditions TEXT DEFAULT '[]',
                recovery_strategies TEXT DEFAULT '[]',
                dependencies TEXT DEFAULT '[]',
                confidence REAL DEFAULT 0.5,
                success_rate REAL DEFAULT 0.0,
                experience_count INTEGER DEFAULT 0,
                last_used REAL,
                related_concepts TEXT DEFAULT '[]',
                version INTEGER DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS learned_generalizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL,
                description TEXT NOT NULL,
                conditions TEXT DEFAULT '[]',
                exceptions TEXT DEFAULT '[]',
                evidence TEXT DEFAULT '[]',
                confidence REAL DEFAULT 0.5,
                scope TEXT DEFAULT 'general',
                source_experiences TEXT DEFAULT '[]',
                created_at REAL NOT NULL,
                last_verified REAL,
                usage_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS prediction_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experience_id TEXT,
                expected TEXT DEFAULT '',
                expected_confidence REAL DEFAULT 0.5,
                actual TEXT DEFAULT '',
                prediction_error REAL DEFAULT 0.0,
                lesson TEXT DEFAULT '',
                timestamp REAL NOT NULL
            )
        """)

    def process_experience(self, experience: Experience) -> LearningResult:
        """Process a single experience through the full learning pipeline.

        This is the main entry point. It runs all stages and returns
        a LearningResult with what was learned.
        """
        start = time.time()
        result = LearningResult(experience_id=experience.experience_id)

        try:
            # Stage 1: OBSERVE
            result.steps_completed.append("OBSERVE")
            observations = self._observe(experience)

            # Stage 2: UNDERSTAND
            result.steps_completed.append("UNDERSTAND")
            understanding = self._understand(experience, observations)

            # Stage 3: REPRESENT
            result.steps_completed.append("REPRESENT")
            representation = self._represent(experience, understanding)

            # Stage 4: EXTRACT FACTS
            result.steps_completed.append("EXTRACT_FACTS")
            facts = self._extract_facts(experience, representation)

            # Stage 5: EXTRACT PATTERNS
            result.steps_completed.append("EXTRACT_PATTERNS")
            patterns = self._extract_patterns(experience, facts)

            # Stage 6: IDENTIFY SUCCESS/FAILURE
            result.steps_completed.append("IDENTIFY_OUTCOME")
            outcome_analysis = self._identify_outcome(experience)

            # Stage 7: GENERALIZE
            result.steps_completed.append("GENERALIZE")
            generalizations = self._generalize(experience, patterns, outcome_analysis)
            result.generalizations = generalizations

            # Stage 8: VERIFY
            result.steps_completed.append("VERIFY")
            verification = self._verify(experience, facts, generalizations)

            # Stage 9: CONNECT
            result.steps_completed.append("CONNECT")
            connections = self._connect(experience, facts, generalizations)

            # Stage 10: CREATE/UPDATE SKILL
            result.steps_completed.append("CREATE_SKILL")
            skill_result = self._create_or_update_skill(experience, outcome_analysis)
            if skill_result:
                result.skills_created.append(skill_result)

            # Stage 11: REFLECT
            result.steps_completed.append("REFLECT")
            reflection = self._reflect(experience, outcome_analysis, generalizations)
            result.lessons_learned = reflection.get("lessons", [])

            # Stage 12: CONFIDENCE UPDATE
            result.steps_completed.append("CONFIDENCE_UPDATE")
            result.confidence_delta = self._update_confidence(experience, outcome_analysis)

            # Stage 13: STORE
            result.steps_completed.append("STORE")
            self._store_knowledge(facts, generalizations, experience)

            # Stage 14: TEST REUSE
            result.steps_completed.append("TEST_REUSE")
            self._test_reuse(generalizations, experience)

            result.success = True

        except Exception as e:
            logger.error("Learning pipeline error: %s", e, exc_info=True)
            result.error = str(e)

        result.duration = time.time() - start
        return result

    def _observe(self, experience: Experience) -> dict:
        """Stage 1: OBSERVE — extract raw observations from the experience."""
        observations = {
            "task_words": set(re.findall(r'\b[a-z]+\b', experience.task.lower())),
            "goal_words": set(re.findall(r'\b[a-z]+\b', experience.goal.lower())),
            "has_errors": bool(experience.errors),
            "error_count": len(experience.errors),
            "action_count": len(experience.actions),
            "tools_used": set(experience.tools_used),
            "attempt_count": len(experience.attempts),
            "success": experience.success,
            "duration": experience.duration,
            "difficulty": experience.difficulty,
        }
        return observations

    def _understand(self, experience: Experience, observations: dict) -> dict:
        """Stage 2: UNDERSTAND — interpret what the experience means."""
        understanding = {
            "task_type": self._classify_task_type(experience),
            "domain": self._extract_domain(experience),
            "complexity": self._assess_complexity(experience),
            "key_concepts": self._extract_key_concepts(experience),
            "failure_categories": self._categorize_failures(experience) if not experience.success else [],
            "success_factors": self._identify_success_factors(experience) if experience.success else [],
        }
        return understanding

    def _represent(self, experience: Experience, understanding: dict) -> dict:
        """Stage 3: REPRESENT — create a structured representation."""
        return {
            "task_representation": {
                "type": understanding["task_type"],
                "domain": understanding["domain"],
                "concepts": understanding["key_concepts"],
                "complexity": understanding["complexity"],
            },
            "outcome_representation": {
                "success": experience.success,
                "errors": experience.errors,
                "lessons": experience.lessons,
            },
            "procedure_representation": {
                "actions": experience.actions,
                "tools": experience.tools_used,
                "attempts": experience.attempts,
            },
        }

    def _extract_facts(self, experience: Experience, representation: dict) -> list[dict]:
        """Stage 4: EXTRACT FACTS — identify factual claims from the experience."""
        facts = []

        # PRIORITY: Extract actual claim from teaching result if available
        result = experience.result if isinstance(experience.result, dict) else {}
        if result.get("claim"):
            concept = result.get("concept", "")
            if not concept:
                # Extract concept from task
                task_concepts = representation["task_representation"]["concepts"]
                concept = task_concepts[0] if task_concepts else "general"
            facts.append({
                "concept": concept,
                "claim": result["claim"],
                "confidence": result.get("confidence", 0.8),
                "source": "teaching",
            })
        # Also extract from evidence if provided (filter out web search garbage)
        if experience.evidence:
            for ev in experience.evidence:
                if isinstance(ev, dict) and ev.get("claim"):
                    source = ev.get("source", "teaching_evidence")
                    claim_text = ev["claim"]
                    # Skip ALL web search results — they are raw snippets, not learned knowledge
                    # Sources that are URLs indicate web search results
                    if source.startswith("http") or source.startswith("www."):
                        continue
                    if "DuckDuckGo" in source or "search" in source.lower():
                        continue
                    # Use generic quality scorer instead of hardcoded patterns
                    from genesis_ai.utils.quality import quality_score
                    if quality_score(claim_text) < 0.4:
                        continue
                    facts.append({
                        "concept": ev.get("concept", result.get("concept", "general")),
                        "claim": claim_text,
                        "confidence": ev.get("confidence", 0.7),
                        "source": source,
                    })

        # Fallback: Do NOT create generic "Task involved X" entries — they are garbage
        # If no actual claims found, return empty list

        # Extract from errors (failure facts)
        for error in experience.errors:
            facts.append({
                "concept": "failure",
                "claim": f"Error occurred: {error[:100]}",
                "confidence": 0.8,
                "source": "experience_error",
            })

        # Extract from lessons (skip raw user queries that look like reflections)
        for lesson in experience.lessons:
            # Skip if lesson is just the raw user query
            if lesson == experience.task:
                continue
            facts.append({
                "concept": "lesson",
                "claim": lesson,
                "confidence": 0.7,
                "source": "experience_lesson",
            })

        # Do NOT store raw reflections as knowledge — they are just user queries

        return facts

    def _extract_patterns(self, experience: Experience, facts: list[dict]) -> list[dict]:
        """Stage 5: EXTRACT PATTERNS — find recurring patterns."""
        patterns = []

        # Pattern: repeated errors
        if len(experience.errors) > 1:
            patterns.append({
                "pattern": "multiple_errors",
                "description": f"Task had {len(experience.errors)} errors, suggesting systematic issues",
                "confidence": 0.6,
            })

        # Pattern: retry success
        if experience.success and len(experience.attempts) > 1:
            patterns.append({
                "pattern": "retry_success",
                "description": "Task succeeded after multiple attempts, suggesting persistence is valuable",
                "confidence": 0.5,
            })

        # Pattern: tool usage
        if experience.tools_used:
            patterns.append({
                "pattern": "tool_dependent",
                "description": f"Task required tools: {', '.join(experience.tools_used)}",
                "confidence": 0.7,
            })

        # Pattern: fast completion
        if experience.success and experience.duration < 5.0:
            patterns.append({
                "pattern": "efficient_completion",
                "description": "Task completed quickly, suggesting well-understood domain",
                "confidence": 0.5,
            })

        return patterns

    def _identify_outcome(self, experience: Experience) -> dict:
        """Stage 6: IDENTIFY SUCCESS/FAILURE — analyze what happened."""
        if experience.success:
            return {
                "outcome": "success",
                "factors": self._identify_success_factors(experience),
                "reusability": "high" if not experience.errors else "medium",
            }
        else:
            return {
                "outcome": "failure",
                "categories": self._categorize_failures(experience),
                "root_cause": self._find_root_cause(experience),
                "correction": self._suggest_correction(experience),
            }

    def _generalize(self, experience: Experience, patterns: list[dict], outcome: dict) -> list[str]:
        """Stage 7: GENERALIZE — transform specific experience into reusable knowledge."""
        generalizations = []

        if outcome["outcome"] == "failure":
            # Generalize from failure
            categories = outcome.get("categories", [])
            for cat in categories:
                gen = self._failure_category_to_generalization(cat, experience)
                if gen:
                    generalizations.append(gen)

            # Generalize root cause
            root_cause = outcome.get("root_cause", "")
            if root_cause:
                generalizations.append(
                    f"Failure type '{root_cause}': Always verify prerequisites before execution."
                )

        else:
            # Generalize from success
            factors = outcome.get("factors", [])
            for factor in factors:
                generalizations.append(
                    f"Success factor: {factor} — apply this in similar contexts."
                )

            # Generalize procedure
            if experience.actions:
                generalizations.append(
                    f"Procedure for {experience.task[:50]}: "
                    f"{'; '.join(experience.actions[:3])}"
                )

        # Generalize from patterns
        for pattern in patterns:
            if pattern["pattern"] == "multiple_errors":
                generalizations.append(
                    "Multiple errors suggest systematic issues — break task into smaller steps."
                )
            elif pattern["pattern"] == "retry_success":
                generalizations.append(
                    "Persistence after initial failure can lead to success — don't give up after first error."
                )

        return generalizations

    def _verify(self, experience: Experience, facts: list[dict], generalizations: list[str]) -> dict:
        """Stage 8: VERIFY — check if learning is trustworthy."""
        verification = {
            "facts_verified": len(facts) > 0,
            "generalizations_supported": len(generalizations) > 0,
            "evidence_strength": "medium" if experience.success else "weak",
            "needs_more_evidence": len(facts) < 2,
        }

        # Single experience = weak evidence for generalization
        if len(generalizations) > 0:
            verification["generalization_confidence"] = 0.4
        else:
            verification["generalization_confidence"] = 0.0

        return verification

    def _connect(self, experience: Experience, facts: list[dict], generalizations: list[str]) -> list[dict]:
        """Stage 9: CONNECT — link new knowledge to existing knowledge."""
        connections = []

        # Connect facts to existing concepts
        for fact in facts:
            existing = self.db.fetch_one(
                "SELECT id FROM concepts WHERE name = ?",
                (fact["concept"],),
            )
            if existing:
                connections.append({
                    "type": "concept_connection",
                    "concept": fact["concept"],
                    "status": "connected",
                })
            else:
                connections.append({
                    "type": "new_concept",
                    "concept": fact["concept"],
                    "status": "created",
                })

        return connections

    def _create_or_update_skill(self, experience: Experience, outcome: dict) -> Optional[dict]:
        """Stage 10: CREATE/UPDATE SKILL — extract reusable procedure."""
        if not experience.actions:
            return None

        skill_name = self._derive_skill_name(experience)
        if not skill_name:
            return None

        # Check if skill already exists
        existing = self.db.fetch_one(
            "SELECT id, skill_id, confidence, experience_count FROM learned_skills WHERE name = ?",
            (skill_name,),
        )

        procedure = json.dumps(experience.actions)
        failure_conditions = json.dumps(experience.errors)
        recovery = json.dumps([outcome.get("correction", "")]) if outcome["outcome"] == "failure" else "[]"

        if existing:
            # existing = (id, skill_id, confidence, experience_count)
            new_count = (existing[3] or 0) + 1
            new_confidence = min(0.95, (existing[2] or 0.5) + 0.05) if outcome["outcome"] == "success" else max(0.1, (existing[2] or 0.5) - 0.1)
            self.db.execute(
                """UPDATE learned_skills
                   SET experience_count = ?, confidence = ?, last_used = ?,
                       failure_conditions = ?, recovery_strategies = ?, version = version + 1
                   WHERE id = ?""",
                (new_count, new_confidence, time.time(), failure_conditions, recovery, existing[0]),
            )
            return {"name": skill_name, "action": "updated", "confidence": new_confidence}
        else:
            # Create new skill
            import uuid
            skill_id = str(uuid.uuid4())[:12]
            self.db.execute(
                """INSERT INTO learned_skills
                   (skill_id, name, description, purpose, requirements, inputs, outputs,
                    preconditions, procedure, failure_conditions, recovery_strategies,
                    dependencies, confidence, success_rate, experience_count, last_used,
                    related_concepts, version, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (
                    skill_id, skill_name,
                    f"Learned from experience: {experience.task[:100]}",
                    experience.goal[:200] if experience.goal else "",
                    "[]", "[]", "[]", "[]",
                    procedure, failure_conditions, recovery,
                    "[]",
                    0.6 if outcome["outcome"] == "success" else 0.3,
                    1.0 if outcome["outcome"] == "success" else 0.0,
                    1, time.time(),
                    json.dumps(experience.lessons[:5]),
                    time.time(), time.time(),
                ),
            )
            return {"name": skill_name, "action": "created", "skill_id": skill_id}

    def _reflect(self, experience: Experience, outcome: dict, generalizations: list[str]) -> dict:
        """Stage 11: REFLECT — meta-cognitive analysis of the learning."""
        reflection = {
            "what_learned": generalizations[:3],
            "what_failed": experience.errors[:3] if not experience.success else [],
            "what_worked": experience.actions[:3] if experience.success else [],
            "missing_knowledge": [],
            "improvements": [],
        }

        if not experience.success:
            reflection["improvements"].append(
                f"Need to handle {outcome.get('root_cause', 'unknown error')} better."
            )

        if experience.success and experience.duration > 10:
            reflection["improvements"].append(
                "Task succeeded but was slow — optimize for speed."
            )

        return reflection

    def _update_confidence(self, experience: Experience, outcome: dict) -> float:
        """Stage 12: CONFIDENCE UPDATE — adjust confidence based on outcome."""
        if outcome["outcome"] == "success":
            return 0.05  # small positive boost
        else:
            return -0.10  # larger negative impact for failures

    def _store_knowledge(self, facts: list[dict], generalizations: list[str], experience: Experience):
        """Stage 13: STORE — persist learned knowledge and create graph concepts."""
        # Lazy-init knowledge graph (avoids circular import at module level)
        _knowledge_graph = None
        try:
            from genesis_ai.knowledge.graph.engine import KnowledgeGraph
            _knowledge_graph = KnowledgeGraph(self.db)
        except Exception:
            pass

        for fact in facts:
            self.db.execute(
                """INSERT INTO learned_knowledge
                   (concept, claim, source, evidence, confidence, created_at, status, experience_ids)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    fact["concept"],
                    fact["claim"],
                    fact.get("source", "experience"),
                    json.dumps([experience.experience_id]),
                    fact.get("confidence", 0.5),
                    time.time(),
                    "UNCERTAIN" if not experience.success else "PROBABLE",
                    json.dumps([experience.experience_id]),
                ),
            )

            # Auto-create concept node in knowledge graph
            if _knowledge_graph and fact.get("concept"):
                try:
                    _knowledge_graph.add_concept(
                        name=fact["concept"],
                        concept_type=fact.get("source", "learned"),
                        properties={
                            "description": fact["claim"][:200],
                            "confidence": fact.get("confidence", 0.5),
                        },
                    )
                except Exception:
                    pass  # graph creation is best-effort

        for gen in generalizations:
            self.db.execute(
                """INSERT INTO learned_generalizations
                   (pattern, description, conditions, evidence, confidence, source_experiences, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    gen[:100],
                    gen,
                    "[]",
                    json.dumps([experience.experience_id]),
                    0.4,  # start low, increase with reuse
                    json.dumps([experience.experience_id]),
                    time.time(),
                ),
            )

    def _test_reuse(self, generalizations: list[str], experience: Experience):
        """Stage 14: TEST REUSE — check if generalization applies to similar tasks."""
        # Find similar experiences and check if generalization would help
        similar = self.experience_memory.find_similar(experience.task, limit=3)
        for sim in similar:
            if sim.experience_id != experience.experience_id:
                # Check if our generalization would have predicted the outcome
                for gen in generalizations:
                    if any(word in sim.task.lower() for word in gen.lower().split()[:3]):
                        # Mark as potentially reusable
                        self.db.execute(
                            "UPDATE learned_generalizations SET usage_count = usage_count + 1 WHERE pattern = ?",
                            (gen[:100],),
                        )

    # ── Helper Methods ────────────────────────────────────────────────

    def _classify_task_type(self, experience: Experience) -> str:
        """Classify the task type from experience."""
        task_lower = experience.task.lower()
        if any(w in task_lower for w in ["code", "program", "function", "script"]):
            return "coding"
        elif any(w in task_lower for w in ["debug", "fix", "error", "bug"]):
            return "debugging"
        elif any(w in task_lower for w in ["research", "find", "search", "learn"]):
            return "research"
        elif any(w in task_lower for w in ["create", "build", "make", "design"]):
            return "creation"
        return "general"

    def _extract_domain(self, experience: Experience) -> str:
        """Extract the domain from the experience."""
        task_lower = experience.task.lower()
        if any(w in task_lower for w in ["python", "javascript", "java", "code"]):
            return "programming"
        elif any(w in task_lower for w in ["server", "api", "http", "network"]):
            return "systems"
        elif any(w in task_lower for w in ["data", "database", "sql", "query"]):
            return "data"
        return "general"

    def _assess_complexity(self, experience: Experience) -> str:
        """Assess task complexity."""
        if experience.duration > 30 or len(experience.actions) > 5:
            return "complex"
        elif experience.duration > 10 or len(experience.actions) > 3:
            return "moderate"
        return "simple"

    def _extract_key_concepts(self, experience: Experience) -> list[str]:
        """Extract key concepts from the experience."""
        concepts = set()
        # From task
        for word in experience.task.lower().split():
            if len(word) > 3 and word not in self.experience_memory.STOPWORDS:
                concepts.add(word)
        # From goal
        if experience.goal:
            for word in experience.goal.lower().split():
                if len(word) > 3 and word not in self.experience_memory.STOPWORDS:
                    concepts.add(word)
        return list(concepts)[:10]

    def _categorize_failures(self, experience: Experience) -> list[str]:
        """Categorize failure types."""
        categories = []
        for error in experience.errors:
            error_lower = error.lower()
            if any(w in error_lower for w in ["not found", "missing", "no such"]):
                categories.append("missing_resource")
            elif any(w in error_lower for w in ["permission", "denied", "forbidden"]):
                categories.append("permission_error")
            elif any(w in error_lower for w in ["timeout", "timed out", "slow"]):
                categories.append("timeout")
            elif any(w in error_lower for w in ["syntax", "invalid", "parse"]):
                categories.append("syntax_error")
            elif any(w in error_lower for w in ["connection", "network", "refused"]):
                categories.append("connection_error")
            else:
                categories.append("unknown_error")
        return list(set(categories))

    def _find_root_cause(self, experience: Experience) -> str:
        """Find the root cause of failure."""
        if not experience.errors:
            return "unknown"
        # Simple heuristic: most frequent error category
        categories = self._categorize_failures(experience)
        if categories:
            return categories[0]
        return "unknown"

    def _suggest_correction(self, experience: Experience) -> str:
        """Suggest a correction based on failure."""
        root_cause = self._find_root_cause(experience)
        corrections = {
            "missing_resource": "Verify all required resources exist before execution.",
            "permission_error": "Check permissions and access rights.",
            "timeout": "Increase timeout or optimize the operation.",
            "syntax_error": "Validate input syntax before processing.",
            "connection_error": "Verify network connectivity and service availability.",
            "unknown_error": "Investigate error details and check logs.",
        }
        return corrections.get(root_cause, "Investigate the specific error.")

    def _identify_success_factors(self, experience: Experience) -> list[str]:
        """Identify what made the task successful."""
        factors = []
        if experience.actions:
            factors.append(f"Used {len(experience.actions)} structured actions")
        if experience.tools_used:
            factors.append(f"Leveraged tools: {', '.join(experience.tools_used)}")
        if experience.duration < 5:
            factors.append("Completed efficiently")
        if not experience.errors:
            factors.append("No errors encountered")
        return factors

    def _derive_skill_name(self, experience: Experience) -> str:
        """Derive a skill name from the experience."""
        task_lower = experience.task.lower()
        if "debug" in task_lower or "fix" in task_lower:
            return "debug_application"
        elif "server" in task_lower or "api" in task_lower:
            return "build_server"
        elif "test" in task_lower:
            return "write_tests"
        elif "code" in task_lower or "program" in task_lower:
            return "write_code"
        elif "research" in task_lower:
            return "research_topic"
        return f"task_{experience.experience_id[:8]}"

    def _failure_category_to_generalization(self, category: str, experience: Experience) -> Optional[str]:
        """Convert a failure category into a reusable generalization."""
        generalizations = {
            "missing_resource": (
                f"Missing resource detected: Always verify prerequisites exist before execution. "
                f"Example from '{experience.task[:50]}'."
            ),
            "permission_error": (
                f"Permission issue: Check access rights and permissions before attempting operations. "
                f"Example from '{experience.task[:50]}'."
            ),
            "timeout": (
                f"Timeout occurred: Increase timeouts or optimize operations for better performance. "
                f"Example from '{experience.task[:50]}'."
            ),
            "syntax_error": (
                f"Syntax/parse error: Validate input format and syntax before processing. "
                f"Example from '{experience.task[:50]}'."
            ),
            "connection_error": (
                f"Connection issue: Verify network connectivity and service availability. "
                f"Example from '{experience.task[:50]}'."
            ),
            "unknown_error": (
                f"Unknown error encountered: Investigate error details, check logs, and add diagnostic logging. "
                f"Example from '{experience.task[:50]}'."
            ),
        }
        return generalizations.get(category)

    def get_stats(self) -> dict:
        """Get learning pipeline statistics."""
        knowledge = self.db.fetch_one("SELECT COUNT(*) FROM learned_knowledge")
        skills = self.db.fetch_one("SELECT COUNT(*) FROM learned_skills")
        generalizations = self.db.fetch_one("SELECT COUNT(*) FROM learned_generalizations")
        verified = self.db.fetch_one(
            "SELECT COUNT(*) FROM learned_knowledge WHERE status = 'VERIFIED'"
        )
        uncertain = self.db.fetch_one(
            "SELECT COUNT(*) FROM learned_knowledge WHERE status = 'UNCERTAIN'"
        )

        return {
            "knowledge_items": knowledge[0] if knowledge else 0,
            "skills": skills[0] if skills else 0,
            "generalizations": generalizations[0] if generalizations else 0,
            "verified_knowledge": verified[0] if verified else 0,
            "uncertain_knowledge": uncertain[0] if uncertain else 0,
            "experience_stats": self.experience_memory.get_stats(),
        }
