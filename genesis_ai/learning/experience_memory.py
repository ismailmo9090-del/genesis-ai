"""Experience Memory — structured storage for learning experiences.

Each experience is a rich record of a task, its context, actions, outcomes,
and lessons. Experiences are historical evidence, NOT the primary answer database.

The memory supports:
- Structured experience ingestion
- Similarity search (keyword-based)
- Lesson extraction
- Confidence tracking
- Experience → Knowledge → Skill pipeline
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional

from genesis_ai.database.db import DatabaseManager


@dataclass
class Experience:
    """A single learning experience — the atomic unit of learning."""

    experience_id: str = ""
    task: str = ""
    goal: str = ""
    context: dict = field(default_factory=dict)
    observations: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    attempts: list[dict] = field(default_factory=list)
    result: dict = field(default_factory=dict)
    success: bool = False
    evidence: list[dict] = field(default_factory=list)
    reflection: str = ""
    lessons: list[str] = field(default_factory=list)
    generalizations: list[str] = field(default_factory=list)
    related_concepts: list[str] = field(default_factory=list)
    related_skills: list[str] = field(default_factory=list)
    confidence: float = 0.5
    difficulty: float = 0.5
    duration: float = 0.0
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.experience_id:
            self.experience_id = str(uuid.uuid4())[:12]


class ExperienceMemory:
    """Structured experience memory with ingestion, search, and pipeline support."""

    STOPWORDS = frozenset({
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "can", "could", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "under", "again",
        "further", "then", "once", "here", "there", "when", "where", "why",
        "how", "all", "each", "every", "both", "few", "more", "most", "other",
        "some", "such", "no", "nor", "not", "only", "own", "same", "so",
        "than", "too", "very", "just", "because", "but", "and", "or", "if",
        "while", "about", "against", "that", "this", "these", "those",
    })

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._ensure_tables()

    def _ensure_tables(self):
        """Create the experience_memory table with full structured fields."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS experience_memory (
                experience_id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                goal TEXT DEFAULT '',
                context TEXT DEFAULT '{}',
                observations TEXT DEFAULT '[]',
                actions TEXT DEFAULT '[]',
                tools_used TEXT DEFAULT '[]',
                errors TEXT DEFAULT '[]',
                attempts TEXT DEFAULT '[]',
                result TEXT DEFAULT '{}',
                success INTEGER DEFAULT 0,
                evidence TEXT DEFAULT '[]',
                reflection TEXT DEFAULT '',
                lessons TEXT DEFAULT '[]',
                generalizations TEXT DEFAULT '[]',
                related_concepts TEXT DEFAULT '[]',
                related_skills TEXT DEFAULT '[]',
                confidence REAL DEFAULT 0.5,
                difficulty REAL DEFAULT 0.5,
                duration REAL DEFAULT 0.0,
                timestamp REAL NOT NULL,
                metadata TEXT DEFAULT '{}'
            )
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_exp_mem_timestamp
            ON experience_memory(timestamp)
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_exp_mem_success
            ON experience_memory(success)
        """)

    def ingest(self, experience: Experience) -> str:
        """Ingest a new experience into memory.

        This is the primary entry point for learning. The experience
        is stored as-is; post-processing (generalization, skill creation)
        happens in the learning pipeline.
        """
        if not experience.experience_id:
            experience.experience_id = str(uuid.uuid4())[:12]

        self.db.execute(
            """INSERT OR REPLACE INTO experience_memory
               (experience_id, task, goal, context, observations, actions,
                tools_used, errors, attempts, result, success, evidence,
                reflection, lessons, generalizations, related_concepts,
                related_skills, confidence, difficulty, duration, timestamp, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                experience.experience_id,
                experience.task,
                experience.goal,
                json.dumps(experience.context),
                json.dumps(experience.observations),
                json.dumps(experience.actions),
                json.dumps(experience.tools_used),
                json.dumps(experience.errors),
                json.dumps(experience.attempts),
                json.dumps(experience.result),
                1 if experience.success else 0,
                json.dumps(experience.evidence),
                experience.reflection,
                json.dumps(experience.lessons),
                json.dumps(experience.generalizations),
                json.dumps(experience.related_concepts),
                json.dumps(experience.related_skills),
                experience.confidence,
                experience.difficulty,
                experience.duration,
                experience.timestamp,
                json.dumps(experience.metadata),
            ),
        )
        return experience.experience_id

    def get(self, experience_id: str) -> Optional[Experience]:
        """Retrieve an experience by ID."""
        row = self.db.fetch_one(
            "SELECT * FROM experience_memory WHERE experience_id = ?",
            (experience_id,),
        )
        if not row:
            return None
        return self._row_to_experience(row)

    def find_similar(self, task_description: str, limit: int = 5) -> list[Experience]:
        """Find experiences similar to the given task using keyword matching."""
        query_tokens = self._tokenize(task_description)
        if not query_tokens:
            return []

        rows = self.db.fetch_all(
            "SELECT * FROM experience_memory ORDER BY timestamp DESC LIMIT 500"
        )
        if not rows:
            return []

        scored = []
        for row in rows:
            exp = self._row_to_experience(row)
            doc_text = f"{exp.task} {exp.goal} {exp.reflection}"
            doc_tokens = self._tokenize(doc_text)
            if not doc_tokens:
                continue
            intersection = query_tokens & doc_tokens
            if intersection:
                similarity = len(intersection) / max(len(query_tokens), len(doc_tokens))
                scored.append((similarity, exp))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored[:limit]]

    def get_successful(self, limit: int = 50) -> list[Experience]:
        """Get successful experiences for generalization."""
        rows = self.db.fetch_all(
            "SELECT * FROM experience_memory WHERE success = 1 ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_experience(r) for r in rows]

    def get_failed(self, limit: int = 50) -> list[Experience]:
        """Get failed experiences for failure learning."""
        rows = self.db.fetch_all(
            "SELECT * FROM experience_memory WHERE success = 0 ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_experience(r) for r in rows]

    def get_recent(self, limit: int = 20) -> list[Experience]:
        """Get most recent experiences."""
        rows = self.db.fetch_all(
            "SELECT * FROM experience_memory ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_experience(r) for r in rows]

    def get_by_domain(self, domain: str, limit: int = 20) -> list[Experience]:
        """Get experiences related to a domain/topic."""
        rows = self.db.fetch_all(
            "SELECT * FROM experience_memory WHERE task LIKE ? OR goal LIKE ? ORDER BY timestamp DESC LIMIT ?",
            (f"%{domain}%", f"%{domain}%", limit),
        )
        return [self._row_to_experience(r) for r in rows]

    def update_lessons(self, experience_id: str, lessons: list[str], generalizations: list[str] = None):
        """Update lessons and generalizations for an experience."""
        exp = self.get(experience_id)
        if not exp:
            return
        exp.lessons = lessons
        if generalizations:
            exp.generalizations = generalizations
        self.db.execute(
            "UPDATE experience_memory SET lessons = ?, generalizations = ? WHERE experience_id = ?",
            (json.dumps(lessons), json.dumps(generalizations or []), experience_id),
        )

    def update_confidence(self, experience_id: str, confidence: float):
        """Update confidence for an experience."""
        self.db.execute(
            "UPDATE experience_memory SET confidence = ? WHERE experience_id = ?",
            (max(0.0, min(1.0, confidence)), experience_id),
        )

    def get_stats(self) -> dict:
        """Get aggregate statistics."""
        total = self.db.fetch_one("SELECT COUNT(*) FROM experience_memory")
        successful = self.db.fetch_one("SELECT COUNT(*) FROM experience_memory WHERE success = 1")
        failed = self.db.fetch_one("SELECT COUNT(*) FROM experience_memory WHERE success = 0")
        avg_conf = self.db.fetch_one("SELECT AVG(confidence) FROM experience_memory")
        avg_diff = self.db.fetch_one("SELECT AVG(difficulty) FROM experience_memory")

        return {
            "total": total[0] if total else 0,
            "successful": successful[0] if successful else 0,
            "failed": failed[0] if failed else 0,
            "success_rate": (successful[0] / total[0]) if total and total[0] > 0 else 0.0,
            "avg_confidence": round(avg_conf[0], 3) if avg_conf and avg_conf[0] else 0.5,
            "avg_difficulty": round(avg_diff[0], 3) if avg_diff and avg_diff[0] else 0.5,
        }

    def _tokenize(self, text: str) -> set:
        """Tokenize text into lowercase words, removing stopwords."""
        words = set(re.findall(r'\b[a-z0-9]+\b', text.lower()))
        return words - self.STOPWORDS

    def _row_to_experience(self, row) -> Experience:
        """Convert a database row to an Experience object."""
        return Experience(
            experience_id=row[0],
            task=row[1],
            goal=row[2],
            context=json.loads(row[3]) if row[3] else {},
            observations=json.loads(row[4]) if row[4] else [],
            actions=json.loads(row[5]) if row[5] else [],
            tools_used=json.loads(row[6]) if row[6] else [],
            errors=json.loads(row[7]) if row[7] else [],
            attempts=json.loads(row[8]) if row[8] else [],
            result=json.loads(row[9]) if row[9] else {},
            success=bool(row[10]),
            evidence=json.loads(row[11]) if row[11] else [],
            reflection=row[12] or "",
            lessons=json.loads(row[13]) if row[13] else [],
            generalizations=json.loads(row[14]) if row[14] else [],
            related_concepts=json.loads(row[15]) if row[15] else [],
            related_skills=json.loads(row[16]) if row[16] else [],
            confidence=row[17] if row[17] is not None else 0.5,
            difficulty=row[18] if row[18] is not None else 0.5,
            duration=row[19] if row[19] is not None else 0.0,
            timestamp=row[20] if row[20] is not None else time.time(),
            metadata=json.loads(row[21]) if row[21] else {},
        )
