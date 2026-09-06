"""Tests for Knowledge Evolution — versioning, contradiction detection, freshness."""

import time
import unittest

from genesis_ai.database.db import DatabaseManager
from genesis_ai.learning.evolution import KnowledgeEvolution, KnowledgeStatus, ContradictionType


class TestKnowledgeEvolution(unittest.TestCase):
    """Test the Knowledge Evolution system."""

    def setUp(self):
        self.db = DatabaseManager(":memory:")
        self.evolution = KnowledgeEvolution(self.db)
        # Create a base knowledge table entry for testing
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS learned_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concept TEXT NOT NULL,
                claim TEXT NOT NULL,
                status TEXT DEFAULT 'UNCERTAIN',
                confidence REAL DEFAULT 0.5,
                last_verified REAL,
                created_at REAL NOT NULL
            )
        """)
        self.db.execute(
            "INSERT INTO learned_knowledge (concept, claim, status, confidence, created_at) VALUES (?, ?, ?, ?, ?)",
            ("python", "Python is a programming language", "UNCERTAIN", 0.6, time.time()),
        )

    def test_create_version(self):
        """Creating a version stores it correctly."""
        version = self.evolution.create_version(
            knowledge_id=1,
            claim="Python is a programming language",
            confidence=0.7,
            status="UNCERTAIN",
        )
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.knowledge_id, 1)

    def test_create_multiple_versions(self):
        """Multiple versions are numbered correctly."""
        v1 = self.evolution.create_version(1, "Python is a language", confidence=0.5)
        v2 = self.evolution.create_version(1, "Python is a programming language", confidence=0.7)
        v3 = self.evolution.create_version(1, "Python is a high-level language", confidence=0.8)
        self.assertEqual(v1.version_number, 1)
        self.assertEqual(v2.version_number, 2)
        self.assertEqual(v3.version_number, 3)

    def test_supersede(self):
        """Superseding marks old knowledge correctly."""
        self.db.execute(
            "INSERT INTO learned_knowledge (concept, claim, status, confidence, created_at) VALUES (?, ?, ?, ?, ?)",
            ("python", "Python is slow", "UNCERTAIN", 0.4, time.time()),
        )
        self.evolution.supersede(old_knowledge_id=1, new_knowledge_id=2)
        row = self.db.fetch_one("SELECT status FROM learned_knowledge WHERE id = 1")
        self.assertEqual(row[0], "SUPERSEDED")

    def test_detect_contradiction_direct(self):
        """Direct contradictions are detected."""
        # Create knowledge that contradicts the existing one
        self.db.execute(
            "INSERT INTO learned_knowledge (concept, claim, status, confidence, created_at) VALUES (?, ?, ?, ?, ?)",
            ("python", "Python is not a programming language", "UNCERTAIN", 0.5, time.time()),
        )
        contradictions = self.evolution.detect_contradictions(
            knowledge_id=2,
            claim="Python is not a programming language",
        )
        # Should detect contradiction (same words, different negation)
        self.assertGreater(len(contradictions), 0)
        self.assertEqual(contradictions[0].contradiction_type, ContradictionType.DIRECT.value)

    def test_no_contradiction_unrelated(self):
        """Unrelated knowledge doesn't trigger contradictions."""
        contradictions = self.evolution.detect_contradictions(
            knowledge_id=1,
            claim="The weather is nice today",
        )
        self.assertEqual(len(contradictions), 0)

    def test_resolve_contradiction(self):
        """Contradictions can be resolved."""
        self.db.execute(
            "INSERT INTO learned_knowledge (concept, claim, status, confidence, created_at) VALUES (?, ?, ?, ?, ?)",
            ("python", "Python is not a programming language", "UNCERTAIN", 0.4, time.time()),
        )
        contradictions = self.evolution.detect_contradictions(
            knowledge_id=2,
            claim="Python is not a programming language",
        )
        if contradictions:
            # Get the actual contradiction row ID
            row = self.db.fetch_one(
                "SELECT id FROM knowledge_contradictions WHERE knowledge_a_id = ? OR knowledge_b_id = ?",
                (2, 2),
            )
            if row:
                self.evolution.resolve_contradiction(
                    row[0],
                    resolution="Verified: Python IS a programming language",
                    winner_id=1,
                )
                resolved = self.evolution.get_contradictions(resolved=True)
                self.assertGreater(len(resolved), 0)

    def test_use_knowledge_increases_freshness(self):
        """Using knowledge increases its freshness."""
        self.evolution.use_knowledge(1)
        freshness = self.evolution.get_freshness(1)
        self.assertGreater(freshness["use_count"], 0)
        self.assertGreater(freshness["freshness"], 0)

    def test_use_knowledge_promotes_status(self):
        """Repeated use promotes uncertain knowledge."""
        # Use 3 times
        for _ in range(3):
            self.evolution.use_knowledge(1)
        row = self.db.fetch_one("SELECT status FROM learned_knowledge WHERE id = 1")
        self.assertEqual(row[0], "VERIFIED")

    def test_verify_knowledge(self):
        """Manual verification sets status to VERIFIED."""
        self.evolution.verify_knowledge(1)
        row = self.db.fetch_one("SELECT status FROM learned_knowledge WHERE id = 1")
        self.assertEqual(row[0], "VERIFIED")
        freshness = self.evolution.get_freshness(1)
        self.assertEqual(freshness["freshness"], 1.0)

    def test_decay_stale_knowledge(self):
        """Stale knowledge loses freshness."""
        # Set last_used to 60 days ago
        sixty_days_ago = time.time() - (60 * 86400)
        self.db.execute(
            "INSERT INTO knowledge_freshness (knowledge_id, last_verified, last_used, use_count, freshness) VALUES (?, ?, ?, 0, 1.0)",
            (1, sixty_days_ago, sixty_days_ago),
        )
        self.evolution.decay_stale_knowledge(max_age_days=30)
        freshness = self.evolution.get_freshness(1)
        self.assertLess(freshness["freshness"], 1.0)

    def test_get_knowledge_versions(self):
        """Versions are retrieved correctly."""
        self.evolution.create_version(1, "v1 claim", confidence=0.5)
        self.evolution.create_version(1, "v2 claim", confidence=0.7)
        versions = self.evolution.get_knowledge_versions(1)
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0].version_number, 1)
        self.assertEqual(versions[1].version_number, 2)

    def test_get_contradictions(self):
        """Contradictions are listed correctly."""
        self.db.execute(
            "INSERT INTO learned_knowledge (concept, claim, status, confidence, created_at) VALUES (?, ?, ?, ?, ?)",
            ("python", "Python is not a programming language", "UNCERTAIN", 0.4, time.time()),
        )
        self.evolution.detect_contradictions(2, "Python is not a programming language")
        contradictions = self.evolution.get_contradictions()
        self.assertGreater(len(contradictions), 0)

    def test_evolution_stats(self):
        """Stats return correct counts."""
        self.evolution.create_version(1, "test claim", confidence=0.5)
        stats = self.evolution.get_evolution_stats()
        self.assertEqual(stats["total_knowledge"], 1)
        self.assertEqual(stats["total_versions"], 1)

    def test_freshness_initial(self):
        """New knowledge has freshness tracking."""
        self.evolution.create_version(1, "test", confidence=0.5)
        freshness = self.evolution.get_freshness(1)
        self.assertEqual(freshness["freshness"], 1.0)
        self.assertEqual(freshness["use_count"], 0)


if __name__ == "__main__":
    unittest.main()
