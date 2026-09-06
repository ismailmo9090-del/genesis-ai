"""Knowledge Evolution — versioning, contradiction detection, freshness tracking.

Manages the lifecycle of learned knowledge:
- Versioning: knowledge evolves over time
- Contradiction detection: flags conflicting claims
- Freshness: tracks when knowledge was last verified
- Promotion: uncertain knowledge becomes verified through reuse
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from genesis_ai.database.db import DatabaseManager

logger = logging.getLogger(__name__)


class KnowledgeStatus(Enum):
    UNCERTAIN = "uncertain"
    PROBABLE = "probable"
    VERIFIED = "verified"
    CONTRADICTED = "contradicted"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"


class ContradictionType(Enum):
    DIRECT = "direct"           # A says X, B says not-X
    PARTIAL = "partial"         # A says X always, B says X sometimes
    TEMPORAL = "temporal"       # A was true, B is true now (knowledge evolved)
    SCOPE = "scope"             # A applies in context C, B applies in context D


@dataclass
class KnowledgeVersion:
    """A version of a knowledge item."""
    version_id: str = ""
    knowledge_id: int = 0
    version_number: int = 1
    claim: str = ""
    confidence: float = 0.5
    status: str = "UNCERTAIN"
    evidence: list[str] = field(default_factory=list)
    source: str = ""
    created_at: float = 0.0
    superseded_by: Optional[int] = None


@dataclass
class Contradiction:
    """A detected contradiction between two knowledge items."""
    contradiction_id: str = ""
    knowledge_a_id: int = 0
    knowledge_b_id: int = 0
    claim_a: str = ""
    claim_b: str = ""
    contradiction_type: str = "direct"
    severity: float = 0.5
    resolved: bool = False
    resolution: str = ""
    detected_at: float = 0.0


class KnowledgeEvolution:
    """Manages knowledge lifecycle — versioning, contradictions, freshness.

    Knowledge is NOT static. It evolves:
    1. New knowledge starts as UNCERTAIN
    2. Reuse increases confidence → PROBABLE
    3. Multiple confirmations → VERIFIED
    4. Contradictions detected → CONTRADICTED
    5. Newer knowledge supersedes old → SUPERSEDED
    6. Unused knowledge decays → DEPRECATED
    """

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._ensure_tables()

    def _ensure_tables(self):
        """Create knowledge evolution tables."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                knowledge_id INTEGER NOT NULL,
                version_number INTEGER NOT NULL,
                claim TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                status TEXT DEFAULT 'UNCERTAIN',
                evidence TEXT DEFAULT '[]',
                source TEXT DEFAULT '',
                created_at REAL NOT NULL,
                superseded_by INTEGER
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_contradictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                knowledge_a_id INTEGER NOT NULL,
                knowledge_b_id INTEGER NOT NULL,
                claim_a TEXT NOT NULL,
                claim_b TEXT NOT NULL,
                contradiction_type TEXT DEFAULT 'direct',
                severity REAL DEFAULT 0.5,
                resolved BOOLEAN DEFAULT 0,
                resolution TEXT DEFAULT '',
                detected_at REAL NOT NULL
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_freshness (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                knowledge_id INTEGER UNIQUE NOT NULL,
                last_verified REAL,
                last_used REAL,
                use_count INTEGER DEFAULT 0,
                decay_rate REAL DEFAULT 0.01,
                freshness REAL DEFAULT 1.0
            )
        """)

    def create_version(
        self,
        knowledge_id: int,
        claim: str,
        confidence: float = 0.5,
        status: str = "UNCERTAIN",
        evidence: list[str] | None = None,
        source: str = "",
    ) -> KnowledgeVersion:
        """Create a new version of a knowledge item."""
        # Get current max version
        row = self.db.fetch_one(
            "SELECT MAX(version_number) FROM knowledge_versions WHERE knowledge_id = ?",
            (knowledge_id,),
        )
        next_version = (row[0] or 0) + 1

        version = KnowledgeVersion(
            knowledge_id=knowledge_id,
            version_number=next_version,
            claim=claim,
            confidence=confidence,
            status=status,
            evidence=evidence or [],
            source=source,
            created_at=time.time(),
        )

        self.db.execute(
            """INSERT INTO knowledge_versions
               (knowledge_id, version_number, claim, confidence, status, evidence, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                knowledge_id, version.version_number, claim, confidence,
                status, json.dumps(evidence or []), source, time.time(),
            ),
        )

        # Initialize freshness tracking
        self.db.execute(
            """INSERT OR IGNORE INTO knowledge_freshness
               (knowledge_id, last_verified, last_used, use_count, freshness)
               VALUES (?, ?, ?, 0, 1.0)""",
            (knowledge_id, time.time(), time.time()),
        )

        return version

    def supersede(self, old_knowledge_id: int, new_knowledge_id: int):
        """Mark old knowledge as superseded by new knowledge."""
        # Mark old as superseded
        self.db.execute(
            "UPDATE learned_knowledge SET status = 'SUPERSEDED' WHERE id = ?",
            (old_knowledge_id,),
        )
        # Update version
        self.db.execute(
            """UPDATE knowledge_versions
               SET superseded_by = ?
               WHERE knowledge_id = ? AND superseded_by IS NULL""",
            (new_knowledge_id, old_knowledge_id),
        )
        logger.info(
            "Knowledge %d superseded by %d", old_knowledge_id, new_knowledge_id
        )

    def detect_contradictions(
        self, knowledge_id: int, claim: str
    ) -> list[Contradiction]:
        """Check if new knowledge contradicts existing knowledge.

        Uses keyword overlap + negation detection for pure-Python contradiction finding.
        """
        contradictions = []

        # Get all existing knowledge
        existing = self.db.fetch_all(
            "SELECT id, claim, confidence, status FROM learned_knowledge WHERE id != ?",
            (knowledge_id,),
        )

        new_words = set(claim.lower().split())
        new_negations = self._detect_negations(claim)

        for row in existing:
            existing_id, existing_claim, existing_conf, existing_status = row
            existing_words = set(existing_claim.lower().split())
            existing_negations = self._detect_negations(existing_claim)

            # Calculate word overlap
            overlap = new_words & existing_words
            if len(overlap) < 3:
                continue  # Not enough overlap to be related

            # Check for negation difference (direct contradiction)
            new_has_neg = bool(new_negations)
            old_has_neg = bool(existing_negations)

            if new_has_neg != old_has_neg and len(overlap) >= 4:
                # Potential contradiction: same words, different negation
                severity = min(1.0, len(overlap) / max(len(new_words), len(existing_words)))
                contradiction = Contradiction(
                    knowledge_a_id=knowledge_id,
                    knowledge_b_id=existing_id,
                    claim_a=claim[:200],
                    claim_b=existing_claim[:200],
                    contradiction_type=ContradictionType.DIRECT.value,
                    severity=severity,
                    detected_at=time.time(),
                )
                contradictions.append(contradiction)

                # Store contradiction
                self.db.execute(
                    """INSERT INTO knowledge_contradictions
                       (knowledge_a_id, knowledge_b_id, claim_a, claim_b,
                        contradiction_type, severity, detected_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        knowledge_id, existing_id, claim[:200], existing_claim[:200],
                        ContradictionType.DIRECT.value, severity, time.time(),
                    ),
                )

            # Check for temporal contradiction (claim changed over time)
            elif len(overlap) >= 5 and abs(existing_conf - 0.5) > 0.2:
                severity = 0.3
                contradiction = Contradiction(
                    knowledge_a_id=knowledge_id,
                    knowledge_b_id=existing_id,
                    claim_a=claim[:200],
                    claim_b=existing_claim[:200],
                    contradiction_type=ContradictionType.TEMPORAL.value,
                    severity=severity,
                    detected_at=time.time(),
                )
                contradictions.append(contradiction)

                self.db.execute(
                    """INSERT INTO knowledge_contradictions
                       (knowledge_a_id, knowledge_b_id, claim_a, claim_b,
                        contradiction_type, severity, detected_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        knowledge_id, existing_id, claim[:200], existing_claim[:200],
                        ContradictionType.TEMPORAL.value, severity, time.time(),
                    ),
                )

        return contradictions

    def resolve_contradiction(
        self, contradiction_id: int, resolution: str, winner_id: Optional[int] = None
    ):
        """Resolve a contradiction."""
        self.db.execute(
            """UPDATE knowledge_contradictions
               SET resolved = 1, resolution = ?
               WHERE id = ?""",
            (resolution, contradiction_id),
        )

        # If a winner is specified, supersede the loser
        if winner_id:
            row = self.db.fetch_one(
                "SELECT knowledge_a_id, knowledge_b_id FROM knowledge_contradictions WHERE id = ?",
                (contradiction_id,),
            )
            if row:
                loser_id = row[1] if row[0] == winner_id else row[0]
                self.supersede(loser_id, winner_id)

    def use_knowledge(self, knowledge_id: int):
        """Record that knowledge was used (increases freshness)."""
        # Ensure freshness row exists
        existing = self.db.fetch_one(
            "SELECT id FROM knowledge_freshness WHERE knowledge_id = ?",
            (knowledge_id,),
        )
        if not existing:
            self.db.execute(
                """INSERT INTO knowledge_freshness
                   (knowledge_id, last_verified, last_used, use_count, freshness)
                   VALUES (?, ?, ?, 0, 1.0)""",
                (knowledge_id, time.time(), time.time()),
            )

        self.db.execute(
            """UPDATE knowledge_freshness
               SET last_used = ?, use_count = use_count + 1,
                   freshness = MIN(1.0, freshness + 0.1)
               WHERE knowledge_id = ?""",
            (time.time(), knowledge_id),
        )

        # Promote status based on usage
        row = self.db.fetch_one(
            "SELECT use_count, freshness FROM knowledge_freshness WHERE knowledge_id = ?",
            (knowledge_id,),
        )
        if row and row[0] >= 3:
            self.db.execute(
                "UPDATE learned_knowledge SET status = 'VERIFIED' WHERE id = ? AND status IN ('UNCERTAIN', 'PROBABLE')",
                (knowledge_id,),
            )
        elif row and row[0] >= 1:
            self.db.execute(
                "UPDATE learned_knowledge SET status = 'PROBABLE' WHERE id = ? AND status = 'UNCERTAIN'",
                (knowledge_id,),
            )

    def verify_knowledge(self, knowledge_id: int):
        """Manually verify knowledge (sets last_verified)."""
        # Ensure freshness row exists
        existing = self.db.fetch_one(
            "SELECT id FROM knowledge_freshness WHERE knowledge_id = ?",
            (knowledge_id,),
        )
        if not existing:
            self.db.execute(
                """INSERT INTO knowledge_freshness
                   (knowledge_id, last_verified, last_used, use_count, freshness)
                   VALUES (?, ?, ?, 0, 1.0)""",
                (knowledge_id, time.time(), time.time()),
            )
        else:
            self.db.execute(
                """UPDATE knowledge_freshness
                   SET last_verified = ?, freshness = 1.0
                   WHERE knowledge_id = ?""",
                (time.time(), knowledge_id),
            )
        self.db.execute(
            "UPDATE learned_knowledge SET status = 'VERIFIED', last_verified = ? WHERE id = ?",
            (time.time(), knowledge_id),
        )

    def decay_stale_knowledge(self, max_age_days: int = 30):
        """Apply decay to knowledge that hasn't been used recently.

        Stale knowledge loses freshness over time.
        """
        cutoff = time.time() - (max_age_days * 86400)
        self.db.execute(
            """UPDATE knowledge_freshness
               SET freshness = MAX(0.0, freshness - decay_rate)
               WHERE last_used < ? AND freshness > 0""",
            (cutoff,),
        )

        # Deprecate very old knowledge
        self.db.execute(
            """UPDATE learned_knowledge
               SET status = 'DEPRECATED'
               WHERE id IN (
                   SELECT knowledge_id FROM knowledge_freshness
                   WHERE freshness <= 0.1 AND use_count = 0
               ) AND status != 'VERIFIED'"""
        )

    def get_contradictions(self, resolved: bool = False) -> list[Contradiction]:
        """Get contradictions, optionally filtering by resolution status."""
        rows = self.db.fetch_all(
            """SELECT knowledge_a_id, knowledge_b_id, claim_a, claim_b,
                      contradiction_type, severity, resolved, resolution, detected_at
               FROM knowledge_contradictions WHERE resolved = ?
               ORDER BY detected_at DESC""",
            (int(resolved),),
        )
        return [
            Contradiction(
                knowledge_a_id=r[0], knowledge_b_id=r[1],
                claim_a=r[2], claim_b=r[3],
                contradiction_type=r[4], severity=r[5],
                resolved=bool(r[6]), resolution=r[7],
                detected_at=r[8],
            )
            for r in rows
        ]

    def get_knowledge_versions(self, knowledge_id: int) -> list[KnowledgeVersion]:
        """Get all versions of a knowledge item."""
        rows = self.db.fetch_all(
            """SELECT version_number, claim, confidence, status, evidence,
                      source, created_at, superseded_by
               FROM knowledge_versions WHERE knowledge_id = ?
               ORDER BY version_number""",
            (knowledge_id,),
        )
        return [
            KnowledgeVersion(
                knowledge_id=knowledge_id,
                version_number=r[0], claim=r[1], confidence=r[2],
                status=r[3], evidence=json.loads(r[4]) if r[4] else [],
                source=r[5], created_at=r[6],
                superseded_by=r[7],
            )
            for r in rows
        ]

    def get_freshness(self, knowledge_id: int) -> dict:
        """Get freshness info for a knowledge item."""
        row = self.db.fetch_one(
            """SELECT last_verified, last_used, use_count, decay_rate, freshness
               FROM knowledge_freshness WHERE knowledge_id = ?""",
            (knowledge_id,),
        )
        if row:
            return {
                "last_verified": row[0],
                "last_used": row[1],
                "use_count": row[2],
                "decay_rate": row[3],
                "freshness": row[4],
            }
        return {"freshness": 0.0, "use_count": 0}

    def get_evolution_stats(self) -> dict:
        """Get statistics about knowledge evolution."""
        total = self.db.fetch_one("SELECT COUNT(*) FROM learned_knowledge")
        versions = self.db.fetch_one("SELECT COUNT(*) FROM knowledge_versions")
        contradictions = self.db.fetch_one("SELECT COUNT(*) FROM knowledge_contradictions")
        unresolved = self.db.fetch_one(
            "SELECT COUNT(*) FROM knowledge_contradictions WHERE resolved = 0"
        )
        verified = self.db.fetch_one(
            "SELECT COUNT(*) FROM learned_knowledge WHERE status = 'VERIFIED'"
        )
        deprecated = self.db.fetch_one(
            "SELECT COUNT(*) FROM learned_knowledge WHERE status = 'DEPRECATED'"
        )
        avg_freshness = self.db.fetch_one(
            "SELECT AVG(freshness) FROM knowledge_freshness"
        )

        return {
            "total_knowledge": total[0] if total else 0,
            "total_versions": versions[0] if versions else 0,
            "total_contradictions": contradictions[0] if contradictions else 0,
            "unresolved_contradictions": unresolved[0] if unresolved else 0,
            "verified_knowledge": verified[0] if verified else 0,
            "deprecated_knowledge": deprecated[0] if deprecated else 0,
            "average_freshness": round(avg_freshness[0], 3) if avg_freshness and avg_freshness[0] else 0.0,
        }

    def _detect_negations(self, text: str) -> list[str]:
        """Detect negation words in text."""
        negation_words = {"not", "no", "never", "neither", "nobody", "nothing",
                          "nowhere", "nor", "cannot", "can't", "don't", "doesn't",
                          "didn't", "won't", "wouldn't", "shouldn't", "couldn't",
                          "isn't", "aren't", "wasn't", "weren't", "hasn't", "haven't",
                          "hadn't", "mustn't", "without", "lack", "lacking", "false"}
        words = set(text.lower().split())
        return list(words & negation_words)
