"""Verification engine for evaluating claims against evidence sources."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from genesis_ai.database.db import DatabaseManager
from genesis_ai.config.settings import CONFIDENCE_THRESHOLD


STATUS_VERIFIED = "VERIFIED"
STATUS_PROBABLE = "PROBABLE"
STATUS_UNCERTAIN = "UNCERTAIN"
STATUS_CONTRADICTED = "CONTRADICTED"
STATUS_OUTDATED = "OUTDATED"


@dataclass
class VerificationResult:
    claim: str
    status: str = STATUS_UNCERTAIN
    confidence: float = 0.0
    evidence_count: int = 0
    contradiction_count: int = 0
    supporting_sources: list[dict] = field(default_factory=list)
    contradicting_sources: list[dict] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class ClaimComparison:
    claim_a: str
    claim_b: str
    relationship: str = "unrelated"
    confidence: float = 0.0
    explanation: str = ""


NEGATION_MARKERS = re.compile(
    r"\b(not|never|no|neither|nor|neither|n't|doesn't|isn't|wasn't|"
    r"aren't|won't|can't|couldn't|shouldn't|wouldn't|don't|didn't|"
    r"cannot|lack|lacks|lacking|without|absent|zero|none)\b",
    re.IGNORECASE,
)


class VerificationEngine:
    """Verify claims against multiple sources with confidence scoring."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def verify_claim(self, claim: str, sources: list[dict]) -> VerificationResult:
        result = VerificationResult(claim=claim)
        supporting = []
        contradicting = []
        for source in sources:
            is_supporting = self._check_support(claim, source)
            entry = {
                "source_name": source.get("source_name", source.get("name", "unknown")),
                "url": source.get("url", ""),
                "reliability": source.get("reliability", 0.5),
                "snippet": source.get("snippet", source.get("text", "")),
            }
            if is_supporting:
                supporting.append(entry)
            else:
                contradicting.append(entry)
        result.supporting_sources = supporting
        result.contradicting_sources = contradicting
        result.evidence_count = len(sources)
        result.contradiction_count = len(contradicting)
        agreements = len(supporting)
        total = len(sources) if sources else 1
        result.confidence = self.calculate_confidence(
            sources=sources,
            agreements=agreements,
            contradictions=len(contradicting),
        )
        result.status = self._determine_status(result)
        result.reasoning = self._build_reasoning(result)
        return result

    def compare_claims(self, claims: list[str]) -> list[ClaimComparison]:
        comparisons: list[ClaimComparison] = []
        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                comparison = self._compare_two_claims(claims[i], claims[j])
                comparisons.append(comparison)
        return comparisons

    def check_consistency(self, knowledge_items: list[dict]) -> list[dict]:
        contradictions: list[dict] = []
        for i in range(len(knowledge_items)):
            for j in range(i + 1, len(knowledge_items)):
                item_a = knowledge_items[i]
                item_b = knowledge_items[j]
                claim_a = item_a.get("claim", "")
                claim_b = item_b.get("claim", "")
                if self._claims_contradict(claim_a, claim_b):
                    contradictions.append({
                        "claim_a": claim_a,
                        "claim_b": claim_b,
                        "claim_a_id": item_a.get("id"),
                        "claim_b_id": item_b.get("id"),
                        "type": "direct_contradiction",
                        "confidence": self._contradiction_confidence(claim_a, claim_b),
                    })
        return contradictions

    def calculate_confidence(
        self,
        sources: list[dict],
        agreements: int,
        contradictions: int,
    ) -> float:
        if not sources:
            return 0.0
        total = len(sources)
        agreement_ratio = agreements / total if total > 0 else 0.0
        avg_reliability = sum(
            s.get("reliability", 0.5) for s in sources
        ) / total
        recency_score = self._calculate_recency_score(sources)
        contradiction_penalty = (contradictions / total) * 0.5 if total > 0 else 0.0
        score = (
            0.40 * agreement_ratio
            + 0.30 * avg_reliability
            + 0.15 * recency_score
            - 0.15 * contradiction_penalty
        )
        if total >= 5:
            score = min(1.0, score + 0.05)
        elif total >= 3:
            score = min(1.0, score + 0.02)
        if contradictions > agreements and total > 1:
            score = max(0.0, score - 0.2)
        return round(max(0.0, min(1.0, score)), 4)

    def _check_support(self, claim: str, source: dict) -> bool:
        snippet = source.get("snippet", source.get("text", ""))
        if not snippet:
            return True
        claim_lower = claim.lower()
        snippet_lower = snippet.lower()
        claim_words = set(re.findall(r'\b[a-z]{4,}\b', claim_lower))
        snippet_words = set(re.findall(r'\b[a-z]{4,}\b', snippet_lower))
        if not claim_words:
            return True
        overlap = claim_words & snippet_words
        overlap_ratio = len(overlap) / len(claim_words)
        claim_negations = bool(NEGATION_MARKERS.search(claim_lower))
        snippet_negations = bool(NEGATION_MARKERS.search(snippet_lower))
        if overlap_ratio < 0.2:
            return True
        if snippet_negations and not claim_negations:
            return False
        if not snippet_negations and claim_negations:
            return False
        return True

    def _determine_status(self, result: VerificationResult) -> str:
        if result.contradiction_count > 0 and result.contradiction_count >= result.evidence_count * 0.5:
            return STATUS_CONTRADICTED
        if result.confidence >= 0.8 and result.evidence_count >= 2:
            return STATUS_VERIFIED
        if result.confidence >= CONFIDENCE_THRESHOLD:
            return STATUS_PROBABLE
        if result.evidence_count == 0:
            return STATUS_UNCERTAIN
        if result.confidence < 0.3:
            return STATUS_UNCERTAIN
        return STATUS_PROBABLE

    def _build_reasoning(self, result: VerificationResult) -> str:
        parts = []
        parts.append(f"Checked {result.evidence_count} source(s).")
        if result.supporting_sources:
            parts.append(f"{len(result.supporting_sources)} support(s).")
        if result.contradicting_sources:
            parts.append(f"{result.contradiction_count} contradict(s).")
        parts.append(f"Confidence: {result.confidence:.2f}")
        parts.append(f"Status: {result.status}")
        return " ".join(parts)

    def _compare_two_claims(self, claim_a: str, claim_b: str) -> ClaimComparison:
        comparison = ClaimComparison(claim_a=claim_a, claim_b=claim_b)
        if self._claims_contradict(claim_a, claim_b):
            comparison.relationship = "contradicts"
            comparison.confidence = self._contradiction_confidence(claim_a, claim_b)
            comparison.explanation = "Claims contain opposing assertions"
        elif self._claims_are_similar(claim_a, claim_b):
            comparison.relationship = "supports"
            comparison.confidence = self._similarity_score(claim_a, claim_b)
            comparison.explanation = "Claims express similar content"
        else:
            comparison.relationship = "unrelated"
            comparison.confidence = 0.0
            comparison.explanation = "No clear relationship detected"
        return comparison

    def _claims_contradict(self, claim_a: str, claim_b: str) -> bool:
        words_a = set(re.findall(r'\b[a-z]{4,}\b', claim_a.lower()))
        words_b = set(re.findall(r'\b[a-z]{4,}\b', claim_b.lower()))
        common = words_a & words_b
        if len(common) < 2:
            return False
        neg_a = bool(NEGATION_MARKERS.search(claim_a))
        neg_b = bool(NEGATION_MARKERS.search(claim_b))
        if neg_a != neg_b:
            return True
        antonym_pairs = [
            ("increase", "decrease"), ("rise", "fall"), ("better", "worse"),
            ("more", "less"), ("higher", "lower"), ("fast", "slow"),
            ("hot", "cold",), ("true", "false"), ("positive", "negative"),
            ("safe", "dangerous"), ("legal", "illegal"), ("possible", "impossible"),
        ]
        a_lower = claim_a.lower()
        b_lower = claim_b.lower()
        for pair in antonym_pairs:
            for word in pair:
                opposite_words = [w for w in pair if w != word]
                for opp in opposite_words:
                    if word in a_lower and opp in b_lower:
                        return True
                    if opp in a_lower and word in b_lower:
                        return True
        return False

    def _contradiction_confidence(self, claim_a: str, claim_b: str) -> float:
        words_a = set(re.findall(r'\b[a-z]{4,}\b', claim_a.lower()))
        words_b = set(re.findall(r'\b[a-z]{4,}\b', claim_b.lower()))
        common = words_a & words_b
        total = words_a | words_b
        jaccard = len(common) / len(total) if total else 0.0
        neg_a = bool(NEGATION_MARKERS.search(claim_a))
        neg_b = bool(NEGATION_MARKERS.search(claim_b))
        neg_score = 0.5 if neg_a != neg_b else 0.0
        score = 0.3 + (jaccard * 0.4) + neg_score
        return round(min(1.0, score), 4)

    def _claims_are_similar(self, claim_a: str, claim_b: str) -> bool:
        score = self._similarity_score(claim_a, claim_b)
        return score >= 0.5

    def _similarity_score(self, claim_a: str, claim_b: str) -> float:
        words_a = set(re.findall(r'\b[a-z]{4,}\b', claim_a.lower()))
        words_b = set(re.findall(r'\b[a-z]{4,}\b', claim_b.lower()))
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        jaccard = len(intersection) / len(union)
        length_ratio = min(len(claim_a), len(claim_b)) / max(len(claim_a), len(claim_b))
        return round((jaccard * 0.7 + length_ratio * 0.3), 4)

    def _calculate_recency_score(self, sources: list[dict]) -> float:
        now = datetime.now(timezone.utc)
        scores: list[float] = []
        for source in sources:
            last_fetched = source.get("last_fetched", source.get("updated_at"))
            if not last_fetched:
                scores.append(0.5)
                continue
            try:
                fetched_dt = datetime.fromisoformat(last_fetched.replace("Z", "+00:00"))
                days_old = (now - fetched_dt).days
                if days_old <= 7:
                    scores.append(1.0)
                elif days_old <= 30:
                    scores.append(0.8)
                elif days_old <= 90:
                    scores.append(0.6)
                elif days_old <= 365:
                    scores.append(0.4)
                else:
                    scores.append(0.2)
            except (ValueError, TypeError):
                scores.append(0.5)
        return sum(scores) / len(scores) if scores else 0.5
