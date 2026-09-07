"""ResearchTrainingSystem — teaches research capabilities via Learning API.

Uses structured experiences to teach:
- When to research
- How to formulate search queries
- How to find authoritative sources
- How to use multiple sources
- How to extract claims
- How to detect contradictions
- How to evaluate evidence
- How to determine freshness
- How to synthesize information
- How to answer clearly
- How to present sources
- How to communicate uncertainty
- How to reuse learned knowledge

All teaching uses the Learning API.
All validation uses /api/chat or /v1/chat.
No direct DB training.
No test-specific hardcoding.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ResearchExperience:
    """A structured research experience for learning."""
    task: str = ""
    goal: str = ""
    context: dict = field(default_factory=dict)
    observations: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    attempts: list[str] = field(default_factory=list)
    result: dict = field(default_factory=dict)
    success: bool = False
    evidence: list[dict] = field(default_factory=list)
    reflection: str = ""
    metadata: dict = field(default_factory=dict)


class ResearchTrainingSystem:
    """Teaches research capabilities through structured experiences.

    Uses the Learning API for all teaching.
    Does NOT directly insert into database.
    Does NOT create test-specific hardcoded questions.
    """

    def __init__(self, api_base_url: str = "http://127.0.0.1:5000"):
        self.api_base_url = api_base_url
        self._session = None

    def _get_session(self):
        """Get or create HTTP session."""
        if not self._session:
            import requests
            self._session = requests.Session()
        return self._session

    def teach_research_decision(self, question: str, should_research: bool,
                                 reason: str, context: dict = None) -> bool:
        """Teach when to research.

        Args:
            question: The question that triggered the decision
            should_research: Whether research was needed
            reason: Why research was needed/not needed
            context: Additional context

        Returns:
            True if teaching was successful
        """
        experience = ResearchExperience(
            task=f"Research decision for: {question[:100]}",
            goal="research_decision",
            context=context or {},
            observations=[
                f"Question: {question}",
                f"Should research: {should_research}",
                f"Reason: {reason}",
            ],
            actions=["decide_research"],
            result={
                "decision": "research" if should_research else "no_research",
                "reason": reason,
            },
            success=True,
            reflection=f"Decision: {'research' if should_research else 'no_research'} - {reason}",
        )

        return self._submit_experience(experience)

    def teach_query_generation(self, question: str, queries: list[str],
                                strategy: str = "default") -> bool:
        """Teach how to generate search queries.

        Args:
            question: Original question
            queries: Generated queries
            strategy: Query generation strategy used

        Returns:
            True if teaching was successful
        """
        experience = ResearchExperience(
            task=f"Query generation for: {question[:100]}",
            goal="query_generation",
            context={"strategy": strategy},
            observations=[
                f"Question: {question}",
                f"Generated queries: {queries}",
                f"Strategy: {strategy}",
            ],
            actions=["generate_queries"],
            result={
                "queries": queries,
                "strategy": strategy,
            },
            success=True,
            reflection=f"Generated {len(queries)} queries using {strategy}",
        )

        return self._submit_experience(experience)

    def teach_source_evaluation(self, url: str, title: str,
                                 reliability: float, relevance: float,
                                 reason: str) -> bool:
        """Teach how to evaluate sources.

        Args:
            url: Source URL
            title: Source title
            reliability: Evaluated reliability
            relevance: Evaluated relevance
            reason: Evaluation reason

        Returns:
            True if teaching was successful
        """
        experience = ResearchExperience(
            task=f"Source evaluation: {title[:50]}",
            goal="source_evaluation",
            context={"url": url, "title": title},
            observations=[
                f"URL: {url}",
                f"Title: {title}",
                f"Reliability: {reliability}",
                f"Relevance: {relevance}",
                f"Reason: {reason}",
            ],
            actions=["evaluate_source"],
            result={
                "reliability": reliability,
                "relevance": relevance,
                "reason": reason,
            },
            success=True,
            reflection=f"Source evaluated: reliability={reliability:.2f}, relevance={relevance:.2f}",
        )

        return self._submit_experience(experience)

    def teach_claim_extraction(self, text: str, claims: list[str],
                                source_url: str = "") -> bool:
        """Teach how to extract claims from text.

        Args:
            text: Source text
            claims: Extracted claims
            source_url: Source URL

        Returns:
            True if teaching was successful
        """
        experience = ResearchExperience(
            task=f"Claim extraction from: {source_url[:50] if source_url else 'text'}",
            goal="claim_extraction",
            context={"source_url": source_url, "text_length": len(text)},
            observations=[
                f"Text length: {len(text)}",
                f"Extracted claims: {len(claims)}",
                f"Claims: {claims[:3]}",
            ],
            actions=["extract_claims"],
            result={
                "claims": claims,
                "count": len(claims),
            },
            success=True,
            reflection=f"Extracted {len(claims)} claims from text",
        )

        return self._submit_experience(experience)

    def teach_contradiction_detection(self, claims: list[str],
                                       contradictions: list[dict]) -> bool:
        """Teach how to detect contradictions.

        Args:
            claims: Claims to check
            contradictions: Detected contradictions

        Returns:
            True if teaching was successful
        """
        experience = ResearchExperience(
            task=f"Contradiction detection for {len(claims)} claims",
            goal="contradiction_detection",
            context={"claims": claims[:5], "contradictions": contradictions},
            observations=[
                f"Claims checked: {len(claims)}",
                f"Contradictions found: {len(contradictions)}",
                f"Contradictions: {contradictions[:2]}",
            ],
            actions=["detect_contradictions"],
            result={
                "contradictions": contradictions,
                "count": len(contradictions),
            },
            success=True,
            reflection=f"Detected {len(contradictions)} contradictions among {len(claims)} claims",
        )

        return self._submit_experience(experience)

    def teach_evidence_comparison(self, claims: list[dict],
                                   comparison_result: dict) -> bool:
        """Teach how to compare evidence.

        Args:
            claims: Claims to compare
            comparison_result: Comparison result

        Returns:
            True if teaching was successful
        """
        experience = ResearchExperience(
            task=f"Evidence comparison for {len(claims)} claims",
            goal="evidence_comparison",
            context={"claims": claims[:5], "result": comparison_result},
            observations=[
                f"Claims compared: {len(claims)}",
                f"Result: {comparison_result}",
            ],
            actions=["compare_evidence"],
            result=comparison_result,
            success=True,
            reflection=f"Compared {len(claims)} claims",
        )

        return self._submit_experience(experience)

    def teach_freshness_handling(self, question: str, freshness: str,
                                  should_reverify: bool) -> bool:
        """Teach how to handle freshness.

        Args:
            question: Original question
            freshness: Detected freshness requirement
            should_reverify: Whether re-verification is needed

        Returns:
            True if teaching was successful
        """
        experience = ResearchExperience(
            task=f"Freshness handling for: {question[:100]}",
            goal="freshness_handling",
            context={"freshness": freshness, "should_reverify": should_reverify},
            observations=[
                f"Question: {question}",
                f"Freshness: {freshness}",
                f"Should reverify: {should_reverify}",
            ],
            actions=["handle_freshness"],
            result={
                "freshness": freshness,
                "should_reverify": should_reverify,
            },
            success=True,
            reflection=f"Freshness: {freshness}, Reverify: {should_reverify}",
        )

        return self._submit_experience(experience)

    def teach_knowledge_synthesis(self, question: str, evidence: list[dict],
                                   synthesized_answer: str,
                                   confidence: float) -> bool:
        """Teach how to synthesize knowledge.

        Args:
            question: Original question
            evidence: Evidence to synthesize
            synthesized_answer: The synthesized answer
            confidence: Confidence in the answer

        Returns:
            True if teaching was successful
        """
        experience = ResearchExperience(
            task=f"Knowledge synthesis for: {question[:100]}",
            goal="knowledge_synthesis",
            context={"evidence_count": len(evidence), "confidence": confidence},
            observations=[
                f"Question: {question}",
                f"Evidence items: {len(evidence)}",
                f"Confidence: {confidence}",
                f"Answer length: {len(synthesized_answer)}",
            ],
            actions=["synthesize_knowledge"],
            result={
                "answer": synthesized_answer[:200],
                "confidence": confidence,
            },
            success=True,
            reflection=f"Synthesized answer with confidence {confidence:.2f}",
        )

        return self._submit_experience(experience)

    def teach_response_presentation(self, question: str, response: str,
                                     language: str, detail_level: str) -> bool:
        """Teach how to present responses.

        Args:
            question: Original question
            response: Presented response
            language: Response language
            detail_level: Detail level

        Returns:
            True if teaching was successful
        """
        experience = ResearchExperience(
            task=f"Response presentation for: {question[:100]}",
            goal="response_presentation",
            context={"language": language, "detail_level": detail_level},
            observations=[
                f"Question: {question}",
                f"Language: {language}",
                f"Detail level: {detail_level}",
                f"Response length: {len(response)}",
            ],
            actions=["present_response"],
            result={
                "response": response[:200],
                "language": language,
                "detail_level": detail_level,
            },
            success=True,
            reflection=f"Presented response in {language} with {detail_level} detail",
        )

        return self._submit_experience(experience)

    def teach_knowledge_reuse(self, question: str, reused_knowledge: dict,
                               new_answer: str) -> bool:
        """Teach how to reuse learned knowledge.

        Args:
            question: New question
            reused_knowledge: Knowledge that was reused
            new_answer: Answer generated from reused knowledge

        Returns:
            True if teaching was successful
        """
        experience = ResearchExperience(
            task=f"Knowledge reuse for: {question[:100]}",
            goal="knowledge_reuse",
            context={"reused_knowledge": reused_knowledge},
            observations=[
                f"Question: {question}",
                f"Reused knowledge: {reused_knowledge.get('concept', 'unknown')}",
                f"Answer length: {len(new_answer)}",
            ],
            actions=["reuse_knowledge"],
            result={
                "answer": new_answer[:200],
                "reused": True,
            },
            success=True,
            reflection=f"Reused knowledge for {question[:50]}",
        )

        return self._submit_experience(experience)

    def teach_uncertainty_handling(self, question: str, uncertainty_reason: str,
                                   uncertainty_response: str) -> bool:
        """Teach how to handle uncertainty.

        Args:
            question: Original question
            uncertainty_reason: Why there is uncertainty
            uncertainty_response: Response communicating uncertainty

        Returns:
            True if teaching was successful
        """
        experience = ResearchExperience(
            task=f"Uncertainty handling for: {question[:100]}",
            goal="uncertainty_handling",
            context={"reason": uncertainty_reason},
            observations=[
                f"Question: {question}",
                f"Uncertainty reason: {uncertainty_reason}",
                f"Response length: {len(uncertainty_response)}",
            ],
            actions=["handle_uncertainty"],
            result={
                "response": uncertainty_response[:200],
                "reason": uncertainty_reason,
            },
            success=True,
            reflection=f"Handled uncertainty: {uncertainty_reason}",
        )

        return self._submit_experience(experience)

    def _submit_experience(self, experience: ResearchExperience) -> bool:
        """Submit an experience to the Learning API."""
        try:
            session = self._get_session()
            url = f"{self.api_base_url}/learning/experience"

            data = {
                "task": experience.task,
                "goal": experience.goal,
                "context": experience.context,
                "observations": experience.observations,
                "actions": experience.actions,
                "tools_used": experience.tools_used,
                "errors": experience.errors,
                "attempts": experience.attempts,
                "result": experience.result,
                "success": experience.success,
                "evidence": experience.evidence,
                "reflection": experience.reflection,
                "metadata": experience.metadata,
            }

            response = session.post(url, json=data, timeout=10)
            if response.status_code == 200:
                logger.debug(f"Experience submitted: {experience.goal}")
                return True
            else:
                logger.warning(f"Experience submission failed: {response.status_code}")
                return False

        except Exception as e:
            logger.warning(f"Failed to submit experience: {e}")
            return False

    def batch_teach(self, experiences: list[ResearchExperience]) -> int:
        """Submit multiple experiences.

        Returns:
            Number of successfully submitted experiences
        """
        success_count = 0
        for exp in experiences:
            if self._submit_experience(exp):
                success_count += 1
        return success_count
