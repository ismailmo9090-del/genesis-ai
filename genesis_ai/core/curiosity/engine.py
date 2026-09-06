"""Curiosity engine for identifying knowledge gaps and autonomous learning."""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from genesis_ai.database.db import DatabaseManager
from genesis_ai.config.settings import (
    AUTONOMOUS_LEARNING_ENABLED,
    MAX_LEARNING_SESSIONS_PER_DAY,
    MAX_WEB_REQUESTS_PER_HOUR,
    CURIOUSITY_STRENGTH,
)


@dataclass
class KnowledgeGap:
    gap_type: str
    topic: str
    detail: str
    priority: float = 0.5
    suggestion: str = ""
    related_concepts: list[str] = field(default_factory=list)


@dataclass
class LearningTopic:
    topic: str
    priority: float
    reason: str
    estimated_difficulty: str = "medium"
    queue_id: Optional[int] = None


class CuriosityEngine:
    """Identifies knowledge gaps, suggests learning topics, and manages curiosity queue."""

    MAX_LEARNING_SESSIONS_PER_DAY = MAX_LEARNING_SESSIONS_PER_DAY
    MAX_WEB_REQUESTS_PER_HOUR = MAX_WEB_REQUESTS_PER_HOUR
    CURIOUSITY_STRENGTH = CURIOUSITY_STRENGTH

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.enabled = True
        self._web_requests_this_hour = 0
        self._hour_start = time.time()
        self._learning_sessions_today = 0
        self._day_start = time.time()

    def identify_gaps(self, knowledge_graph: dict = None) -> list[KnowledgeGap]:
        gaps = []
        concepts = self.db.list_concepts()
        for concept in concepts:
            rels = self.db.get_relationships_for_concept(concept["id"])
            if len(rels) < 2:
                gaps.append(
                    KnowledgeGap(
                        gap_type="isolated_concept",
                        topic=concept["name"],
                        detail=f"Concept '{concept['name']}' has only {len(rels)} relationships",
                        priority=0.6,
                        suggestion=f"Research more connections for '{concept['name']}'",
                    )
                )
            knowledge = self.db.get_knowledge_for_concept(concept["id"])
            if len(knowledge) == 0:
                gaps.append(
                    KnowledgeGap(
                        gap_type="no_knowledge_claims",
                        topic=concept["name"],
                        detail=f"Concept '{concept['name']}' has no knowledge claims",
                        priority=0.7,
                        suggestion=f"Learn about '{concept['name']}' to build knowledge claims",
                    )
                )
            unverified = [
                k for k in knowledge if k.get("verification_status") == "unverified"
            ]
            if len(unverified) > len(knowledge) * 0.5 and len(knowledge) > 0:
                gaps.append(
                    KnowledgeGap(
                        gap_type="low_verification",
                        topic=concept["name"],
                        detail=f"Concept '{concept['name']}' has {len(unverified)}/{len(knowledge)} unverified claims",
                        priority=0.5,
                        suggestion=f"Verify claims about '{concept['name']}'",
                    )
                )
        related_pairs = set()
        for concept in concepts:
            rels = self.db.get_relationships_for_concept(concept["id"])
            for rel in rels:
                target_id = (
                    rel["target_concept_id"]
                    if rel["source_concept_id"] == concept["id"]
                    else rel["source_concept_id"]
                )
                pair = tuple(sorted([concept["id"], target_id]))
                related_pairs.add(pair)
        all_concept_ids = [c["id"] for c in concepts]
        for i in range(len(all_concept_ids)):
            for j in range(i + 1, min(i + 5, len(all_concept_ids))):
                pair = tuple(sorted([all_concept_ids[i], all_concept_ids[j]]))
                if pair not in related_pairs:
                    c1 = next(c for c in concepts if c["id"] == all_concept_ids[i])
                    c2 = next(c for c in concepts if c["id"] == all_concept_ids[j])
                    if c1.get("domain") == c2.get("domain") and c1.get("domain"):
                        gaps.append(
                            KnowledgeGap(
                                gap_type="missing_relationship",
                                topic=f"{c1['name']} <-> {c2['name']}",
                                detail=f"Same domain '{c1['domain']}' concepts lack direct relationship",
                                priority=0.4,
                                suggestion=f"Investigate relationship between '{c1['name']}' and '{c2['name']}'",
                                related_concepts=[c1["name"], c2["name"]],
                            )
                        )
        gaps.sort(key=lambda g: g.priority, reverse=True)
        return gaps

    def suggest_learning_topics(
        self, gaps: list[KnowledgeGap], user_preferences: dict = None
    ) -> list[LearningTopic]:
        user_preferences = user_preferences or {}
        preferred_domains = user_preferences.get("preferred_domains", [])
        excluded_topics = user_preferences.get("excluded_topics", [])
        max_difficulty = user_preferences.get("max_difficulty", "hard")
        difficulty_order = {"easy": 0, "medium": 1, "hard": 2}
        topics = []
        for gap in gaps:
            if gap.topic in excluded_topics:
                continue
            adjusted_priority = gap.priority * self.CURIOSITY_STRENGTH
            if preferred_domains:
                topic_lower = gap.topic.lower()
                for domain in preferred_domains:
                    if domain.lower() in topic_lower:
                        adjusted_priority = min(1.0, adjusted_priority + 0.2)
                        break
            difficulty = "medium"
            if gap.gap_type == "isolated_concept":
                difficulty = "easy"
            elif gap.gap_type == "missing_relationship":
                difficulty = "hard"
            if difficulty_order.get(difficulty, 1) > difficulty_order.get(max_difficulty, 2):
                continue
            topics.append(
                LearningTopic(
                    topic=gap.topic,
                    priority=round(adjusted_priority, 4),
                    reason=gap.suggestion,
                    estimated_difficulty=difficulty,
                )
            )
        topics.sort(key=lambda t: t.priority, reverse=True)
        return topics

    def should_learn(self, user_preferences: dict = None, resource_limits: dict = None) -> bool:
        if not self.enabled:
            return False
        if not AUTONOMOUS_LEARNING_ENABLED:
            return False
        user_preferences = user_preferences or {}
        resource_limits = resource_limits or {}
        self._reset_counters()
        if self._learning_sessions_today >= self.MAX_LEARNING_SESSIONS_PER_DAY:
            return False
        max_hourly = resource_limits.get("max_web_requests_per_hour", self.MAX_WEB_REQUESTS_PER_HOUR)
        if self._web_requests_this_hour >= max_hourly:
            return False
        if user_preferences.get("autonomous_learning_disabled", False):
            return False
        return True

    def add_to_queue(self, topic: str, priority: float = 0.5, reason: str = "") -> int:
        queue_id = self.db.insert_curiosity(
            topic=topic,
            priority=priority,
            reason=reason,
        )
        return queue_id

    def process_queue(self, limit: int = 5) -> list[LearningTopic]:
        if not self.should_learn():
            return []
        pending = self.db.list_curiosity(status="pending", limit=limit)
        topics = []
        for item in pending:
            topics.append(
                LearningTopic(
                    topic=item["topic"],
                    priority=item["priority"],
                    reason=item.get("reason", ""),
                    queue_id=item["id"],
                )
            )
            self.db.process_curiosity(item["id"])
            self._learning_sessions_today += 1
        return topics

    def get_queue_status(self) -> dict:
        with self.db.get_conn() as conn:
            pending = conn.execute(
                "SELECT COUNT(*) as cnt FROM curiosity_queue WHERE status = 'pending'"
            ).fetchone()["cnt"]
            processed = conn.execute(
                "SELECT COUNT(*) as cnt FROM curiosity_queue WHERE status = 'processed'"
            ).fetchone()["cnt"]
            failed = conn.execute(
                "SELECT COUNT(*) as cnt FROM curiosity_queue WHERE status = 'failed'"
            ).fetchone()["cnt"]
        return {
            "enabled": self.enabled,
            "pending": pending,
            "processed": processed,
            "failed": failed,
            "learning_sessions_today": self._learning_sessions_today,
            "max_sessions_per_day": self.MAX_LEARNING_SESSIONS_PER_DAY,
            "web_requests_this_hour": self._web_requests_this_hour,
            "max_web_requests_per_hour": self.MAX_WEB_REQUESTS_PER_HOUR,
        }

    def pause(self):
        self.enabled = False

    def resume(self):
        self.enabled = True

    def clear_queue(self) -> int:
        with self.db.get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM curiosity_queue WHERE status = 'pending'"
            )
            conn.commit()
            return cursor.rowcount

    def _reset_counters(self):
        now = time.time()
        if now - self._hour_start >= 3600:
            self._web_requests_this_hour = 0
            self._hour_start = now
        if now - self._day_start >= 86400:
            self._learning_sessions_today = 0
            self._day_start = now
