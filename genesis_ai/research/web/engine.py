"""WebResearchEngine — modular research orchestrator for Phase 3.

Separate from CognitiveEngine, ContextManager, LearningEngine.
The Cognitive/Decision layer decides WHEN research is needed.
This engine executes the research pipeline.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ResearchPlan:
    """Structured research plan."""
    research_id: str = ""
    original_question: str = ""
    user_goal: str = ""
    knowledge_gap: str = ""
    sub_questions: list[str] = field(default_factory=list)
    required_claims: list[str] = field(default_factory=list)
    freshness_requirement: str = "stable"  # stable, recent, current
    source_requirements: list[str] = field(default_factory=list)
    verification_level: str = "standard"  # basic, standard, rigorous
    completion_condition: str = "sufficient_evidence"
    created_at: float = field(default_factory=time.time)


@dataclass
class CollectedSource:
    """A collected web source with metadata."""
    source_id: str = ""
    url: str = ""
    title: str = ""
    source_type: str = "web"
    publisher: str = ""
    domain: str = ""
    retrieved_at: float = field(default_factory=time.time)
    publication_date: str = ""
    update_date: str = ""
    reliability: float = 0.5
    relevance: float = 0.0
    snippet: str = ""
    full_text: str = ""


@dataclass
class ExtractedClaim:
    """An individual claim extracted from a source."""
    claim_id: str = ""
    concept: str = ""
    statement: str = ""
    source_id: str = ""
    evidence: str = ""
    confidence: float = 0.5
    freshness: str = "unknown"
    created_at: float = field(default_factory=time.time)
    last_verified: float = 0.0
    status: str = "UNCERTAIN"  # VERIFIED, PROBABLE, UNCERTAIN, CONTRADICTED, OUTDATED


@dataclass
class EvidenceComparison:
    """Result of comparing evidence across sources."""
    claim: str = ""
    supporting_count: int = 0
    contradicting_count: int = 0
    agreement_ratio: float = 0.0
    avg_reliability: float = 0.0
    detection: str = "unknown"  # agreement, contradiction, incomplete, outdated
    confidence: float = 0.0


@dataclass
class VerifiedKnowledge:
    """Verified knowledge after research synthesis."""
    concept: str = ""
    claim: str = ""
    relationships: list[str] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    confidence: float = 0.5
    sources: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_verified: float = 0.0
    freshness: str = "stable"
    scope: str = ""
    exceptions: list[str] = field(default_factory=list)
    status: str = "UNCERTAIN"
    usage_count: int = 0


@dataclass
class ResearchResult:
    """Complete research result."""
    plan: Optional[ResearchPlan] = None
    sources: list[CollectedSource] = field(default_factory=list)
    claims: list[ExtractedClaim] = field(default_factory=list)
    comparisons: list[EvidenceComparison] = field(default_factory=list)
    verified_knowledge: list[VerifiedKnowledge] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    research_duration: float = 0.0
    queries_used: list[str] = field(default_factory=list)
    success: bool = False
    error: Optional[str] = None


class WebResearchEngine:
    """Modular research orchestrator.

    Separated from CognitiveEngine, ContextManager, LearningEngine.
    Executes the research pipeline when the decision layer calls for it.

    Pipeline:
    1. Create research plan
    2. Generate queries
    3. Search web
    4. Collect sources
    5. Evaluate sources
    6. Extract claims
    7. Compare evidence
    8. Detect contradictions
    9. Verify claims
    10. Synthesize knowledge
    """

    def __init__(self, db=None):
        self.db = db
        self._search_engine = None
        self._source_manager = None
        self._extraction_engine = None

        # Lazy load to avoid circular imports
        self._init_engines()

    def _init_engines(self):
        """Initialize dependent engines."""
        try:
            from genesis_ai.research.search.engine import WebSearchEngine
            self._search_engine = WebSearchEngine()
        except Exception as e:
            logger.warning(f"Failed to init WebSearchEngine: {e}")

        try:
            from genesis_ai.research.sources.engine import SourceManager
            if self.db:
                self._source_manager = SourceManager(self.db)
        except Exception as e:
            logger.warning(f"Failed to init SourceManager: {e}")

        try:
            from genesis_ai.research.extraction.engine import InformationExtraction
            self._extraction_engine = InformationExtraction()
        except Exception as e:
            logger.warning(f"Failed to init InformationExtraction: {e}")

    def research(self, question: str, knowledge_gap: str = "",
                 user_goal: str = "", freshness: str = "stable",
                 verification_level: str = "standard") -> ResearchResult:
        """Execute full research pipeline.

        Args:
            question: The original user question
            knowledge_gap: What information is missing
            user_goal: What the user wants to achieve
            freshness: How fresh the information needs to be
            verification_level: How thorough the verification should be

        Returns:
            ResearchResult with all findings
        """
        start_time = time.time()
        result = ResearchResult()

        try:
            # Step 1: Create research plan
            plan = self._create_research_plan(
                question, knowledge_gap, user_goal, freshness, verification_level
            )
            result.plan = plan

            # Step 2: Generate search queries
            queries = self._generate_queries(plan)
            result.queries_used = queries

            # Step 3: Search web
            raw_sources = self._search_web(queries)

            # Step 4: Collect and evaluate sources
            sources = self._collect_sources(raw_sources, plan)
            result.sources = sources

            # Step 5: Extract claims
            claims = self._extract_claims(sources)
            # Light relevance filter: remove claims with zero word overlap with query.
            # Only filter out clearly unrelated claims — let the composer handle
            # deeper relevance. For short queries, require just 1 word overlap.
            query_words = set(re.findall(r'\b[a-z]{3,}\b', question.lower()))
            query_words -= {'what', 'which', 'where', 'when', 'how', 'who', 'why',
                           'does', 'do', 'did', 'is', 'are', 'was', 'were', 'the',
                           'and', 'for', 'that', 'this', 'with', 'can', 'tell',
                           'about', 'have', 'has', 'will', 'would', 'make', 'write'}
            if query_words:
                claims = [c for c in claims if self._claim_matches_query(c, query_words)]
            result.claims = claims

            # Step 6: Compare evidence
            comparisons = self._compare_evidence(claims)
            result.comparisons = comparisons

            # Step 7: Detect contradictions
            contradictions = self._detect_contradictions(claims, comparisons)
            result.contradictions = contradictions

            # Step 8: Verify claims
            verified = self._verify_claims(claims, sources, comparisons)

            # Step 9: Synthesize knowledge
            knowledge = self._synthesize_knowledge(verified, sources, plan)
            result.verified_knowledge = knowledge

            # Step 10: Store verified knowledge for future use
            self._store_research_knowledge(knowledge)

            # Calculate overall confidence
            result.confidence = self._calculate_confidence(
                sources, claims, comparisons, contradictions
            )

            result.success = True
            result.research_duration = time.time() - start_time

            logger.info(
                f"Research completed: {len(sources)} sources, "
                f"{len(claims)} claims, confidence={result.confidence:.2f}"
            )

        except Exception as e:
            result.error = str(e)
            result.research_duration = time.time() - start_time
            logger.error(f"Research failed: {e}")

        return result

    def _create_research_plan(self, question: str, knowledge_gap: str,
                               user_goal: str, freshness: str,
                               verification_level: str) -> ResearchPlan:
        """Create a structured research plan."""
        plan = ResearchPlan(
            research_id=str(uuid.uuid4())[:8],
            original_question=question,
            user_goal=user_goal or "answer_question",
            knowledge_gap=knowledge_gap or question,
            freshness_requirement=freshness,
            verification_level=verification_level,
        )

        # Generate sub-questions
        plan.sub_questions = self._generate_sub_questions(question, knowledge_gap)

        # Determine source requirements
        plan.source_requirements = self._determine_source_requirements(
            question, freshness, verification_level
        )

        # Set completion condition
        if verification_level == "rigorous":
            plan.completion_condition = "multiple_agreeing_sources"
        elif verification_level == "standard":
            plan.completion_condition = "sufficient_evidence"
        else:
            plan.completion_condition = "any_source"

        return plan

    def _generate_sub_questions(self, question: str, knowledge_gap: str) -> list[str]:
        """Generate sub-questions from the main question."""
        sub_questions = []
        q_lower = question.lower()

        # Structural decomposition (not content-specific)
        # If it's a comparison, split into parts
        if any(w in q_lower for w in ["vs", "versus", "compared", "difference", "better"]):
            sub_questions.append(f"What are the key features of each option?")
            sub_questions.append(f"What are the pros and cons?")

        # If it's a how-to, break into steps
        if any(w in q_lower for w in ["how to", "steps", "process", "guide"]):
            sub_questions.append(f"What are the prerequisites?")
            sub_questions.append(f"What is the step-by-step process?")

        # If it's a what-is, get definition + examples
        if any(w in q_lower for w in ["what is", "what are", "define", "explain"]):
            sub_questions.append(f"What is the definition?")
            sub_questions.append(f"What are examples?")

        # Generic sub-questions
        if not sub_questions:
            sub_questions.append(question)
            sub_questions.append(f"Key facts about this topic")

        return sub_questions[:5]

    def _determine_source_requirements(self, question: str, freshness: str,
                                        verification_level: str) -> list[str]:
        """Determine what kinds of sources are needed."""
        requirements = []

        # Always want at least one source
        requirements.append("any_relevant")

        # Freshness requirements
        if freshness == "current":
            requirements.append("recent_publication")
        elif freshness == "recent":
            requirements.append("updated_content")

        # Verification level
        if verification_level == "rigorous":
            requirements.append("authoritative_source")
            requirements.append("multiple_sources")
        elif verification_level == "standard":
            requirements.append("reliable_source")

        # Topic-based source requirements (structural, not content-specific)
        q_lower = question.lower()
        if any(w in q_lower for w in ["official", "documentation", "docs"]):
            requirements.append("official_documentation")
        if any(w in q_lower for w in ["research", "study", "paper"]):
            requirements.append("academic_source")
        if any(w in q_lower for w in ["price", "cost", "buy"]):
            requirements.append("current_pricing")

        return requirements

    def _generate_queries(self, plan: ResearchPlan) -> list[str]:
        """Generate search queries from the research plan."""
        queries = []
        question = plan.original_question

        # Primary query - the original question
        queries.append(question)

        # Focused query - based on knowledge gap
        if plan.knowledge_gap and plan.knowledge_gap != question:
            queries.append(plan.knowledge_gap)

        # Sub-question queries
        for sq in plan.sub_questions[:2]:
            if sq not in queries:
                queries.append(sq)

        # Freshness query if needed
        if plan.freshness_requirement == "current":
            year = str(int(time.time() // (365.25 * 24 * 3600)) + 1970)
            queries.append(f"{question} {year}")

        # Official source query if needed
        if "official_documentation" in plan.source_requirements:
            queries.append(f"{question} official documentation")

        return queries[:5]

    def _search_web(self, queries: list[str]) -> list[dict]:
        """Search the web using multiple queries."""
        if not self._search_engine:
            return []

        all_results = []
        seen_urls = set()

        for query in queries[:3]:  # Limit to 3 queries
            try:
                results = self._search_engine.search(query, max_results=5)
                for r in results:
                    if r.url not in seen_urls:
                        seen_urls.add(r.url)
                        all_results.append({
                            "title": r.title,
                            "url": r.url,
                            "snippet": r.snippet,
                            "source_name": r.source_name,
                        })
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                logger.warning(f"Search failed for query '{query}': {e}")

        return all_results

    def _collect_sources(self, raw_results: list[dict],
                          plan: ResearchPlan) -> list[CollectedSource]:
        """Collect and evaluate sources from search results."""
        sources = []

        for i, result in enumerate(raw_results[:10]):  # Limit to 10 sources
            source = CollectedSource(
                source_id=f"src_{i}",
                url=result.get("url", ""),
                title=result.get("title", ""),
                source_type=self._classify_source_type(result.get("url", "")),
                publisher=result.get("source_name", ""),
                domain=self._extract_domain(result.get("url", "")),
                snippet=result.get("snippet", ""),
            )

            # Evaluate reliability
            source.reliability = self._evaluate_source_reliability(source)

            # Evaluate relevance
            source.relevance = self._evaluate_source_relevance(
                source, plan.original_question
            )

            # Try to extract full text for important sources
            if source.reliability >= 0.6 and source.relevance >= 0.5:
                try:
                    full_text = self._search_engine.extract_text_from_url(source.url)
                    if full_text:
                        source.full_text = full_text[:5000]  # Limit size
                except Exception:
                    pass

            sources.append(source)

        # Sort by combined reliability + relevance
        sources.sort(key=lambda s: s.reliability * 0.5 + s.relevance * 0.5, reverse=True)

        return sources[:7]  # Return top 7 sources

    def _extract_claims(self, sources: list[CollectedSource]) -> list[ExtractedClaim]:
        """Extract individual claims from sources."""
        claims = []

        for source in sources:
            text = source.full_text or source.snippet
            if not text:
                continue

            # Use extraction engine if available
            if self._extraction_engine:
                facts = self._extraction_engine.extract_facts(text)
                for fact in facts[:5]:  # Limit per source
                    claim = ExtractedClaim(
                        claim_id=f"claim_{source.source_id}_{len(claims)}",
                        concept=self._extract_concept(fact.claim),
                        statement=fact.claim,
                        source_id=source.source_id,
                        evidence=fact.evidence,
                        confidence=fact.confidence * source.reliability,
                        freshness=self._estimate_freshness(source),
                    )
                    claims.append(claim)
            else:
                # Fallback: treat snippet as a claim
                if source.snippet and len(source.snippet) > 30:
                    claim = ExtractedClaim(
                        claim_id=f"claim_{source.source_id}_{len(claims)}",
                        concept=self._extract_concept(source.snippet),
                        statement=source.snippet,
                        source_id=source.source_id,
                        evidence=source.snippet,
                        confidence=0.4 * source.reliability,
                        freshness=self._estimate_freshness(source),
                    )
                    claims.append(claim)

        return claims

    def _claim_matches_query(self, claim: ExtractedClaim, query_words: set) -> bool:
        """Check if a claim is relevant to the query.

        Very relaxed matching: any 1 word overlap is sufficient.
        The composer handles deeper relevance filtering.
        """
        if not query_words:
            return True
        claim_words = set(re.findall(r'\b[a-z]{3,}\b', (claim.statement or '').lower()))
        claim_words.update(re.findall(r'\b[a-z]{3,}\b', (claim.concept or '').lower()))
        overlap = query_words & claim_words
        return len(overlap) >= 1

    def _compare_evidence(self, claims: list[ExtractedClaim]) -> list[EvidenceComparison]:
        """Compare evidence across sources."""
        comparisons = []

        # Group claims by concept
        concept_claims = {}
        for claim in claims:
            key = claim.concept.lower()[:50]
            if key not in concept_claims:
                concept_claims[key] = []
            concept_claims[key].append(claim)

        # Compare within each concept group
        for concept, group_claims in concept_claims.items():
            if len(group_claims) < 2:
                continue

            comparison = EvidenceComparison(claim=concept)

            # Simple comparison based on statement similarity
            for i, c1 in enumerate(group_claims):
                for c2 in group_claims[i+1:]:
                    similarity = self._calculate_statement_similarity(
                        c1.statement, c2.statement
                    )
                    if similarity > 0.7:
                        comparison.supporting_count += 1
                    elif similarity < 0.3:
                        # Check for negation patterns
                        if self._has_contradiction(c1.statement, c2.statement):
                            comparison.contradicting_count += 1
                        else:
                            comparison.supporting_count += 1

            total = comparison.supporting_count + comparison.contradicting_count
            if total > 0:
                comparison.agreement_ratio = comparison.supporting_count / total

            # Calculate average reliability
            reliabilities = [c.confidence for c in group_claims]
            comparison.avg_reliability = sum(reliabilities) / len(reliabilities)

            # Determine detection
            if comparison.contradicting_count > 0:
                comparison.detection = "contradiction"
            elif comparison.supporting_count > 1:
                comparison.detection = "agreement"
            else:
                comparison.detection = "incomplete"

            comparison.confidence = min(comparison.avg_reliability, 0.9)
            comparisons.append(comparison)

        return comparisons

    def _detect_contradictions(self, claims: list[ExtractedClaim],
                                comparisons: list[EvidenceComparison]) -> list[dict]:
        """Detect contradictions between claims."""
        contradictions = []

        for comp in comparisons:
            if comp.detection == "contradiction":
                contradictions.append({
                    "topic": comp.claim,
                    "severity": "moderate" if comp.contradicting_count == 1 else "high",
                    "supporting": comp.supporting_count,
                    "contradicting": comp.contradicting_count,
                    "resolution": "needs_further_research",
                })

        return contradictions

    def _verify_claims(self, claims: list[ExtractedClaim],
                        sources: list[CollectedSource],
                        comparisons: list[EvidenceComparison]) -> list[ExtractedClaim]:
        """Verify claims based on evidence quality."""
        verified = []

        for claim in claims:
            # Find the source for this claim
            source = next((s for s in sources if s.source_id == claim.source_id), None)
            if not source:
                continue

            # Verification logic
            if source.reliability >= 0.8 and claim.confidence >= 0.7:
                claim.status = "VERIFIED"
            elif source.reliability >= 0.6 and claim.confidence >= 0.5:
                claim.status = "PROBABLE"
            elif claim.confidence < 0.3:
                claim.status = "UNCERTAIN"
            else:
                claim.status = "UNCERTAIN"

            # Check for contradictions
            for comp in comparisons:
                if comp.detection == "contradiction" and comp.claim in claim.concept:
                    claim.status = "CONTRADICTED"
                    break

            # Check freshness
            if claim.freshness == "outdated":
                claim.status = "OUTDATED"

            claim.last_verified = time.time()
            verified.append(claim)

        return verified

    def _synthesize_knowledge(self, verified_claims: list[ExtractedClaim],
                               sources: list[CollectedSource],
                               plan: ResearchPlan) -> list[VerifiedKnowledge]:
        """Synthesize verified claims into structured knowledge."""
        knowledge = []

        # Group verified claims by concept
        concept_knowledge = {}
        for claim in verified_claims:
            if claim.status in ("VERIFIED", "PROBABLE"):
                key = claim.concept.lower()[:50]
                if key not in concept_knowledge:
                    concept_knowledge[key] = {
                        "concept": claim.concept,
                        "claims": [],
                        "sources": set(),
                        "confidences": [],
                    }
                concept_knowledge[key]["claims"].append(claim)
                concept_knowledge[key]["sources"].add(claim.source_id)
                concept_knowledge[key]["confidences"].append(claim.confidence)

        # Create VerifiedKnowledge for each concept
        for key, data in concept_knowledge.items():
            # Pick the best claim (highest confidence)
            best_claim = max(data["claims"], key=lambda c: c.confidence)

            knowledge.append(VerifiedKnowledge(
                concept=data["concept"],
                claim=best_claim.statement,
                evidence=[{
                    "claim_id": c.claim_id,
                    "statement": c.statement,
                    "source_id": c.source_id,
                    "confidence": c.confidence,
                } for c in data["claims"][:3]],
                confidence=sum(data["confidences"]) / len(data["confidences"]),
                sources=list(data["sources"]),
                freshness=best_claim.freshness,
                status=best_claim.status,
            ))

        return knowledge

    def _calculate_confidence(self, sources: list[CollectedSource],
                               claims: list[ExtractedClaim],
                               comparisons: list[EvidenceComparison],
                               contradictions: list[dict]) -> float:
        """Calculate overall research confidence."""
        if not sources:
            return 0.0

        # Source quality score
        source_score = sum(s.reliability for s in sources) / len(sources)

        # Claim quality score
        claim_score = 0.0
        if claims:
            verified_count = sum(1 for c in claims if c.status in ("VERIFIED", "PROBABLE"))
            claim_score = verified_count / len(claims)

        # Agreement score
        agreement_score = 1.0
        if contradictions:
            agreement_score = max(0.3, 1.0 - len(contradictions) * 0.2)

        # Evidence quantity bonus
        quantity_bonus = min(0.2, len(sources) * 0.03)

        confidence = (
            source_score * 0.3 +
            claim_score * 0.3 +
            agreement_score * 0.2 +
            quantity_bonus
        )

        return max(0.1, min(0.95, confidence))

    # ── Helper Methods ────────────────────────────────────────────────

    def _classify_source_type(self, url: str) -> str:
        """Classify source type from URL."""
        url_lower = url.lower()
        if "gov" in url_lower:
            return "government"
        if "edu" in url_lower:
            return "academic"
        if "org" in url_lower:
            return "organization"
        if "github.com" in url_lower:
            return "code_repository"
        if "stackoverflow.com" in url_lower:
            return "qa_forum"
        if "wikipedia.org" in url_lower:
            return "encyclopedia"
        if "medium.com" in url_lower:
            return "blog_platform"
        if "docs." in url_lower or "documentation" in url_lower:
            return "official_documentation"
        return "web"

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""

    def _evaluate_source_reliability(self, source: CollectedSource) -> float:
        """Evaluate source reliability based on structural features."""
        score = 0.5  # baseline

        # Domain-based scoring (structural, not content-specific)
        domain = source.domain.lower()
        if source.source_type == "government":
            score += 0.3
        elif source.source_type == "academic":
            score += 0.25
        elif source.source_type == "official_documentation":
            score += 0.3
        elif source.source_type == "code_repository":
            score += 0.2
        elif source.source_type == "encyclopedia":
            score += 0.2
        elif source.source_type == "qa_forum":
            score += 0.15
        elif source.source_type == "blog_platform":
            score += 0.0

        # URL structure indicators
        if ".edu" in domain or ".gov" in domain:
            score += 0.1
        if ".org" in domain:
            score += 0.05

        # Snippet quality indicators
        if source.snippet:
            if len(source.snippet) > 100:
                score += 0.05
            if any(w in source.snippet.lower() for w in ["according to", "research shows", "study"]):
                score += 0.05

        return max(0.1, min(0.95, score))

    def _evaluate_source_relevance(self, source: CollectedSource,
                                    question: str) -> float:
        """Evaluate source relevance to the question."""
        if not source.snippet and not source.title:
            return 0.3

        # Word overlap between question and source
        question_words = set(question.lower().split())
        source_text = f"{source.title} {source.snippet}".lower()
        source_words = set(source_text.split())

        if not question_words:
            return 0.3

        overlap = question_words & source_words
        relevance = len(overlap) / len(question_words)

        # Boost for matching title
        title_words = set(source.title.lower().split())
        title_overlap = question_words & title_words
        if title_overlap:
            relevance += 0.2

        return max(0.1, min(0.95, relevance))

    def _extract_concept(self, text: str) -> str:
        """Extract the main concept from text."""
        # Simple extraction: first noun phrase
        import re
        words = text.split()
        if len(words) <= 5:
            return text
        # Return first few words as concept
        return " ".join(words[:5])

    def _estimate_freshness(self, source: CollectedSource) -> str:
        """Estimate content freshness."""
        # If no dates available, assume stable
        if not source.publication_date and not source.update_date:
            return "stable"

        # Try to parse dates
        try:
            if source.update_date:
                # Parse update date
                return "recent"
            if source.publication_date:
                return "stable"
        except Exception:
            pass

        return "stable"

    def _calculate_statement_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity between two statements."""
        words1 = set(s1.lower().split())
        words2 = set(s2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0

    def _has_contradiction(self, s1: str, s2: str) -> bool:
        """Check if two statements contradict each other."""
        negation_patterns = [
            r'\bnot\b', r'\bnever\b', r'\bno\b', r'\bneither\b',
            r'\bdoes not\b', r'\bis not\b', r'\bwas not\b',
        ]

        s1_lower = s1.lower()
        s2_lower = s2.lower()

        s1_negated = any(re.search(p, s1_lower) for p in negation_patterns)
        s2_negated = any(re.search(p, s2_lower) for p in negation_patterns)

        # If one is negated and the other isn't, and they share key words
        if s1_negated != s2_negated:
            words1 = set(re.findall(r'\b[a-z]{4,}\b', s1_lower))
            words2 = set(re.findall(r'\b[a-z]{4,}\b', s2_lower))
            overlap = words1 & words2
            if len(overlap) >= 2:
                return True

        return False

    def _store_research_knowledge(self, knowledge: list[VerifiedKnowledge]):
        """Store verified research knowledge in learned_knowledge table."""
        if not self.db or not knowledge:
            return
        import time as _time
        for vk in knowledge:
            if vk.status not in ("VERIFIED", "PROBABLE"):
                continue
            try:
                self.db.execute(
                    """INSERT INTO learned_knowledge
                       (concept, claim, source, evidence, confidence,
                        created_at, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        vk.concept,
                        vk.claim,
                        "web_research",
                        json.dumps(vk.evidence[:3] if vk.evidence else []),
                        vk.confidence,
                        _time.time(),
                        vk.status,
                    ),
                )
            except Exception:
                pass  # best-effort storage
