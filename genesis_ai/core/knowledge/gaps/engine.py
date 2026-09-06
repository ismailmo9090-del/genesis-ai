"""Knowledge gap detector for identifying missing, outdated, or uncertain knowledge.

Takes an AnalysisResult and produces a prioritized list of knowledge gaps
with suggested search queries and a research plan.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from genesis_ai.database.db import DatabaseManager
from genesis_ai.knowledge.graph.engine import KnowledgeGraph
from genesis_ai.knowledge.storage.engine import KnowledgeStorage
from genesis_ai.core.analysis.engine import AnalysisResult


@dataclass
class KnowledgeGap:
    """Represents a single identified knowledge gap."""

    topic: str
    gap_type: str = "missing"
    priority: str = "medium"
    search_queries: list = field(default_factory=list)
    related_knowledge: list = field(default_factory=list)


@dataclass
class GapAnalysisResult:
    """Complete result of knowledge gap analysis."""

    gaps: list[KnowledgeGap] = field(default_factory=list)
    total_gaps: int = 0
    research_plan: list = field(default_factory=list)
    can_answer_locally: bool = False


# ── Gap type detection patterns ────────────────────────────────

_OUTDATED_INDICATORS = re.compile(
    r'\b(outdated|old|deprecated|legacy|previous version|'
    r'2020|2021|2022|2023|last year|purana)\b',
    re.IGNORECASE,
)

UNCERTAIN_INDICATORS = re.compile(
    r'\b(maybe|uncertain|unclear|disputed|debated|controversial|'
    r'some say|others claim|mixed opinions|alag alag)\b',
    re.IGNORECASE,
)

CONFLICTING_INDICATORS = re.compile(
    r'\b(conflict|contradict|disagree|opposite|different sources|'
    r'ek kehta hai dusra kehta|conflicting)\b',
    re.IGNORECASE,
)


# ── Query generation templates ─────────────────────────────────

_QUERY_TEMPLATES = {
    "definition": [
        "what is {topic}",
        "{topic} definition",
        "{topic} ka matlab",
        "{topic} explained",
    ],
    "how_to": [
        "how to {topic}",
        "{topic} step by step",
        "{topic} tutorial",
        "{topic} kaise kare",
    ],
    "examples": [
        "{topic} examples",
        "{topic} example code",
        "{topic} sample",
        "{topic} demo",
    ],
    "best_practices": [
        "{topic} best practices",
        "{topic} tips",
        "{topic} do and dont",
        "{topic} recommended approach",
    ],
    "comparison": [
        "{topic} pros and cons",
        "{topic} advantages disadvantages",
        "{topic} vs alternatives",
        "{topic} alternatives",
    ],
    "troubleshooting": [
        "{topic} common errors",
        "{topic} debugging",
        "{topic} issues and solutions",
        "{topic} problems",
    ],
    "latest": [
        "latest {topic}",
        "{topic} 2026",
        "{topic} current version",
        "{topic} recent updates",
    ],
}


class KnowledgeGapDetector:
    """Detects knowledge gaps from analysis results and generates research plans.

    Uses the KnowledgeGraph and KnowledgeStorage to check what knowledge
    already exists locally, then identifies gaps and prioritizes them
    for research.
    """

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.graph = KnowledgeGraph(db)
        self.storage = KnowledgeStorage(db)

    def detect_gaps(self, analysis: AnalysisResult) -> GapAnalysisResult:
        """Analyze the AnalysisResult to find and prioritize knowledge gaps.

        Args:
            analysis: The AnalysisResult from the AnalysisEngine.

        Returns:
            GapAnalysisResult with prioritized gaps and a research plan.
        """
        result = GapAnalysisResult()

        raw_gaps = self._extract_gaps(analysis)
        enriched_gaps = self._enrich_gaps(raw_gaps, analysis)
        partial_gaps = self._check_partial_coverage(enriched_gaps)
        scored_gaps = self._score_priorities(partial_gaps, analysis)

        result.gaps = scored_gaps
        result.total_gaps = len(scored_gaps)
        result.research_plan = self._build_research_plan(scored_gaps)
        result.can_answer_locally = result.total_gaps == 0

        return result

    def _extract_gaps(self, analysis: AnalysisResult) -> list[KnowledgeGap]:
        """Create KnowledgeGap objects from unknown knowledge entries."""
        gaps = []
        for unknown in analysis.unknown_knowledge:
            gap_type = self._classify_gap_type(unknown)
            gap = KnowledgeGap(
                topic=unknown.get("query", "unknown"),
                gap_type=gap_type,
                priority=unknown.get("priority", "medium"),
                search_queries=[],
                related_knowledge=[],
            )
            gaps.append(gap)
        return gaps

    def _classify_gap_type(self, unknown_entry: dict) -> str:
        """Determine whether a gap is missing, outdated, uncertain, or conflicting."""
        query = unknown_entry.get("query", "")
        component = unknown_entry.get("component", "")

        if _OUTDATED_INDICATORS.search(query) or _OUTDATED_INDICATORS.search(component):
            return "outdated"
        if CONFLICTING_INDICATORS.search(query) or CONFLICTING_INDICATORS.search(component):
            return "conflicting"
        if UNCERTAIN_INDICATORS.search(query) or UNCERTAIN_INDICATORS.search(component):
            return "uncertain"
        return "missing"

    def _enrich_gaps(self, gaps: list[KnowledgeGap], analysis: AnalysisResult) -> list[KnowledgeGap]:
        """Add search queries and related knowledge to each gap."""
        for gap in gaps:
            gap.search_queries = self._generate_search_queries(gap.topic, analysis)
            gap.related_knowledge = self._find_related_knowledge(gap.topic)
        return gaps

    def _generate_search_queries(self, topic: str, analysis: AnalysisResult) -> list[str]:
        """Generate multiple search query variants for a gap topic."""
        queries = []
        topic_lower = topic.lower().strip()

        base_terms = topic_lower.split()
        if len(base_terms) > 4:
            topic_lower = " ".join(base_terms[:4])

        applicable_templates = self._select_query_templates(topic_lower, analysis)

        for template_key in applicable_templates:
            templates = _QUERY_TEMPLATES.get(template_key, [])
            for template in templates:
                query = template.format(topic=topic_lower)
                if query not in queries:
                    queries.append(query)

        generic_queries = [
            topic_lower,
            f"{topic_lower} explained",
            f"{topic_lower} tutorial",
        ]
        for gq in generic_queries:
            if gq not in queries:
                queries.append(gq)

        return queries[:8]

    def _select_query_templates(self, topic: str, analysis: AnalysisResult) -> list[str]:
        """Choose which query template categories apply to a topic."""
        templates = ["definition", "examples"]

        if analysis.recommended_approach in ("deep_research_then_build", "comprehensive_research"):
            templates.extend(["best_practices", "comparison", "latest"])

        if analysis.recommended_approach in ("quick_research_then_respond", "research_and_explain"):
            templates.append("how_to")

        if analysis.recommended_approach == "parallel_research_then_compare":
            templates.append("comparison")

        return templates

    def _find_related_knowledge(self, topic: str) -> list[dict]:
        """Find existing knowledge related to a gap topic."""
        related = []

        graph_results = self.graph.search_concepts(topic)
        for concept in graph_results[:3]:
            related.append({
                "type": "concept",
                "name": concept.get("name"),
                "description": concept.get("description"),
                "confidence": concept.get("confidence", 0),
            })

        storage_results = self.storage.search_knowledge(topic)
        for knowledge in storage_results[:3]:
            related.append({
                "type": "knowledge",
                "claim": knowledge.get("claim"),
                "confidence": knowledge.get("confidence", 0),
                "source": knowledge.get("source"),
            })

        related_terms = topic.split()
        for term in related_terms:
            if len(term) > 3:
                term_results = self.graph.search_concepts(term)
                for concept in term_results[:2]:
                    already_found = any(
                        r.get("name") == concept.get("name") for r in related if r.get("type") == "concept"
                    )
                    if not already_found:
                        related.append({
                            "type": "related_concept",
                            "name": concept.get("name"),
                            "description": concept.get("description"),
                            "confidence": concept.get("confidence", 0),
                        })

        return related

    def _check_partial_coverage(self, gaps: list[KnowledgeGap]) -> list[KnowledgeGap]:
        """Downgrade gaps that have partial local knowledge coverage."""
        for gap in gaps:
            if gap.related_knowledge:
                high_confidence = [
                    r for r in gap.related_knowledge
                    if r.get("confidence", 0) >= 0.7
                ]
                medium_confidence = [
                    r for r in gap.related_knowledge
                    if 0.4 <= r.get("confidence", 0) < 0.7
                ]

                if len(high_confidence) >= 2:
                    gap.gap_type = "uncertain"
                    gap.priority = "low"
                elif len(medium_confidence) >= 2:
                    gap.priority = "low" if gap.priority == "medium" else gap.priority

        return gaps

    def _score_priorities(self, gaps: list[KnowledgeGap], analysis: AnalysisResult) -> list[KnowledgeGap]:
        """Assign final priority scores based on importance to the answer."""
        component_gap_count = {}
        for gap in gaps:
            topic = gap.topic
            component_gap_count[topic] = component_gap_count.get(topic, 0) + 1

        for gap in gaps:
            priority_score = self._calculate_priority_score(gap, analysis, component_gap_count)

            if priority_score >= 0.7:
                gap.priority = "high"
            elif priority_score >= 0.4:
                gap.priority = "medium"
            else:
                gap.priority = "low"

        gaps.sort(key=lambda g: self._priority_to_num(g.priority), reverse=True)
        return gaps

    def _calculate_priority_score(
        self, gap: KnowledgeGap, analysis: AnalysisResult, gap_counts: dict
    ) -> float:
        """Calculate a priority score from 0.0 to 1.0 for a gap."""
        score = 0.0

        if gap.gap_type == "missing":
            score += 0.4
        elif gap.gap_type == "outdated":
            score += 0.3
        elif gap.gap_type == "conflicting":
            score += 0.35
        elif gap.gap_type == "uncertain":
            score += 0.2

        if gap.related_knowledge:
            max_conf = max(r.get("confidence", 0) for r in gap.related_knowledge)
            score += (1.0 - max_conf) * 0.2
        else:
            score += 0.2

        if analysis.complexity_score > 0.7:
            score += 0.15
        elif analysis.complexity_score > 0.4:
            score += 0.1

        if analysis.research_needed:
            score += 0.1

        component_count = gap_counts.get(gap.topic, 1)
        if component_count > 2:
            score += 0.1

        return min(score, 1.0)

    def _priority_to_num(self, priority: str) -> int:
        """Convert priority string to numeric for sorting."""
        return {"high": 3, "medium": 2, "low": 1}.get(priority, 0)

    def _build_research_plan(self, gaps: list[KnowledgeGap]) -> list[dict]:
        """Build an ordered research plan from prioritized gaps."""
        plan = []

        high_gaps = [g for g in gaps if g.priority == "high"]
        medium_gaps = [g for g in gaps if g.priority == "medium"]
        low_gaps = [g for g in gaps if g.priority == "low"]

        step = 1
        for gap in high_gaps:
            plan.append({
                "step": step,
                "topic": gap.topic,
                "gap_type": gap.gap_type,
                "priority": "high",
                "search_queries": gap.search_queries[:3],
                "rationale": f"Critical gap for {gap.gap_type} knowledge",
            })
            step += 1

        for gap in medium_gaps:
            plan.append({
                "step": step,
                "topic": gap.topic,
                "gap_type": gap.gap_type,
                "priority": "medium",
                "search_queries": gap.search_queries[:2],
                "rationale": f"Important for completeness ({gap.gap_type})",
            })
            step += 1

        for gap in low_gaps:
            plan.append({
                "step": step,
                "topic": gap.topic,
                "gap_type": gap.gap_type,
                "priority": "low",
                "search_queries": gap.search_queries[:1],
                "rationale": f"Supplementary information ({gap.gap_type})",
            })
            step += 1

        return plan
