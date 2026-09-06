"""Contradiction engine for detecting and resolving conflicting claims.

Compares claims from different sources, classifies contradiction severity,
and attempts resolution using source authority and recency. Pure Python
implementation with no ML dependencies.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from genesis_ai.database.db import DatabaseManager


@dataclass
class Contradiction:
    """A single detected contradiction between two claims."""
    claim_a: str
    claim_b: str
    source_a: str
    source_b: str
    topic: str
    severity: str = "low"
    resolution: str = "unresolved"
    resolution_notes: str = ""


@dataclass
class ContradictionResult:
    """Aggregated result of contradiction analysis."""
    contradictions_found: int = 0
    contradictions: list[Contradiction] = field(default_factory=list)
    unresolved_count: int = 0
    overall_confidence: float = 1.0


# Antonym / negation helpers ------------------------------------------------

_NEGATION_RE = re.compile(
    r"\b(not|never|no|neither|nor|n't|doesn't|isn't|wasn't|"
    r"aren't|won't|can't|couldn't|shouldn't|wouldn't|don't|didn't|"
    r"cannot|lack|lacks|lacking|without|absent|zero|none)\b",
    re.IGNORECASE,
)

_ANTONYM_PAIRS: list[tuple[str, ...]] = [
    ("increase", "decrease"), ("rise", "fall"), ("better", "worse"),
    ("more", "less"), ("higher", "lower"), ("fast", "slow"),
    ("hot", "cold"), ("true", "false"), ("positive", "negative"),
    ("safe", "dangerous"), ("legal", "illegal"), ("possible", "impossible"),
    ("enable", "disable"), ("support", "reject"), ("agree", "disagree"),
    ("open", "close"), ("start", "stop"), ("add", "remove"),
    ("yes", "no"), ("always", "never"), ("all", "none"),
]

# Number extraction for factual comparison.
_NUMBER_RE = re.compile(r'[\d,]+\.?\d*')


class ContradictionEngine:
    """Detect and resolve contradictions between claims from different sources.

    The engine performs three types of analysis:
    1. Factual contradiction detection (different numbers / dates / names).
    2. Method contradiction detection (different recommended approaches).
    3. Severity classification and attempted resolution.
    """

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db

    # ── Public API ─────────────────────────────────────────

    def detect(
        self,
        claims: list[dict],
        topic: str = "",
    ) -> ContradictionResult:
        """Analyse a list of claims and return detected contradictions.

        Parameters
        ----------
        claims:
            Each dict must have ``text`` or ``claim``.  Optional keys:
            ``source_name``, ``url``, ``reliability`` (0-1), ``date``,
            ``authority``.
        topic:
            Human-readable topic for the result.

        Returns
        -------
        ContradictionResult
        """
        if len(claims) < 2:
            return ContradictionResult(
                contradictions_found=0,
                unresolved_count=0,
                overall_confidence=1.0,
            )

        raw_pairs = self._extract_pairs(claims)
        contradictions: list[Contradiction] = []

        for (a, b) in raw_pairs:
            ct = self._classify_contradiction(a, b)
            if ct is None:
                continue
            contradiction = Contradiction(
                claim_a=a.get("text", a.get("claim", "")),
                claim_b=b.get("text", b.get("claim", "")),
                source_a=a.get("source_name", a.get("url", "unknown")),
                source_b=b.get("source_name", b.get("url", "unknown")),
                topic=topic,
                severity=ct["severity"],
            )
            self._attempt_resolution(contradiction, a, b)
            contradictions.append(contradiction)

        unresolved = [c for c in contradictions if c.resolution != "resolved"]
        confidence = self._compute_confidence(contradictions, len(claims))

        return ContradictionResult(
            contradictions_found=len(contradictions),
            contradictions=contradictions,
            unresolved_count=len(unresolved),
            overall_confidence=round(confidence, 4),
        )

    # ── Pair extraction ────────────────────────────────────

    def _extract_pairs(self, claims: list[dict]) -> list[tuple[dict, dict]]:
        """Generate all unique pairs of claims."""
        pairs = []
        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                pairs.append((claims[i], claims[j]))
        return pairs

    # ── Contradiction classification ───────────────────────

    def _classify_contradiction(
        self,
        a: dict,
        b: dict,
    ) -> Optional[dict]:
        """Return severity dict if the two claims contradict, else None."""
        text_a = (a.get("text", "") + " " + a.get("claim", "")).strip()
        text_b = (b.get("text", "") + " " + b.get("claim", "")).strip()

        if not text_a or not text_b:
            return None

        # Factual contradiction: different numbers or dates.
        fact_score = self._factual_contradiction_score(text_a, text_b)
        if fact_score >= 0.7:
            return {"severity": "high", "type": "factual"}

        # Method contradiction: negation-based or antonym-based.
        method_score = self._method_contradiction_score(text_a, text_b)
        if method_score >= 0.6:
            return {"severity": "medium", "type": "method"}

        # Soft contradiction: minimal overlap with opposing tone.
        soft_score = self._soft_contradiction_score(text_a, text_b)
        if soft_score >= 0.5:
            return {"severity": "low", "type": "soft"}

        return None

    def _factual_contradiction_score(self, a: str, b: str) -> float:
        """Detect contradictions in numbers, dates, or named entities."""
        nums_a = _NUMBER_RE.findall(a)
        nums_b = _NUMBER_RE.findall(b)

        if not nums_a or not nums_b:
            return 0.0

        words_a = set(re.findall(r'\b[a-z]{4,}\b', a.lower()))
        words_b = set(re.findall(r'\b[a-z]{4,}\b', b.lower()))
        common = words_a & words_b

        if len(common) < 2:
            return 0.0

        nums_a_clean = {n.replace(",", "") for n in nums_a}
        nums_b_clean = {n.replace(",", "") for n in nums_b}

        if nums_a_clean and nums_b_clean and nums_a_clean != nums_b_clean:
            return 0.9

        dates_a = [n for n in nums_a if len(n) == 4 and n.isdigit()]
        dates_b = [n for n in nums_b if len(n) == 4 and n.isdigit()]
        if dates_a and dates_b and set(dates_a) != set(dates_b):
            return 0.85

        return 0.0

    def _method_contradiction_score(self, a: str, b: str) -> float:
        """Detect contradictions based on negation or antonym presence."""
        words_a = set(re.findall(r'\b[a-z]{4,}\b', a.lower()))
        words_b = set(re.findall(r'\b[a-z]{4,}\b', b.lower()))
        common = words_a & words_b

        if len(common) < 2:
            return 0.0

        neg_a = bool(_NEGATION_RE.search(a))
        neg_b = bool(_NEGATION_RE.search(b))

        if neg_a != neg_b:
            return 0.75

        for pair in _ANTONYM_PAIRS:
            for word in pair:
                opposites = [w for w in pair if w != word]
                for opp in opposites:
                    if word in a.lower() and opp in b.lower():
                        return 0.70
                    if opp in a.lower() and word in b.lower():
                        return 0.70

        return 0.0

    def _soft_contradiction_score(self, a: str, b: str) -> float:
        """Detect weak contradictions via negation markers and overlap."""
        words_a = set(re.findall(r'\b[a-z]{4,}\b', a.lower()))
        words_b = set(re.findall(r'\b[a-z]{4,}\b', b.lower()))
        if not words_a or not words_b:
            return 0.0

        intersection = words_a & words_b
        union = words_a | words_b
        jaccard = len(intersection) / len(union) if union else 0.0

        if jaccard < 0.15:
            return 0.0

        neg_a = bool(_NEGATION_RE.search(a))
        neg_b = bool(_NEGATION_RE.search(b))

        if neg_a == neg_b:
            return 0.0

        return 0.3 + 0.3 * jaccard

    # ── Resolution ─────────────────────────────────────────

    def _attempt_resolution(
        self,
        contradiction: Contradiction,
        a: dict,
        b: dict,
    ) -> None:
        """Try to resolve a contradiction using source metadata."""
        rel_a = a.get("reliability", a.get("authority", 0.5))
        rel_b = b.get("reliability", b.get("authority", 0.5))
        date_a = self._parse_date(a.get("date", a.get("last_fetched", "")))
        date_b = self._parse_date(b.get("date", b.get("last_fetched", "")))

        # Higher authority wins.
        if abs(rel_a - rel_b) >= 0.3:
            winner = "A" if rel_a > rel_b else "B"
            contradiction.resolution = "resolved"
            contradiction.resolution_notes = (
                f"Resolved by authority: source {winner} "
                f"(reliability={max(rel_a, rel_b):.2f}) outweighs the other."
            )
            return

        # More recent source wins.
        if date_a and date_b and date_a != date_b:
            winner = "A" if date_a > date_b else "B"
            contradiction.resolution = "resolved"
            contradiction.resolution_notes = (
                f"Resolved by recency: source {winner} "
                f"({max(date_a, date_b)}) is more recent."
            )
            return

        # Authority difference is small but non-zero.
        if abs(rel_a - rel_b) > 0.1:
            contradiction.resolution = "partially_resolved"
            contradiction.resolution_notes = (
                "Partial resolution: slight authority difference detected."
            )
            return

        contradiction.resolution = "unresolved"
        contradiction.resolution_notes = (
            "Cannot resolve: sources have similar authority and recency."
        )

    def _parse_date(self, raw: str) -> Optional[datetime]:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    # ── Confidence ─────────────────────────────────────────

    def _compute_confidence(
        self,
        contradictions: list[Contradiction],
        claim_count: int,
    ) -> float:
        if not contradictions:
            return 1.0

        severity_weight = {"high": 0.4, "medium": 0.25, "low": 0.1}
        total_penalty = sum(
            severity_weight.get(c.severity, 0.1) for c in contradictions
        )

        unresolved_penalty = 0.0
        for c in contradictions:
            if c.resolution == "unresolved":
                unresolved_penalty += 0.15
            elif c.resolution == "partially_resolved":
                unresolved_penalty += 0.05

        claim_density = len(contradictions) / max(1, claim_count)
        density_penalty = min(0.3, claim_density * 0.5)

        confidence = 1.0 - total_penalty - unresolved_penalty - density_penalty
        return max(0.0, min(1.0, confidence))
