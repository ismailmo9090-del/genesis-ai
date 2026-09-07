"""KnowledgeGapDetector — structured knowledge gap analysis.

Before researching, Genesis should determine what it does not know.
Represents knowledge gaps as structured data:

- topic
- requested_information
- missing_information
- confidence
- freshness_requirement
- reason_for_research
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeGap:
    """A structured knowledge gap."""
    topic: str = ""
    requested_information: str = ""
    missing_information: str = ""
    confidence: float = 0.0
    freshness_requirement: str = "stable"  # stable, recent, current
    reason_for_research: str = ""
    gap_type: str = "unknown"  # unknown, outdated, uncertain, incomplete
    priority: int = 0  # Higher = more important to research


@dataclass
class GapAnalysis:
    """Result of gap analysis."""
    gaps: list[KnowledgeGap] = field(default_factory=list)
    overall_confidence: float = 0.0
    research_needed: bool = False
    primary_gap: Optional[KnowledgeGap] = None
    analysis_time: float = 0.0


class KnowledgeGapDetector:
    """Detects knowledge gaps before research.

    Analyzes:
    1. What information is requested
    2. What information is available
    3. What information is missing
    4. What information may be outdated
    5. Confidence levels
    6. Freshness requirements

    Does NOT hardcode individual topics.
    Uses structural patterns for detection.
    """

    def __init__(self, db=None):
        self.db = db

    def analyze(self, question: str, local_knowledge: list = None,
                learned_knowledge: list = None, context: dict = None,
                knowledge_status: str = "unknown",
                knowledge_confidence: float = 0.0) -> GapAnalysis:
        """Analyze knowledge gaps for a question.

        Args:
            question: The user's question
            local_knowledge: Available local knowledge
            learned_knowledge: Available learned knowledge
            context: Conversation context
            knowledge_status: Current knowledge status
            knowledge_confidence: Confidence in existing knowledge

        Returns:
            GapAnalysis with detected gaps
        """
        start_time = time.time()
        analysis = GapAnalysis()

        # Extract what information is requested
        requested_info = self._extract_requested_information(question)

        # Check what's available
        available_info = self._check_available_information(
            local_knowledge, learned_knowledge
        )

        # Detect gaps
        gaps = self._detect_gaps(
            question, requested_info, available_info, knowledge_status,
            knowledge_confidence, context
        )

        analysis.gaps = gaps
        analysis.overall_confidence = knowledge_confidence
        analysis.research_needed = len(gaps) > 0 and any(
            g.priority >= 3 for g in gaps
        )

        if gaps:
            analysis.primary_gap = max(gaps, key=lambda g: g.priority)

        analysis.analysis_time = time.time() - start_time

        return analysis

    def _extract_requested_information(self, question: str) -> list[str]:
        """Extract what information the user is requesting."""
        requested = []
        q_lower = question.lower()

        # Question type detection (structural patterns)
        if any(w in q_lower for w in ["what is", "what are", "kya hai", "kya hota"]):
            requested.append("definition")
            requested.append("explanation")

        if any(w in q_lower for w in ["who is", "who was", "kaun hai", "kaun tha"]):
            requested.append("identity")
            requested.append("biography")

        if any(w in q_lower for w in ["how to", "kaise", "steps", "process"]):
            requested.append("procedure")
            requested.append("steps")

        if any(w in q_lower for w in ["when did", "kab", "date", "year"]):
            requested.append("temporal_info")

        if any(w in q_lower for w in ["where is", "kahan", "location", "place"]):
            requested.append("location_info")

        if any(w in q_lower for w in ["why", "kyu", "reason", "because"]):
            requested.append("causal_info")

        if any(w in q_lower for w in ["how many", "how much", "kitna", "number"]):
            requested.append("quantitative_info")

        if any(w in q_lower for w in ["compare", "vs", "difference", "better"]):
            requested.append("comparison")

        if any(w in q_lower for w in ["latest", "current", "recent", "new"]):
            requested.append("current_info")

        if any(w in q_lower for w in ["price", "cost", "version"]):
            requested.append("current_value")

        if not requested:
            requested.append("general_info")

        return requested

    def _check_available_information(self, local_knowledge: list = None,
                                      learned_knowledge: list = None) -> dict:
        """Check what information is already available."""
        available = {
            "has_local": bool(local_knowledge),
            "has_learned": bool(learned_knowledge),
            "local_count": len(local_knowledge) if local_knowledge else 0,
            "learned_count": len(learned_knowledge) if learned_knowledge else 0,
            "topics": set(),
            "confidence": 0.0,
        }

        # Extract topics from available knowledge
        if local_knowledge:
            for k in local_knowledge[:10]:
                topic = k.get("topic", k.get("concept", ""))
                if topic:
                    available["topics"].add(topic.lower())
                conf = k.get("confidence", 0.5)
                available["confidence"] = max(available["confidence"], conf)

        if learned_knowledge:
            for k in learned_knowledge[:10]:
                if hasattr(k, "concept"):
                    available["topics"].add(k.concept.lower())
                    available["confidence"] = max(
                        available["confidence"], k.confidence
                    )

        return available

    def _detect_gaps(self, question: str, requested_info: list,
                      available_info: dict, knowledge_status: str,
                      knowledge_confidence: float,
                      context: dict = None) -> list[KnowledgeGap]:
        """Detect specific knowledge gaps."""
        gaps = []

        # Gap 1: No information available
        if knowledge_status == "unknown" or (
            not available_info["has_local"] and not available_info["has_learned"]
        ):
            gap = KnowledgeGap(
                topic=self._extract_topic(question),
                requested_information=", ".join(requested_info),
                missing_information=question,
                confidence=0.0,
                freshness_requirement=self._determine_freshness(question),
                reason_for_research="No existing knowledge available",
                gap_type="unknown",
                priority=5,
            )
            gaps.append(gap)

        # Gap 2: Low confidence knowledge
        elif knowledge_confidence < 0.5:
            gap = KnowledgeGap(
                topic=self._extract_topic(question),
                requested_information=", ".join(requested_info),
                missing_information="Higher confidence verification",
                confidence=knowledge_confidence,
                freshness_requirement=self._determine_freshness(question),
                reason_for_research="Existing knowledge has low confidence",
                gap_type="uncertain",
                priority=4,
            )
            gaps.append(gap)

        # Gap 3: Potentially outdated information
        elif knowledge_status == "outdated":
            gap = KnowledgeGap(
                topic=self._extract_topic(question),
                requested_information=", ".join(requested_info),
                missing_information="Current information",
                confidence=knowledge_confidence,
                freshness_requirement="current",
                reason_for_research="Knowledge may be outdated",
                gap_type="outdated",
                priority=4,
            )
            gaps.append(gap)

        # Gap 4: Contradicted information
        elif knowledge_status == "contradicted":
            gap = KnowledgeGap(
                topic=self._extract_topic(question),
                requested_information=", ".join(requested_info),
                missing_information="Resolved contradiction",
                confidence=knowledge_confidence,
                freshness_requirement=self._determine_freshness(question),
                reason_for_research="Knowledge contains contradictions",
                gap_type="uncertain",
                priority=4,
            )
            gaps.append(gap)

        # Gap 5: Incomplete information for complex questions
        if any(info in requested_info for info in ["comparison", "current_info", "current_value"]):
            if knowledge_confidence < 0.7:
                gap = KnowledgeGap(
                    topic=self._extract_topic(question),
                    requested_information=", ".join(requested_info),
                    missing_information="Complete information for comparison/current value",
                    confidence=knowledge_confidence,
                    freshness_requirement="current",
                    reason_for_research="Complex question requires fresh data",
                    gap_type="incomplete",
                    priority=3,
                )
                gaps.append(gap)

        # Gap 6: User explicitly requested research
        q_lower = question.lower()
        if any(w in q_lower for w in ["search", "find", "look up", "research", "verify"]):
            gap = KnowledgeGap(
                topic=self._extract_topic(question),
                requested_information=", ".join(requested_info),
                missing_information="External verification",
                confidence=knowledge_confidence,
                freshness_requirement=self._determine_freshness(question),
                reason_for_research="User explicitly requested research",
                gap_type="unknown",
                priority=5,
            )
            gaps.append(gap)

        return gaps

    def _extract_topic(self, question: str) -> str:
        """Extract the main topic from the question."""
        import re
        # Remove question words
        q = re.sub(
            r'\b(what|who|when|where|why|how|is|are|was|were|do|does|did|'
            r'kya|hai|kaun|kaise|kab|kahan|kyu|batao|samjhao|mujhe|tell|me|about|the)\b',
            '', question, flags=re.IGNORECASE
        ).strip()
        # Take first few words as topic
        words = q.split()[:5]
        return " ".join(words) if words else question[:50]

    def _determine_freshness(self, question: str) -> str:
        """Determine freshness requirement from question."""
        q_lower = question.lower()

        if any(w in q_lower for w in ["latest", "current", "today", "now", "2026"]):
            return "current"
        elif any(w in q_lower for w in ["recent", "new", "updated"]):
            return "recent"
        else:
            return "stable"
