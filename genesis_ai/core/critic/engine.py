"""Self-critic engine for evaluating generated answers.

Scores an answer against ten quality criteria, calculates a weighted overall
score, and produces actionable improvement suggestions.  Pure Python
implementation with no ML dependencies.
"""

import ast
import re
from dataclasses import dataclass, field
from typing import Optional

from genesis_ai.database.db import DatabaseManager


@dataclass
class CritiqueResult:
    """Structured output from the self-critique pass."""
    score: float = 0.0
    correctness: float = 0.0
    completeness: float = 0.0
    source_quality: float = 0.0
    issues: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    should_retry: bool = False
    confidence: float = 0.0


# Criterion definitions: (key, weight, description)
_CRITERIA = [
    ("addresses_question",       0.15, "Does the answer actually address the user's question?"),
    ("meets_requirements",       0.12, "Are all stated requirements satisfied?"),
    ("technical_accuracy",       0.15, "Is the information technically accurate?"),
    ("source_authority",         0.12, "Are sources authoritative and reliable?"),
    ("no_unresolved_contradictions", 0.10, "Are contradictions between sources resolved?"),
    ("code_validity",            0.10, "For code answers: is the syntax valid?"),
    ("simplicity",               0.08, "Could a simpler solution achieve the same result?"),
    ("no_vagueness",             0.08, "Is the answer specific rather than vague?"),
    ("no_hallucination",         0.10, "Is all information grounded in provided sources?"),
    ("improvability",            0.00, "Can the answer be improved further? (informational)"),
]

# Question words used to test whether the answer addresses the query.
_QUESTION_WORDS = re.compile(
    r'\b(what|how|why|when|where|who|which|explain|describe|compare|list)\b',
    re.IGNORECASE,
)

# Vague / hedging language.
_VAGUE_MARKERS = re.compile(
    r'\b(maybe|perhaps|might|could be|possibly|sort of|kind of|'
    r'it depends|generally|usually|often|sometimes|some cases|'
    r'not sure|unclear|hard to say|arguably|presumably)\b',
    re.IGNORECASE,
)

# Hedging filler that weakens answers.
_FILLER_MARKERS = re.compile(
    r'\b(in order to|for the purpose of|it is worth noting that|'
    r'as a matter of fact|basically|essentially|literally|'
    r'obviously|clearly|of course)\b',
    re.IGNORECASE,
)

# Claim-source grounding check: words from the answer that must come from sources.
_MIN_SOURCE_OVERLAP = 0.15


class CriticEngine:
    """Evaluate a generated answer against ten quality criteria.

    Parameters
    ----------
    db:
        Optional database manager for persistence.
    """

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db

    # ── Public API ─────────────────────────────────────────

    def critique(
        self,
        answer: str,
        question: str = "",
        research: list[dict] | None = None,
        understanding: dict | None = None,
        contradictions: list[dict] | None = None,
    ) -> CritiqueResult:
        """Run all ten criteria against *answer* and return scores.

        Parameters
        ----------
        answer:
            The generated response text.
        question:
            The original user question.
        research:
            List of research items (dicts with ``text``/``claim``/``snippet``).
        understanding:
            Optional parsed understanding of the question.
        contradictions:
            Optional list of detected contradictions.

        Returns
        -------
        CritiqueResult
        """
        research = research or []
        contradictions = contradictions or []
        understanding = understanding or {}

        scores: dict[str, float] = {}
        issues: list[str] = []
        improvements: list[str] = []

        # 1. Addresses question
        scores["addresses_question"] = self._check_addresses_question(
            answer, question, issues, improvements,
        )

        # 2. Meets requirements
        scores["meets_requirements"] = self._check_meets_requirements(
            answer, understanding, issues, improvements,
        )

        # 3. Technical accuracy
        scores["technical_accuracy"] = self._check_technical_accuracy(
            answer, issues, improvements,
        )

        # 4. Source authority
        scores["source_authority"] = self._check_source_quality(
            research, issues, improvements,
        )

        # 5. No unresolved contradictions
        scores["no_unresolved_contradictions"] = self._check_contradictions(
            contradictions, issues, improvements,
        )

        # 6. Code validity
        scores["code_validity"] = self._check_code_validity(
            answer, issues, improvements,
        )

        # 7. Simplicity
        scores["simplicity"] = self._check_simplicity(
            answer, issues, improvements,
        )

        # 8. No vagueness
        scores["no_vagueness"] = self._check_vagueness(
            answer, issues, improvements,
        )

        # 9. No hallucination
        scores["no_hallucination"] = self._check_hallucination(
            answer, research, issues, improvements,
        )

        # 10. Improvability (informational, not weighted in total)
        scores["improvability"] = self._check_improvability(
            answer, improvements,
        )

        overall = self._weighted_average(scores)
        correctness = (
            scores["addresses_question"] * 0.5
            + scores["technical_accuracy"] * 0.3
            + scores["no_hallucination"] * 0.2
        )
        completeness = (
            scores["meets_requirements"] * 0.4
            + scores["completeness"]
            + scores["simplicity"]
        ) / 3.0 if "completeness" in scores else scores["meets_requirements"]
        source_quality = scores["source_authority"]

        should_retry = overall < 0.6 or correctness < 0.5

        confidence = self._compute_confidence(
            overall, len(research), len(contradictions),
        )

        return CritiqueResult(
            score=round(overall, 4),
            correctness=round(correctness, 4),
            completeness=round(completeness, 4),
            source_quality=round(source_quality, 4),
            issues=issues,
            improvements=improvements,
            should_retry=should_retry,
            confidence=round(confidence, 4),
        )

    # ── Criterion implementations ──────────────────────────

    def _check_addresses_question(
        self,
        answer: str,
        question: str,
        issues: list[str],
        improvements: list[str],
    ) -> float:
        if not question:
            return 0.5

        q_words = set(re.findall(r'\b[a-z]{4,}\b', question.lower()))
        a_words = set(re.findall(r'\b[a-z]{4,}\b', answer.lower()))

        if not q_words:
            return 0.5

        overlap = q_words & a_words
        ratio = len(overlap) / len(q_words)

        q_type = _QUESTION_WORDS.search(question)
        if q_type:
            q_keyword = q_type.group(1).lower()
            answer_lower = answer.lower()
            if q_keyword in ("what", "which", "who"):
                if not re.search(r'\b(is|are|was|were|refers?|means?)\b', answer_lower):
                    ratio *= 0.8
            elif q_keyword == "how":
                if not re.search(r'\b(step|process|method|approach|way)\b', answer_lower):
                    ratio *= 0.8
            elif q_keyword == "why":
                if not re.search(r'\b(because|due to|reason|caused|since)\b', answer_lower):
                    ratio *= 0.8

        score = self._clamp(0.2 + 0.6 * ratio)

        if ratio < 0.3:
            issues.append("Answer may not address the core question.")
            improvements.append(
                "Ensure the answer directly responds to the user's question."
            )

        return score

    def _check_meets_requirements(
        self,
        answer: str,
        understanding: dict,
        issues: list[str],
        improvements: list[str],
    ) -> float:
        requirements = understanding.get("requirements", [])
        if not requirements:
            return 0.7

        met = 0
        for req in requirements:
            req_words = set(re.findall(r'\b[a-z]{3,}\b', str(req).lower()))
            ans_words = set(re.findall(r'\b[a-z]{3,}\b', answer.lower()))
            if req_words & ans_words:
                met += 1

        ratio = met / len(requirements) if requirements else 1.0
        score = self._clamp(ratio)

        if ratio < 0.5:
            issues.append(f"Only {met}/{len(requirements)} requirements appear met.")
            improvements.append("Review all stated requirements and address each one.")

        return score

    def _check_technical_accuracy(
        self,
        answer: str,
        issues: list[str],
        improvements: list[str],
    ) -> float:
        score = 0.7

        if re.search(r'\b(19|20)\d{2}\b', answer):
            score += 0.05

        patterns_correct = [
            (r'\b\d+\.\d+\.\d+\b', "version number detected"),
            (r'\bhttps?://\S+\b', "URL detected"),
            (r'\b[A-Z][a-z]+Error\b', "error class detected"),
        ]
        for pat, _desc in patterns_correct:
            if re.search(pat, answer):
                score += 0.03

        if answer.isupper() and len(answer) > 50:
            score -= 0.1
            issues.append("Excessive use of uppercase may indicate shouting or errors.")

        return self._clamp(score)

    def _check_source_quality(
        self,
        research: list[dict],
        issues: list[str],
        improvements: list[str],
    ) -> float:
        if not research:
            issues.append("No source material provided for verification.")
            improvements.append("Provide research sources for fact-checking.")
            return 0.3

        reliabilities = [
            item.get("reliability", item.get("authority", 0.5))
            for item in research
        ]
        avg = sum(reliabilities) / len(reliabilities)
        count_bonus = min(0.15, len(research) * 0.02)
        score = self._clamp(avg + count_bonus)

        low_sources = [
            item.get("source_name", item.get("url", "unknown"))
            for item in research
            if item.get("reliability", item.get("authority", 0.5)) < 0.3
        ]
        if low_sources:
            issues.append(
                f"Some sources have low authority: {', '.join(low_sources[:3])}."
            )
            improvements.append("Use more authoritative sources where possible.")

        return score

    def _check_contradictions(
        self,
        contradictions: list[dict],
        issues: list[str],
        improvements: list[str],
    ) -> float:
        if not contradictions:
            return 1.0

        unresolved = [
            c for c in contradictions
            if c.get("resolution", "unresolved") == "unresolved"
        ]
        high_severity = [
            c for c in contradictions
            if c.get("severity") == "high"
        ]

        penalty = len(contradictions) * 0.1 + len(unresolved) * 0.15
        score = self._clamp(1.0 - penalty)

        if unresolved:
            issues.append(
                f"{len(unresolved)} unresolved contradiction(s) remain."
            )
            improvements.append(
                "Address unresolved contradictions by selecting the most "
                "authoritative source or noting the uncertainty."
            )

        if high_severity:
            issues.append(
                f"{len(high_severity)} high-severity contradiction(s) detected."
            )

        return score

    def _check_code_validity(
        self,
        answer: str,
        issues: list[str],
        improvements: list[str],
    ) -> float:
        code_blocks = re.findall(r'```(?:python)?\s*\n(.*?)```', answer, re.DOTALL)
        if not code_blocks:
            code_blocks = re.findall(r'```(.*?)```', answer, re.DOTALL)

        if not code_blocks:
            return 0.5

        valid = 0
        total = 0
        for block in code_blocks:
            block = block.strip()
            if not block:
                continue
            total += 1
            try:
                ast.parse(block)
                valid += 1
            except SyntaxError:
                issues.append("Code block contains a syntax error.")
                improvements.append(
                    "Fix the syntax error in the code block before finalising."
                )

        if total == 0:
            return 0.5

        score = valid / total
        if score < 1.0:
            improvements.append(
                "Validate all code blocks for correct Python syntax."
            )
        return self._clamp(score)

    def _check_simplicity(
        self,
        answer: str,
        issues: list[str],
        improvements: list[str],
    ) -> float:
        words = answer.split()
        length = len(words)

        if length < 20:
            return 0.5

        sentences = re.split(r'[.!?]+', answer)
        sentences = [s.strip() for s in sentences if s.strip()]
        avg_len = sum(len(s.split()) for s in sentences) / max(1, len(sentences))

        score = 0.7
        if avg_len > 30:
            score -= 0.15
            issues.append("Sentences are quite long; consider breaking them up.")
        if length > 500:
            score -= 0.1
            improvements.append("Consider condensing the answer for clarity.")
        if length > 1000:
            score -= 0.15

        return self._clamp(score)

    def _check_vagueness(
        self,
        answer: str,
        issues: list[str],
        improvements: list[str],
    ) -> float:
        vague_hits = _VAGUE_MARKERS.findall(answer)
        filler_hits = _FILLER_MARKERS.findall(answer)
        total = len(vague_hits) + len(filler_hits)

        words = answer.split()
        word_count = max(1, len(words))
        vague_ratio = total / word_count

        score = self._clamp(0.8 - vague_ratio * 5)

        if vague_hits:
            issues.append(
                f"Vague language detected ({len(vague_hits)} instance(s))."
            )
            improvements.append("Replace hedging words with concrete statements.")
        if filler_hits:
            issues.append(
                f"Filler phrases detected ({len(filler_hits)} instance(s))."
            )
            improvements.append("Remove filler phrases for a more direct answer.")

        return score

    def _check_hallucination(
        self,
        answer: str,
        research: list[dict],
        issues: list[str],
        improvements: list[str],
    ) -> float:
        if not research:
            return 0.5

        answer_words = set(re.findall(r'\b[a-z]{4,}\b', answer.lower()))
        source_words: set[str] = set()
        for item in research:
            text = (
                item.get("text", "")
                + " "
                + item.get("claim", "")
                + " "
                + item.get("snippet", "")
            )
            source_words |= set(re.findall(r'\b[a-z]{4,}\b', text.lower()))

        if not answer_words or not source_words:
            return 0.5

        overlap = answer_words & source_words
        overlap_ratio = len(overlap) / len(answer_words)

        external_words = answer_words - source_words
        total_external = len(external_words)

        structural_words = {
            "the", "and", "that", "this", "with", "from", "have", "are",
            "was", "were", "been", "being", "will", "would", "could",
            "should", "may", "might", "can", "must", "shall", "need",
            "for", "not", "but", "also", "than", "when", "where", "how",
            "what", "which", "about", "into", "through", "during", "before",
            "after", "above", "below", "between", "each", "every", "both",
            "few", "more", "most", "other", "some", "such", "only", "own",
            "same", "then", "very", "just", "here", "there", "why",
        }
        meaningful_external = external_words - structural_words

        if len(answer_words) < 10:
            return 0.7

        novelty_ratio = len(meaningful_external) / len(answer_words)
        if novelty_ratio > 0.5:
            score = 0.3
            issues.append("Much of the answer is not grounded in provided sources.")
            improvements.append(
                "Ground claims in the provided research or clearly mark "
                "inferences as such."
            )
        elif novelty_ratio > 0.35:
            score = 0.5
            issues.append("Some claims may not be directly supported by sources.")
            improvements.append(
                "Verify that each factual claim can be traced to a source."
            )
        else:
            score = 0.7 + 0.3 * overlap_ratio

        return self._clamp(score)

    def _check_improvability(
        self,
        answer: str,
        improvements: list[str],
    ) -> float:
        score = 0.5
        words = answer.split()

        if len(words) < 30:
            improvements.append("The answer is quite short; consider adding more detail.")
            score -= 0.1

        has_structure = bool(re.search(r'```|^- |\d+\.', answer, re.MULTILINE))
        if not has_structure and len(words) > 100:
            improvements.append(
                "Consider using lists, code blocks, or headers for clarity."
            )
            score -= 0.05

        return self._clamp(score)

    # ── Scoring helpers ────────────────────────────────────

    def _weighted_average(self, scores: dict[str, float]) -> float:
        total = 0.0
        weight_sum = 0.0
        for key, weight, _desc in _CRITERIA:
            if key == "improvability":
                continue
            if key in scores:
                total += scores[key] * weight
                weight_sum += weight
        return total / weight_sum if weight_sum > 0 else 0.0

    def _compute_confidence(
        self,
        overall: float,
        research_count: int,
        contradiction_count: int,
    ) -> float:
        base = overall * 0.6
        research_bonus = min(0.2, research_count * 0.03)
        contra_penalty = min(0.3, contradiction_count * 0.1)
        return self._clamp(base + research_bonus - contra_penalty + 0.2)

    @staticmethod
    def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return round(max(lo, min(hi, value)), 4)
