"""ResearchDecisionEngine — teaches Genesis WHEN to research.

Separate from the execution engine. This decides whether web research
is needed based on:
- intent
- context
- knowledge confidence
- freshness
- user request
- research history

Do NOT implement as keyword-only rules.
Use multi-factor scoring.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ResearchDecision:
    """Decision about whether to research."""
    should_research: bool = False
    confidence: float = 0.0
    reason: str = ""
    research_type: str = "none"  # none, quick, standard, deep
    freshness_requirement: str = "stable"
    verification_level: str = "basic"
    factors: dict = field(default_factory=dict)


class ResearchDecisionEngine:
    """Decides whether web research is needed.

    Uses multi-factor scoring instead of keyword-only rules.
    Factors:
    1. Knowledge confidence
    2. User request signals
    3. Freshness requirement
    4. Context signals
    5. Topic characteristics
    6. Research history
    """

    def __init__(self, db=None):
        self.db = db
        self._research_history = {}  # user_id -> list of recent research topics

    def decide(self, question: str, knowledge_status: str = "unknown",
               knowledge_confidence: float = 0.0, user_goal: str = "",
               context: dict = None, detected_language: str = "english",
               user_id: str = "") -> ResearchDecision:
        """Decide whether research is needed.

        Args:
            question: The user's question
            knowledge_status: Current knowledge status (known, unknown, uncertain, outdated)
            knowledge_confidence: Confidence in existing knowledge (0-1)
            user_goal: Detected user goal
            context: Conversation context
            detected_language: Detected language
            user_id: User identifier for history

        Returns:
            ResearchDecision with recommendation
        """
        decision = ResearchDecision()

        # Calculate scores for each factor
        factors = {}

        # Factor 1: Knowledge confidence (0-1, higher = less need for research)
        factors["knowledge_confidence"] = self._score_knowledge_confidence(
            knowledge_status, knowledge_confidence
        )

        # Factor 2: User request signals (0-1, higher = more need for research)
        factors["user_request"] = self._score_user_request(question)

        # Factor 3: Freshness requirement (0-1, higher = more need for research)
        factors["freshness"] = self._score_freshness_requirement(question)

        # Factor 4: Context signals (0-1, higher = more need for research)
        factors["context"] = self._score_context_signals(context)

        # Factor 5: Topic characteristics (0-1, higher = more need for research)
        factors["topic"] = self._score_topic_characteristics(question)

        # Factor 6: Research history (0-1, higher = less need for re-research)
        factors["history"] = self._score_research_history(question, user_id)

        # Weighted combination
        weights = {
            "knowledge_confidence": 0.35,  # Increased from 0.25
            "user_request": 0.30,  # Increased from 0.25
            "freshness": 0.15,
            "context": 0.10,
            "topic": 0.10,
            "history": 0.00,  # Removed from active scoring
        }

        research_score = sum(
            factors[k] * weights[k] for k in factors
        )

        # Determine decision
        decision.factors = factors
        decision.confidence = abs(research_score - 0.5) * 2  # Distance from threshold

        if research_score >= 0.55:  # Lowered from 0.6
            decision.should_research = True
            decision.research_type = self._determine_research_type(
                research_score, question, factors
            )
            decision.freshness_requirement = self._determine_freshness(question)
            decision.verification_level = self._determine_verification_level(
                question, research_score
            )
            decision.reason = self._generate_reason(factors, research_score)
        else:
            decision.should_research = False
            decision.research_type = "none"
            decision.reason = "Existing knowledge is sufficient"

        return decision

    def _score_knowledge_confidence(self, status: str, confidence: float) -> float:
        """Score based on existing knowledge confidence.

        Higher score = MORE need for research (inverted from original logic).
        """
        if status == "known" and confidence >= 0.8:
            return 0.1  # Well known, little need for research
        elif status == "known" and confidence >= 0.6:
            return 0.3  # Somewhat known
        elif status == "uncertain":
            return 0.6  # Uncertain, needs verification
        elif status == "outdated":
            return 0.8  # Outdated, needs fresh info
        elif status == "contradicted":
            return 0.7  # Contradicted, needs resolution
        else:  # unknown
            return 0.9  # Unknown, definitely needs research

    def _score_user_request(self, question: str) -> float:
        """Score based on user request signals.

        Higher score = more need for research.
        """
        q_lower = question.lower()
        score = 0.4  # baseline (increased from 0.3)

        # Explicit search/research request (structural patterns)
        search_patterns = [
            r'\b(search|find|look up|research|verify|check|confirm)\b',
            r'\b(latest|current|recent|today|now|202[4-6])\b',
            r'\b(kya hai|kya hota|kaise|kaun|kab|kahan)\b',
            r'\b(tell me about|batao|samjhao)\b',
        ]

        for pattern in search_patterns:
            if __import__("re").search(pattern, q_lower):
                score += 0.15

        # Question structure
        if "?" in question:
            score += 0.15  # Increased from 0.1

        # Length indicates complexity
        word_count = len(question.split())
        if word_count > 10:
            score += 0.1
        if word_count > 20:
            score += 0.1

        return min(1.0, score)

    def _score_freshness_requirement(self, question: str) -> float:
        """Score based on freshness requirement.

        Higher score = more need for fresh information.
        """
        q_lower = question.lower()
        score = 0.3  # baseline (increased from 0.2)

        # Freshness indicators (structural patterns)
        fresh_patterns = [
            r'\b(latest|current|recent|newest|today|now)\b',
            r'\b(202[4-6]|this year|this month)\b',
            r'\b(price|cost|version|release|update)\b',
            r'\b(event|happening|news|breaking)\b',
        ]

        for pattern in fresh_patterns:
            if __import__("re").search(pattern, q_lower):
                score += 0.15

        return min(1.0, score)

    def _score_context_signals(self, context: dict = None) -> float:
        """Score based on conversation context.

        Higher score = more need for research in context.
        """
        if not context:
            return 0.3

        score = 0.3

        # Previous topic was researched
        if context.get("previous_researched"):
            score += 0.2

        # User expressed uncertainty
        if context.get("user_uncertain"):
            score += 0.2

        # Follow-up question
        if context.get("is_followup"):
            score += 0.1

        return min(1.0, score)

    def _score_topic_characteristics(self, question: str) -> float:
        """Score based on topic characteristics.

        Higher score = more likely to need research.
        """
        q_lower = question.lower()
        score = 0.4  # baseline (increased from 0.3)

        # Technical topics often need research
        tech_patterns = [
            r'\b(api|framework|library|version|update|release)\b',
            r'\b(python|javascript|java|html|css|sql)\b',
            r'\b(database|server|deploy|docker|kubernetes)\b',
        ]

        for pattern in tech_patterns:
            if __import__("re").search(pattern, q_lower):
                score += 0.1

        # Factual questions often need verification
        factual_patterns = [
            r'\b(who|what|when|where|how many|how much)\b',
            r'\b(kaun|kya|kab|kahan|kitna)\b',
        ]

        for pattern in factual_patterns:
            if __import__("re").search(pattern, q_lower):
                score += 0.1

        return min(1.0, score)

    def _score_research_history(self, question: str, user_id: str) -> float:
        """Score based on research history.

        Higher score = less need if recently researched.
        """
        if not user_id or user_id not in self._research_history:
            return 0.5  # No history, neutral

        recent_topics = self._research_history.get(user_id, [])
        q_words = set(question.lower().split())

        # Check if similar topic was recently researched
        for topic in recent_topics[-5:]:  # Last 5 research topics
            topic_words = set(topic.lower().split())
            overlap = q_words & topic_words
            if len(overlap) >= 2:
                return 0.8  # Recently researched similar topic

        return 0.3  # Different topic

    def _determine_research_type(self, score: float, question: str,
                                   factors: dict) -> str:
        """Determine the type of research needed."""
        if score >= 0.8:
            return "deep"
        elif score >= 0.6:
            return "standard"
        else:
            return "quick"

    def _determine_freshness(self, question: str) -> str:
        """Determine freshness requirement."""
        q_lower = question.lower()

        if any(w in q_lower for w in ["latest", "current", "today", "now", "2026"]):
            return "current"
        elif any(w in q_lower for w in ["recent", "new", "updated"]):
            return "recent"
        else:
            return "stable"

    def _determine_verification_level(self, question: str, score: float) -> str:
        """Determine verification level."""
        if score >= 0.8:
            return "rigorous"
        elif score >= 0.6:
            return "standard"
        else:
            return "basic"

    def _generate_reason(self, factors: dict, score: float) -> str:
        """Generate human-readable reason for the decision."""
        reasons = []

        if factors.get("knowledge_confidence", 0) < 0.3:
            reasons.append("low knowledge confidence")
        if factors.get("user_request", 0) > 0.6:
            reasons.append("user explicitly requested research")
        if factors.get("freshness", 0) > 0.6:
            reasons.append("fresh information needed")
        if factors.get("topic", 0) > 0.6:
            reasons.append("topic requires verification")

        if not reasons:
            reasons.append("multi-factor analysis")

        return f"Research needed: {', '.join(reasons)} (score={score:.2f})"

    def record_research(self, user_id: str, topic: str):
        """Record that research was performed on a topic."""
        if user_id not in self._research_history:
            self._research_history[user_id] = []
        self._research_history[user_id].append(topic)
        # Keep only last 20 topics
        self._research_history[user_id] = self._research_history[user_id][-20:]
