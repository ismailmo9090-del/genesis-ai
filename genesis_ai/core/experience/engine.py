"""Experience engine that records task outcomes and extracts lessons for future improvement."""

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from genesis_ai.database.db import DatabaseManager


@dataclass
class ExperienceRecord:
    """A single record of a completed task, its approach, and its outcome."""

    task_id: str
    task_description: str
    approach: str
    knowledge_used: List[str] = field(default_factory=list)
    research_used: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    solution_summary: str = ""
    result: str = "pending"  # success, partial, failure
    lessons: List[str] = field(default_factory=list)
    duration: float = 0.0
    timestamp: float = field(default_factory=time.time)


class ExperienceEngine:
    """Tracks task outcomes, finds similar past experiences, and extracts lessons learned.

    Uses keyword-based similarity matching to surface relevant past experiences
    when a new task arrives, enabling the system to learn from successes and failures.
    """

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
        """Create the experience_engine table with extended columns for the engine."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS experience_engine (
                task_id TEXT PRIMARY KEY,
                task_description TEXT NOT NULL,
                approach TEXT DEFAULT '',
                knowledge_used TEXT DEFAULT '[]',
                research_used TEXT DEFAULT '[]',
                errors TEXT DEFAULT '[]',
                solution_summary TEXT DEFAULT '',
                result TEXT DEFAULT 'pending',
                lessons TEXT DEFAULT '[]',
                duration REAL DEFAULT 0.0,
                timestamp REAL NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_exp_engine_result ON experience_engine(result)
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_exp_engine_timestamp ON experience_engine(timestamp DESC)
        """)

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into lowercase words, removing stopwords."""
        text = re.sub(r"[^\w\s]", " ", text.lower())
        return [t for t in text.split() if t not in self.STOPWORDS and len(t) > 1]

    def _similarity_score(self, query_tokens: List[str], doc_tokens: List[str]) -> float:
        """Compute Jaccard-style similarity between two token sets, weighted by overlap ratio."""
        if not query_tokens or not doc_tokens:
            return 0.0
        query_set = set(query_tokens)
        doc_set = set(doc_tokens)
        intersection = query_set & doc_set
        if not intersection:
            return 0.0
        # Jaccard coefficient
        union = query_set | doc_set
        jaccard = len(intersection) / len(union)
        # Overlap coefficient (penalize when query terms are missing from doc)
        coverage = len(intersection) / len(query_set)
        return 0.6 * jaccard + 0.4 * coverage

    def _row_to_record(self, row: tuple) -> ExperienceRecord:
        """Convert a database row tuple into an ExperienceRecord dataclass."""
        return ExperienceRecord(
            task_id=row[0],
            task_description=row[1],
            approach=row[2],
            knowledge_used=json.loads(row[3]) if row[3] else [],
            research_used=json.loads(row[4]) if row[4] else [],
            errors=json.loads(row[5]) if row[5] else [],
            solution_summary=row[6] or "",
            result=row[7] or "pending",
            lessons=json.loads(row[8]) if row[8] else [],
            duration=row[9] or 0.0,
            timestamp=row[10] or 0.0,
        )

    def create_experience(self, record: ExperienceRecord) -> str:
        """Persist a new experience record to the database.

        Args:
            record: The ExperienceRecord to store. If task_id is empty, a new UUID is generated.

        Returns:
            The task_id of the stored record.
        """
        if not record.task_id:
            record.task_id = str(uuid.uuid4())[:12]
        if record.timestamp == 0.0:
            record.timestamp = time.time()
        self.db.execute(
            """INSERT OR REPLACE INTO experience_engine
               (task_id, task_description, approach, knowledge_used, research_used,
                errors, solution_summary, result, lessons, duration, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.task_id,
                record.task_description,
                record.approach,
                json.dumps(record.knowledge_used),
                json.dumps(record.research_used),
                json.dumps(record.errors),
                record.solution_summary,
                record.result,
                json.dumps(record.lessons),
                record.duration,
                record.timestamp,
            ),
        )
        return record.task_id

    def get_experience(self, task_id: str) -> Optional[ExperienceRecord]:
        """Retrieve a single experience by its task_id.

        Args:
            task_id: The unique identifier of the experience.

        Returns:
            The ExperienceRecord if found, otherwise None.
        """
        row = self.db.fetch_one(
            "SELECT * FROM experience_engine WHERE task_id = ?", (task_id,)
        )
        if row:
            return self._row_to_record(row)
        return None

    def find_similar_experiences(
        self, task_description: str, limit: int = 5
    ) -> List[Dict]:
        """Find past experiences similar to the given task description using keyword matching.

        Computes a similarity score between the query and every stored experience,
        returning the top ``limit`` results ordered by relevance.

        Args:
            task_description: The new task description to match against.
            limit: Maximum number of results to return.

        Returns:
            List of dicts with experience data and a ``similarity`` score.
        """
        query_tokens = self._tokenize(task_description)
        if not query_tokens:
            return []

        rows = self.db.fetch_all(
            "SELECT * FROM experience_engine ORDER BY timestamp DESC"
        )
        if not rows:
            return []

        scored = []
        for row in rows:
            exp = self._row_to_record(row)
            # Combine task description and approach for matching
            doc_text = f"{exp.task_description} {exp.approach} {exp.solution_summary}"
            doc_tokens = self._tokenize(doc_text)
            score = self._similarity_score(query_tokens, doc_tokens)
            # Boost successful experiences slightly
            if exp.result == "success":
                score *= 1.1
            elif exp.result == "failure":
                score *= 0.9
            if score > 0.0:
                entry = {
                    "task_id": exp.task_id,
                    "task_description": exp.task_description,
                    "approach": exp.approach,
                    "result": exp.result,
                    "lessons": exp.lessons,
                    "solution_summary": exp.solution_summary,
                    "duration": exp.duration,
                    "similarity": round(score, 4),
                }
                scored.append(entry)

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:limit]

    def get_lessons_learned(self, domain: str = None) -> List[Dict]:
        """Extract lessons from successful experiences, optionally filtered by domain keyword.

        Only experiences marked as ``success`` are considered. Each lesson is returned
        as a separate entry with its parent experience metadata.

        Args:
            domain: Optional keyword to filter task descriptions (case-insensitive substring match).

        Returns:
            List of dicts, each containing a single lesson string and its source experience info.
        """
        if domain:
            rows = self.db.fetch_all(
                """SELECT * FROM experience_engine
                   WHERE result = 'success' AND task_description LIKE ?
                   ORDER BY timestamp DESC""",
                (f"%{domain}%",),
            )
        else:
            rows = self.db.fetch_all(
                """SELECT * FROM experience_engine
                   WHERE result = 'success'
                   ORDER BY timestamp DESC"""
            )

        lessons = []
        for row in rows:
            exp = self._row_to_record(row)
            for lesson in exp.lessons:
                if lesson:
                    lessons.append({
                        "lesson": lesson,
                        "task_id": exp.task_id,
                        "task_description": exp.task_description,
                        "approach": exp.approach,
                        "timestamp": exp.timestamp,
                    })
        return lessons

    def get_success_rate(self, task_type: str = None) -> float:
        """Calculate the success rate for experiences, optionally filtered by task_type keyword.

        Args:
            task_type: Optional keyword to filter task descriptions (case-insensitive substring match).

        Returns:
            Float between 0.0 and 1.0 representing the fraction of successful experiences.
            Returns 0.0 if no matching experiences exist.
        """
        if task_type:
            total_row = self.db.fetch_one(
                "SELECT COUNT(*) FROM experience_engine WHERE task_description LIKE ?",
                (f"%{task_type}%",),
            )
            success_row = self.db.fetch_one(
                "SELECT COUNT(*) FROM experience_engine WHERE task_description LIKE ? AND result = 'success'",
                (f"%{task_type}%",),
            )
        else:
            total_row = self.db.fetch_one(
                "SELECT COUNT(*) FROM experience_engine"
            )
            success_row = self.db.fetch_one(
                "SELECT COUNT(*) FROM experience_engine WHERE result = 'success'"
            )

        total = total_row[0] if total_row else 0
        successes = success_row[0] if success_row else 0
        if total == 0:
            return 0.0
        return round(successes / total, 4)

    def update_experience(self, task_id: str, updates: dict):
        """Update specific fields on an existing experience record.

        Allowed update keys: approach, knowledge_used, research_used, errors,
        solution_summary, result, lessons, duration.

        Args:
            task_id: The experience to update.
            updates: Dict of field names to new values.
        """
        allowed = {
            "approach", "knowledge_used", "research_used", "errors",
            "solution_summary", "result", "lessons", "duration",
        }
        fields = {}
        for k, v in updates.items():
            if k not in allowed:
                continue
            if k in ("knowledge_used", "research_used", "errors", "lessons"):
                fields[k] = json.dumps(v) if isinstance(v, list) else v
            else:
                fields[k] = v
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [task_id]
        self.db.execute(
            f"UPDATE experience_engine SET {set_clause} WHERE task_id = ?",
            tuple(values),
        )

    def get_recent_experiences(self, limit: int = 10) -> List[Dict]:
        """Return the most recent experiences.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of experience dicts ordered by timestamp descending.
        """
        rows = self.db.fetch_all(
            "SELECT * FROM experience_engine ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [
            {
                "task_id": r[0],
                "task_description": r[1],
                "approach": r[2],
                "result": r[7],
                "lessons": json.loads(r[8]) if r[8] else [],
                "duration": r[9],
                "timestamp": r[10],
            }
            for r in rows
        ]

    def delete_experience(self, task_id: str) -> bool:
        """Remove an experience record by task_id.

        Returns:
            True if a row was deleted, False otherwise.
        """
        self.db.execute(
            "DELETE FROM experience_engine WHERE task_id = ?", (task_id,)
        )
        return True

    def get_stats(self) -> Dict:
        """Return aggregate statistics about stored experiences.

        Includes total count, count by result, average duration, and overall success rate.
        """
        total_row = self.db.fetch_one("SELECT COUNT(*) FROM experience_engine")
        total = total_row[0] if total_row else 0

        by_result_rows = self.db.fetch_all(
            "SELECT result, COUNT(*) FROM experience_engine GROUP BY result"
        )
        by_result = {r[0]: r[1] for r in by_result_rows} if by_result_rows else {}

        avg_duration_row = self.db.fetch_one(
            "SELECT AVG(duration) FROM experience_engine"
        )
        avg_duration = round(avg_duration_row[0], 2) if avg_duration_row and avg_duration_row[0] else 0.0

        success_count = by_result.get("success", 0)
        success_rate = round(success_count / total, 4) if total > 0 else 0.0

        return {
            "total_experiences": total,
            "by_result": by_result,
            "average_duration": avg_duration,
            "success_rate": success_rate,
        }
