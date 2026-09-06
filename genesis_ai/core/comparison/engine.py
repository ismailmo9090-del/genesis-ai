"""Comparison engine for evaluating multiple approaches and evidence sources.

Compares different methods, frameworks, claims, or solutions by scoring them
across simplicity, completeness, and reliability dimensions using source
authority weights. Pure Python implementation with no ML dependencies.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from genesis_ai.database.db import DatabaseManager


@dataclass
class ApproachScore:
    """Score breakdown for a single approach."""
    name: str
    simplicity: float = 0.0
    completeness: float = 0.0
    reliability: float = 0.0
    combined: float = 0.0
    evidence_count: int = 0
    source_authority: float = 0.0
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)


@dataclass
class ComparisonResult:
    """Structured result from comparing multiple sources or approaches."""
    topic: str
    approaches: list[dict] = field(default_factory=list)
    best_approach: str = ""
    reasoning: str = ""
    tradeoffs: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    alternatives: list[str] = field(default_factory=list)


class ComparisonEngine:
    """Compare multiple sources, approaches, or claims and rank them.

    The engine groups evidence by approach or claim, scores each on three
    dimensions (simplicity, completeness, reliability), applies source
    authority weighting, and produces a ranked recommendation.
    """

    # Weights for the three scoring dimensions.
    WEIGHTS = {"simplicity": 0.25, "completeness": 0.35, "reliability": 0.40}

    # Simple keyword heuristics for code-comparison mode.
    _SIMPLICITY_POSITIVE = {
        "simple", "concise", "lightweight", "minimal", "readable",
        "clean", "straightforward", "easy", "small", "fast",
    }
    _SIMPLICITY_NEGATIVE = {
        "complex", "verbose", "heavy", "boilerplate", "verbose",
        "cumbersome", "bloated", "overhead", "slow", "deprecat",
    }
    _COMPLETENESS_POSITIVE = {
        "full", "complete", "comprehensive", "feature", "supports",
        "covers", "robust", "mature", "batteries", "includes",
    }
    _COMPLETENESS_NEGATIVE = {
        "partial", "incomplete", "lacks", "missing", "limited",
        "basic", "stub", "unfinished", "incomplete",
    }

    # Fact-number extraction pattern.
    _NUMBER_RE = re.compile(r'[\d,]+\.?\d*')

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db

    # ── Public API ─────────────────────────────────────────

    def compare(
        self,
        evidence_list: list[dict],
        topic: str = "",
        mode: str = "auto",
    ) -> ComparisonResult:
        """Compare a list of evidence entries and return a ranked result.

        Parameters
        ----------
        evidence_list:
            Each dict should contain at least ``text`` or ``claim``.  Optional
            keys: ``source_name``, ``reliability`` (0-1), ``url``,
            ``approach``, ``snippet``, ``authoritative``.
        topic:
            A human-readable topic string for the result.
        mode:
            ``"auto"`` (default), ``"code"``, or ``"fact"``.  When *auto* the
            engine inspects the text to choose the best heuristic set.

        Returns
        -------
        ComparisonResult
        """
        if not evidence_list:
            return ComparisonResult(topic=topic, reasoning="No evidence provided.")

        if mode == "auto":
            mode = self._detect_mode(evidence_list)

        grouped = self._group_by_approach(evidence_list)
        scored: list[ApproachScore] = []
        for approach_name, items in grouped.items():
            score = self._score_approach(approach_name, items, mode)
            scored.append(score)

        scored.sort(key=lambda s: s.combined, reverse=True)

        best = scored[0] if scored else ApproachScore(name="none")
        alternatives = [s.name for s in scored[1:] if s.combined > 0.3]

        tradeoffs = []
        for s in scored:
            tradeoffs.append({
                "approach": s.name,
                "pros": s.pros,
                "cons": s.cons,
                "score": round(s.combined, 4),
            })

        confidence = self._compute_overall_confidence(scored)

        approaches_dicts = []
        for s in scored:
            approaches_dicts.append({
                "name": s.name,
                "simplicity": round(s.simplicity, 4),
                "completeness": round(s.completeness, 4),
                "reliability": round(s.reliability, 4),
                "combined": round(s.combined, 4),
                "evidence_count": s.evidence_count,
            })

        reasoning = self._build_reasoning(best, len(evidence_list), len(scored))

        return ComparisonResult(
            topic=topic,
            approaches=approaches_dicts,
            best_approach=best.name,
            reasoning=reasoning,
            tradeoffs=tradeoffs,
            confidence=round(confidence, 4),
            alternatives=alternatives,
        )

    def compare_claims(
        self,
        claims: list[dict],
        topic: str = "",
    ) -> ComparisonResult:
        """Convenience wrapper for comparing factual claims.

        Each claim dict should have ``text``/``claim`` and optionally
        ``source_name``, ``reliability``, ``date``.
        """
        return self.compare(claims, topic=topic, mode="fact")

    def compare_code(
        self,
        code_options: list[dict],
        topic: str = "",
    ) -> ComparisonResult:
        """Convenience wrapper for comparing code frameworks / patterns.

        Each code_options dict should have ``text``/``code`` and optionally
        ``framework``, ``source_name``, ``reliability``.
        """
        return self.compare(code_options, topic=topic, mode="code")

    # ── Grouping ───────────────────────────────────────────

    def _group_by_approach(self, evidence_list: list[dict]) -> dict[str, list[dict]]:
        """Group evidence by an extracted ``approach`` label.

        If an explicit ``approach`` key is present it is used directly.
        Otherwise the first meaningful noun-phrase of the text is extracted.
        """
        groups: dict[str, list[dict]] = defaultdict(list)
        for item in evidence_list:
            approach = item.get("approach", "").strip()
            if not approach:
                text = item.get("text", item.get("claim", item.get("snippet", "")))
                approach = self._extract_approach_label(text)
            groups[approach].append(item)
        return dict(groups)

    def _extract_approach_label(self, text: str) -> str:
        """Return a short label for *text* (first 6 words, lower-cased)."""
        words = re.findall(r'[A-Za-z]{2,}', text)
        label = " ".join(words[:6]).lower() or "unknown"
        return label

    # ── Scoring ────────────────────────────────────────────

    def _score_approach(
        self,
        name: str,
        items: list[dict],
        mode: str,
    ) -> ApproachScore:
        score = ApproachScore(name=name, evidence_count=len(items))

        reliabilities = [
            item.get("reliability", item.get("authority", 0.5))
            for item in items
        ]
        score.source_authority = (
            sum(reliabilities) / len(reliabilities) if reliabilities else 0.5
        )

        if mode == "code":
            score.simplicity = self._code_simplicity_score(items)
            score.completeness = self._code_completeness_score(items)
        elif mode == "fact":
            score.simplicity = self._fact_simplicity_score(items)
            score.completeness = self._fact_completeness_score(items)
        else:
            score.simplicity = self._generic_simplicity_score(items)
            score.completeness = self._generic_completeness_score(items)

        score.reliability = self._reliability_score(items)

        score.combined = (
            self.WEIGHTS["simplicity"] * score.simplicity
            + self.WEIGHTS["completeness"] * score.completeness
            + self.WEIGHTS["reliability"] * score.reliability
        )

        score.pros, score.cons = self._extract_tradeoffs(items, mode)
        return score

    # ── Simplicity scorers ─────────────────────────────────

    def _generic_simplicity_score(self, items: list[dict]) -> float:
        total = 0.0
        for item in items:
            text = (
                item.get("text", "")
                + " "
                + item.get("claim", "")
                + " "
                + item.get("snippet", "")
            ).lower()
            pos = sum(1 for w in self._SIMPLICITY_POSITIVE if w in text)
            neg = sum(1 for w in self._SIMPLICITY_NEGATIVE if w in text)
            total += 0.5 + 0.1 * (pos - neg)
        return self._clamp(total / len(items)) if items else 0.5

    def _code_simplicity_score(self, items: list[dict]) -> float:
        total = 0.0
        for item in items:
            text = (
                item.get("text", "")
                + " "
                + item.get("code", "")
                + " "
                + item.get("snippet", "")
            ).lower()
            lines = text.split("\n")
            loc = len([l for l in lines if l.strip()])
            pos = sum(1 for w in self._SIMPLICITY_POSITIVE if w in text)
            neg = sum(1 for w in self._SIMPLICITY_NEGATIVE if w in text)
            loc_score = max(0.0, 1.0 - loc / 200.0)
            total += 0.3 * loc_score + 0.35 + 0.1 * (pos - neg)
        return self._clamp(total / len(items)) if items else 0.5

    def _fact_simplicity_score(self, items: list[dict]) -> float:
        total = 0.0
        for item in items:
            text = (
                item.get("text", "") + " " + item.get("claim", "")
            ).lower()
            specificity = len(self._NUMBER_RE.findall(text))
            length = len(text.split())
            length_score = max(0.0, 1.0 - length / 80.0)
            spec_score = min(1.0, specificity / 5.0)
            total += 0.5 * length_score + 0.5 * spec_score
        return self._clamp(total / len(items)) if items else 0.5

    # ── Completeness scorers ───────────────────────────────

    def _generic_completeness_score(self, items: list[dict]) -> float:
        total = 0.0
        for item in items:
            text = (
                item.get("text", "")
                + " "
                + item.get("claim", "")
                + " "
                + item.get("snippet", "")
            ).lower()
            pos = sum(1 for w in self._COMPLETENESS_POSITIVE if w in text)
            neg = sum(1 for w in self._COMPLETENESS_NEGATIVE if w in text)
            length = len(text.split())
            length_score = min(1.0, length / 60.0)
            total += 0.35 * length_score + 0.35 + 0.1 * (pos - neg)
        return self._clamp(total / len(items)) if items else 0.5

    def _code_completeness_score(self, items: list[dict]) -> float:
        total = 0.0
        for item in items:
            text = (
                item.get("text", "")
                + " "
                + item.get("code", "")
                + " "
                + item.get("snippet", "")
            ).lower()
            pos = sum(1 for w in self._COMPLETENESS_POSITIVE if w in text)
            neg = sum(1 for w in self._COMPLETENESS_NEGATIVE if w in text)
            has_imports = "import" in text or "require" in text or "from" in text
            has_def = "def " in text or "function" in text or "class " in text
            has_return = "return" in text or "yield" in text
            structural = sum([has_imports, has_def, has_return])
            struct_score = structural / 3.0
            total += 0.3 * struct_score + 0.35 + 0.1 * (pos - neg)
        return self._clamp(total / len(items)) if items else 0.5

    def _fact_completeness_score(self, items: list[dict]) -> float:
        total = 0.0
        for item in items:
            text = (
                item.get("text", "") + " " + item.get("claim", "")
            ).lower()
            has_date = bool(re.search(r'\b(19|20)\d{2}\b', text))
            has_number = bool(self._NUMBER_RE.search(text))
            has_source = bool(item.get("source_name") or item.get("url"))
            attributes = sum([has_date, has_number, has_source])
            total += 0.3 + 0.2 * attributes
        return self._clamp(total / len(items)) if items else 0.5

    # ── Reliability scorer ─────────────────────────────────

    def _reliability_score(self, items: list[dict]) -> float:
        reliabilities = [
            item.get("reliability", item.get("authority", 0.5))
            for item in items
        ]
        if not reliabilities:
            return 0.5
        avg = sum(reliabilities) / len(reliabilities)
        count_bonus = min(0.1, len(items) * 0.02)
        return self._clamp(avg + count_bonus)

    # ── Tradeoff extraction ────────────────────────────────

    def _extract_tradeoffs(
        self,
        items: list[dict],
        mode: str,
    ) -> tuple[list[str], list[str]]:
        pros: list[str] = []
        cons: list[str] = []
        for item in items:
            text = (
                item.get("text", "")
                + " "
                + item.get("claim", "")
                + " "
                + item.get("snippet", "")
            ).lower()
            for w in self._SIMPLICITY_POSITIVE:
                if w in text and f"simple: {w}" not in pros:
                    pros.append(f"simple: {w}")
            for w in self._SIMPLICITY_NEGATIVE:
                if w in text and f"complex: {w}" not in cons:
                    cons.append(f"complex: {w}")
            for w in self._COMPLETENESS_POSITIVE:
                if w in text and f"complete: {w}" not in pros:
                    pros.append(f"complete: {w}")
            for w in self._COMPLETENESS_NEGATIVE:
                if w in text and f"incomplete: {w}" not in cons:
                    cons.append(f"incomplete: {w}")

        if not pros:
            pros.append("supported by evidence")
        if not cons:
            cons.append("no obvious drawbacks found")

        return pros[:5], cons[:5]

    # ── Confidence ─────────────────────────────────────────

    def _compute_overall_confidence(self, scored: list[ApproachScore]) -> float:
        if not scored:
            return 0.0
        best = scored[0].combined
        runner = scored[1].combined if len(scored) > 1 else 0.0
        margin = best - runner
        margin_bonus = min(0.2, margin)
        evidence_bonus = min(0.15, scored[0].evidence_count * 0.03)
        authority_bonus = min(0.1, scored[0].source_authority * 0.15)
        return self._clamp(0.4 + margin_bonus + evidence_bonus + authority_bonus)

    # ── Mode detection ─────────────────────────────────────

    def _detect_mode(self, evidence_list: list[dict]) -> str:
        all_text = " ".join(
            (item.get("text", "") + " " + item.get("claim", "") + " " + item.get("snippet", "") + " " + item.get("code", ""))
            for item in evidence_list
        ).lower()
        code_signals = ["def ", "class ", "import ", "function ", "return ", "const ", "let ", "var "]
        code_hits = sum(1 for s in code_signals if s in all_text)
        if code_hits >= 2:
            return "code"
        number_hits = len(self._NUMBER_RE.findall(all_text))
        if number_hits >= 3:
            return "fact"
        return "generic"

    # ── Reasoning builder ──────────────────────────────────

    def _build_reasoning(
        self,
        best: ApproachScore,
        evidence_count: int,
        approach_count: int,
    ) -> str:
        parts = [
            f"Compared {approach_count} approach(es) from {evidence_count} evidence source(s).",
            f"Best approach: '{best.name}' with combined score {best.combined:.3f}.",
            f"Simplicity={best.simplicity:.2f}, Completeness={best.completeness:.2f}, "
            f"Reliability={best.reliability:.2f}.",
        ]
        if best.pros:
            parts.append(f"Strengths: {', '.join(best.pros[:3])}.")
        if best.cons:
            parts.append(f"Weaknesses: {', '.join(best.cons[:3])}.")
        return " ".join(parts)

    @staticmethod
    def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return round(max(lo, min(hi, value)), 4)
