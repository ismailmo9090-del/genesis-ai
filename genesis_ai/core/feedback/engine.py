"""Feedback engine for processing user feedback and applying corrections."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from genesis_ai.database.db import DatabaseManager


class FeedbackType:
    POSITIVE = "positive"
    NEGATIVE = "negative"
    CORRECTION = "correction"
    PREFERENCE = "preference"
    RATING = "rating"


@dataclass
class FeedbackResult:
    success: bool
    feedback_id: Optional[int] = None
    feedback_type: str = ""
    correction_event: Optional[dict] = None
    confidence_adjustment: float = 0.0
    message: str = ""


@dataclass
class CorrectionEvent:
    old_belief: str
    user_correction: str
    new_belief: str
    reason: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    knowledge_id: Optional[int] = None
    confidence_delta: float = 0.0


class FeedbackEngine:
    """Processes user feedback and applies corrections to knowledge."""

    POSITIVE_CONFIDENCE_BOOST = 0.05
    NEGATIVE_CONFIDENCE_PENALTY = 0.10
    CORRECTION_CONFIDENCE_BOOST = 0.15

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._ensure_tables()

    def _ensure_tables(self):
        with self.db.get_conn() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    old_belief TEXT NOT NULL,
                    user_correction TEXT NOT NULL,
                    new_belief TEXT NOT NULL,
                    reason TEXT,
                    knowledge_id INTEGER,
                    confidence_delta REAL DEFAULT 0.0,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                    FOREIGN KEY (knowledge_id) REFERENCES knowledge(id) ON DELETE SET NULL
                )"""
            )
            conn.commit()

    def process_feedback(
        self,
        user_id: int,
        conversation_id: int,
        feedback_type: str,
        details: dict = None,
    ) -> FeedbackResult:
        details = details or {}
        if feedback_type == FeedbackType.POSITIVE:
            return self._process_positive_feedback(user_id, conversation_id, details)
        elif feedback_type == FeedbackType.NEGATIVE:
            return self._process_negative_feedback(user_id, conversation_id, details)
        elif feedback_type == FeedbackType.CORRECTION:
            return self._process_correction(user_id, conversation_id, details)
        elif feedback_type == FeedbackType.PREFERENCE:
            return self._process_preference(user_id, details)
        elif feedback_type == FeedbackType.RATING:
            return self._process_rating(user_id, conversation_id, details)
        return FeedbackResult(
            success=False,
            feedback_type=feedback_type,
            message=f"Unknown feedback type: {feedback_type}",
        )

    def get_feedback_history(self, user_id: int, limit: int = 50) -> list[dict]:
        with self.db.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM feedback WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_feedback_stats(self) -> dict:
        with self.db.get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) as cnt FROM feedback").fetchone()["cnt"]
            by_type = conn.execute(
                "SELECT feedback_type, COUNT(*) as cnt FROM feedback GROUP BY feedback_type"
            ).fetchall()
            avg_rating = conn.execute(
                "SELECT AVG(rating) as avg FROM feedback WHERE rating IS NOT NULL"
            ).fetchone()["avg"]
            recent_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM feedback WHERE created_at >= datetime('now', '-7 days')"
            ).fetchone()["cnt"]
            correction_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM corrections"
            ).fetchone()["cnt"]
        return {
            "total_feedback": total,
            "by_type": {row["feedback_type"]: row["cnt"] for row in by_type},
            "average_rating": round(avg_rating, 2) if avg_rating else None,
            "recent_feedback_7d": recent_count,
            "total_corrections": correction_count,
        }

    def calculate_user_satisfaction(self) -> float:
        with self.db.get_conn() as conn:
            ratings = conn.execute(
                "SELECT rating FROM feedback WHERE rating IS NOT NULL"
            ).fetchall()
            positive = conn.execute(
                "SELECT COUNT(*) as cnt FROM feedback WHERE feedback_type = 'positive'"
            ).fetchone()["cnt"]
            negative = conn.execute(
                "SELECT COUNT(*) as cnt FROM feedback WHERE feedback_type = 'negative'"
            ).fetchone()["cnt"]
            total = conn.execute("SELECT COUNT(*) as cnt FROM feedback").fetchone()["cnt"]
        if total == 0:
            return 0.5
        if ratings:
            avg_rating = sum(r["rating"] for r in ratings) / len(ratings)
            rating_score = avg_rating / 5.0
        else:
            rating_score = 0.5
        if positive + negative > 0:
            sentiment_score = positive / (positive + negative)
        else:
            sentiment_score = 0.5
        satisfaction = (rating_score * 0.6) + (sentiment_score * 0.4)
        return round(min(1.0, max(0.0, satisfaction)), 4)

    def apply_feedback_to_knowledge(self, feedback: dict) -> dict:
        feedback_type = feedback.get("feedback_type", "")
        knowledge_id = feedback.get("knowledge_id")
        if not knowledge_id:
            return {"adjusted": False, "reason": "No knowledge_id provided"}
        knowledge = self.db.get_knowledge(knowledge_id)
        if not knowledge:
            return {"adjusted": False, "reason": "Knowledge not found"}
        current_conf = knowledge.get("confidence", 0.5)
        adjustment = 0.0
        new_flags = {}
        if feedback_type == FeedbackType.POSITIVE:
            adjustment = self.POSITIVE_CONFIDENCE_BOOST
            new_flags["verification_status"] = "probable"
        elif feedback_type == FeedbackType.NEGATIVE:
            adjustment = -self.NEGATIVE_CONFIDENCE_PENALTY
            new_flags["verification_status"] = "disputed"
        elif feedback_type == FeedbackType.CORRECTION:
            adjustment = self.CORRECTION_CONFIDENCE_BOOST
        new_conf = max(0.0, min(1.0, current_conf + adjustment))
        update_kwargs = {"confidence": new_conf}
        update_kwargs.update(new_flags)
        self.db.update_knowledge(knowledge_id, **update_kwargs)
        return {
            "adjusted": True,
            "old_confidence": current_conf,
            "new_confidence": new_conf,
            "adjustment": adjustment,
            "flags_updated": new_flags,
        }

    def _process_positive_feedback(
        self, user_id: int, conversation_id: int, details: dict
    ) -> FeedbackResult:
        comment = details.get("comment", "")
        experience_id = details.get("experience_id")
        fb_id = self.db.insert_feedback(
            user_id=user_id,
            rating=None,
            comment=comment,
            experience_id=experience_id,
            feedback_type=FeedbackType.POSITIVE,
        )
        knowledge_id = details.get("knowledge_id")
        if knowledge_id:
            self.apply_feedback_to_knowledge(
                {"feedback_type": FeedbackType.POSITIVE, "knowledge_id": knowledge_id}
            )
        return FeedbackResult(
            success=True,
            feedback_id=fb_id,
            feedback_type=FeedbackType.POSITIVE,
            confidence_adjustment=self.POSITIVE_CONFIDENCE_BOOST,
            message="Positive feedback recorded",
        )

    def _process_negative_feedback(
        self, user_id: int, conversation_id: int, details: dict
    ) -> FeedbackResult:
        comment = details.get("comment", "")
        experience_id = details.get("experience_id")
        fb_id = self.db.insert_feedback(
            user_id=user_id,
            rating=None,
            comment=comment,
            experience_id=experience_id,
            feedback_type=FeedbackType.NEGATIVE,
        )
        knowledge_id = details.get("knowledge_id")
        if knowledge_id:
            self.apply_feedback_to_knowledge(
                {"feedback_type": FeedbackType.NEGATIVE, "knowledge_id": knowledge_id}
            )
        return FeedbackResult(
            success=True,
            feedback_id=fb_id,
            feedback_type=FeedbackType.NEGATIVE,
            confidence_adjustment=-self.NEGATIVE_CONFIDENCE_PENALTY,
            message="Negative feedback recorded",
        )

    def _process_correction(
        self, user_id: int, conversation_id: int, details: dict
    ) -> FeedbackResult:
        old_belief = details.get("old_belief", "")
        new_belief = details.get("new_belief", "")
        reason = details.get("reason", "user_correction")
        if not old_belief or not new_belief:
            return FeedbackResult(
                success=False,
                feedback_type=FeedbackType.CORRECTION,
                message="Both old_belief and new_belief are required",
            )
        event = CorrectionEvent(
            old_belief=old_belief,
            user_correction=new_belief,
            new_belief=new_belief,
            reason=reason,
        )
        knowledge_id = None
        existing = self.db.search_knowledge(old_belief, limit=5)
        if existing:
            knowledge = existing[0]
            knowledge_id = knowledge["id"]
            self.db.update_knowledge(
                knowledge_id,
                claim=new_belief,
                confidence=min(knowledge.get("confidence", 0.5) + self.CORRECTION_CONFIDENCE_BOOST, 1.0),
            )
            event.knowledge_id = knowledge_id
            event.confidence_delta = self.CORRECTION_CONFIDENCE_BOOST
        else:
            concept = self.db.search_concepts(old_belief, limit=1)
            concept_id = concept[0]["id"] if concept else self._ensure_concept(old_belief)
            knowledge_id = self.db.insert_knowledge(
                concept_id=concept_id,
                claim=new_belief,
                claim_type="correction",
                confidence=0.7,
            )
            event.knowledge_id = knowledge_id
        with self.db.get_conn() as conn:
            conn.execute(
                """INSERT INTO corrections
                   (user_id, old_belief, user_correction, new_belief, reason, knowledge_id, confidence_delta)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    old_belief,
                    new_belief,
                    new_belief,
                    reason,
                    knowledge_id,
                    event.confidence_delta,
                ),
            )
            conn.commit()
        self.db.insert_feedback(
            user_id=user_id,
            rating=3,
            comment=f"Correction: '{old_belief}' -> '{new_belief}'",
            feedback_type=FeedbackType.CORRECTION,
        )
        return FeedbackResult(
            success=True,
            feedback_type=FeedbackType.CORRECTION,
            correction_event={
                "old_belief": event.old_belief,
                "new_belief": event.new_belief,
                "reason": event.reason,
                "timestamp": event.timestamp,
                "knowledge_id": event.knowledge_id,
            },
            confidence_adjustment=event.confidence_delta,
            message=f"Correction applied: '{old_belief}' updated to '{new_belief}'",
        )

    def _process_preference(self, user_id: int, details: dict) -> FeedbackResult:
        preference_key = details.get("key", "")
        preference_value = details.get("value", "")
        if not preference_key:
            return FeedbackResult(
                success=False,
                feedback_type=FeedbackType.PREFERENCE,
                message="Preference key is required",
            )
        user = self.db.get_user(user_id)
        if user:
            prefs = json.loads(user.get("preferences", "{}"))
            prefs[preference_key] = preference_value
            self.db.update_user(user_id, preferences=prefs)
        self.db.insert_feedback(
            user_id=user_id,
            rating=3,
            comment=f"Preference: {preference_key} = {preference_value}",
            feedback_type=FeedbackType.PREFERENCE,
        )
        return FeedbackResult(
            success=True,
            feedback_type=FeedbackType.PREFERENCE,
            message=f"Preference '{preference_key}' set to '{preference_value}'",
        )

    def _process_rating(
        self, user_id: int, conversation_id: int, details: dict
    ) -> FeedbackResult:
        rating = details.get("rating", 0)
        comment = details.get("comment", "")
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return FeedbackResult(
                success=False,
                feedback_type=FeedbackType.RATING,
                message="Rating must be an integer between 1 and 5",
            )
        fb_id = self.db.insert_feedback(
            user_id=user_id,
            rating=rating,
            comment=comment,
            feedback_type=FeedbackType.RATING,
        )
        return FeedbackResult(
            success=True,
            feedback_id=fb_id,
            feedback_type=FeedbackType.RATING,
            message=f"Rating {rating}/5 recorded",
        )

    def _ensure_concept(self, name: str) -> int:
        concept = self.db.get_concept_by_name(name)
        if concept:
            return concept["id"]
        return self.db.insert_concept(name=name, domain="general", confidence=0.5)
