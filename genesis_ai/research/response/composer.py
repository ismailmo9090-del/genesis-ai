"""ResponseComposer — synthesizes evidence into clear user-facing responses.

After research, Genesis must NOT simply return raw sources.
This composer converts:
EVIDENCE → UNDERSTANDING → SYNTHESIS → USER-FACING ANSWER

Uses a generic rule-based template system with varied connectors
to produce natural, flowing prose — not concatenated claims.

Supports:
- Multiple response structures based on question TYPE (not topic)
- English, Hindi, Hinglish
- Concise vs detailed
- Varied connector phrases (rotated to avoid templated feel)
- Language-matched responses
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Connector Pools (rotated for variety) ──────────────────────────────────────

_CAUSE_CONNECTORS_EN = [
    "This happens because",
    "The reason for this is that",
    "This occurs when",
    "This is due to",
    "The underlying cause is that",
]

_ELABORATION_CONNECTORS_EN = [
    "In addition,",
    "It's also worth noting that",
    "Beyond that,",
    "Furthermore,",
    "On top of that,",
]

_CONTRAST_CONNECTORS_EN = [
    "However,",
    "On the other hand,",
    "In contrast,",
    "That said,",
    "Conversely,",
]

_DEFINITION_CONNECTORS_EN = [
    "In other words,",
    "More specifically,",
    "To put it simply,",
    "Essentially,",
    "That means",
]

_MECHANISM_CONNECTORS_EN = [
    "This involves",
    "The process works through",
    "One key aspect is that",
    "In this process,",
    "The system works by",
]

# Hindi connectors
_CAUSE_CONNECTORS_HI = [
    "ऐसा इसलिए होता है क्योंकि",
    "इसका कारण यह है कि",
    "यह तब होता है जब",
    "इसके पीछे वजह यह है कि",
]

_ELABORATION_CONNECTORS_HI = [
    "इसके अलावा,",
    "यह भी ध्यान देने योग्य है कि",
    "इसके साथ ही,",
    "साथ ही,",
]

_CONTRAST_CONNECTORS_HI = [
    "लेकिन,",
    "हालांकि,",
    "दूसरी ओर,",
    "इसके विपरीत,",
]

_DEFINITION_CONNECTORS_HI = [
    "यानी,",
    "और अधिक स्पष्ट रूप से,",
    "सरल शब्दों में,",
    "मूल रूप से,",
]

_MECHANISM_CONNECTORS_HI = [
    "यह इस तरह काम करता है कि",
    "इसकी कार्यप्रणाली यह है कि",
    "इस प्रक्रिया में",
    "मूल रूप से,",
]

# Hinglish connectors
_CAUSE_CONNECTORS_HIENG = [
    "Aisa isliye hota hai kyunki",
    "Iska reason yeh hai ki",
    "Yeh tab hota hai jab",
    "Iske peeche wajah yeh hai ki",
]

_ELABORATION_CONNECTORS_HIENG = [
    "Iske alawa,",
    "Yeh bhi dhyan dene layak hai ki",
    "Iske saath hi,",
]

_CONTRAST_CONNECTORS_HIENG = [
    "Lekin,",
    "Halanki,",
    "Doosri taraf,",
]

_DEFINITION_CONNECTORS_HIENG = [
    "Yaani,",
    "Aur clearly,",
    "Simply boloon toh,",
    "Basically,",
]

_MECHANISM_CONNECTORS_HIENG = [
    "Yeh is tarah kaam karta hai ki",
    "Iska mechanism yeh hai ki",
    "Is process mein",
]


@dataclass
class ResponsePlan:
    """Plan for composing a response."""
    response_type: str = "generic"
    detail_level: str = "normal"
    language: str = "english"
    include_sources: bool = False
    include_confidence: bool = False
    structure: list[str] = field(default_factory=list)


class ResponseComposer:
    """Composes clear, structured responses from research evidence.

    Uses generic rule-based templates with varied connectors.
    No topic-specific logic — only question-type structure.
    """

    def __init__(self):
        self._connector_index = 0  # round-robin counter for variety

    def _next_connector(self, pool: list) -> str:
        """Pick next connector from pool using round-robin for variety."""
        connector = pool[self._connector_index % len(pool)]
        self._connector_index += 1
        return connector

    def _get_connectors(self, lang: str, connector_type: str) -> list:
        """Get connector pool for language and type."""
        pools = {
            "cause": {
                "english": _CAUSE_CONNECTORS_EN,
                "hindi": _CAUSE_CONNECTORS_HI,
                "hinglish": _CAUSE_CONNECTORS_HIENG,
            },
            "elaboration": {
                "english": _ELABORATION_CONNECTORS_EN,
                "hindi": _ELABORATION_CONNECTORS_HI,
                "hinglish": _ELABORATION_CONNECTORS_HIENG,
            },
            "contrast": {
                "english": _CONTRAST_CONNECTORS_EN,
                "hindi": _CONTRAST_CONNECTORS_HI,
                "hinglish": _CONTRAST_CONNECTORS_HIENG,
            },
            "definition": {
                "english": _DEFINITION_CONNECTORS_EN,
                "hindi": _DEFINITION_CONNECTORS_HI,
                "hinglish": _DEFINITION_CONNECTORS_HIENG,
            },
            "mechanism": {
                "english": _MECHANISM_CONNECTORS_EN,
                "hindi": _MECHANISM_CONNECTORS_HI,
                "hinglish": _MECHANISM_CONNECTORS_HIENG,
            },
        }
        return pools.get(connector_type, {}).get(lang, pools[connector_type].get("english", []))

    def _is_quality_claim(self, claim: str, question: str = "") -> bool:
        """Check if a claim is quality content using generic scoring."""
        from genesis_ai.utils.quality import quality_score
        score = quality_score(claim, question)
        # Lower threshold for evidence that passed initial filtering
        # Real explanations may score moderate on quality but still be valuable
        return score >= 0.25

    def _clean_claim(self, claim: str) -> str:
        """Clean a claim for composition — remove data junk, fix formatting."""
        if not claim:
            return ""
        # Remove hex color codes
        claim = re.sub(r'#[0-9A-Fa-f]{6}\b', '', claim)
        claim = re.sub(r'#[0-9A-Fa-f]{3}\b', '', claim)
        # Remove pipe-delimited key-value pairs (infobox data)
        if '|' in claim:
            parts = [p.strip() for p in claim.split('|') if p.strip()]
            # If most parts are very short (key-value pairs), reject
            short_parts = sum(1 for p in parts if len(p) < 20)
            if short_parts > len(parts) * 0.5:
                return ""
        # Remove coordinate/color data patterns
        claim = re.sub(r'\(?\d+,\s*\d+,\s*\d+\)?', '', claim)
        claim = re.sub(r'Hex\s+triplet.*', '', claim, flags=re.IGNORECASE)
        claim = re.sub(r'sRGB.*', '', claim, flags=re.IGNORECASE)
        claim = re.sub(r'HSV.*', '', claim, flags=re.IGNORECASE)
        claim = re.sub(r'CIEL.*', '', claim, flags=re.IGNORECASE)
        # Remove "redirects here" Wikipedia artifacts
        claim = re.sub(r'.*redirects here.*', '', claim, flags=re.IGNORECASE)
        claim = re.sub(r'.*For other uses.*', '', claim, flags=re.IGNORECASE)
        # Remove navigation/chrome patterns (breadcrumbs, category paths, site menus)
        # Match navigation prefix: everything up to "Short Answer" or first real sentence
        claim = re.sub(r'^.*?(Short Answer|Detailed Explanation|Background|Overview)\s*', '', claim, flags=re.IGNORECASE)
        # Match "Discover the..." / "Learn about..." engagement-bait intros
        claim = re.sub(r'^(Discover the .{10,60}\.)\s*', '', claim, flags=re.IGNORECASE)
        claim = re.sub(r'^(Learn about .{10,60}\.)\s*', '', claim, flags=re.IGNORECASE)
        claim = re.sub(r'^(Understanding the .{10,60}\.)\s*', '', claim, flags=re.IGNORECASE)
        # Clean whitespace
        claim = re.sub(r'\s+', ' ', claim).strip()
        return claim

    def _clean_claims(self, claims: list, question: str) -> list:
        """Clean and filter all claims."""
        cleaned = []
        for c in claims:
            c = self._clean_claim(c)
            if c and len(c) > 15 and self._is_quality_claim(c, question):
                cleaned.append(c)
        return cleaned

    def _ensure_flowing(self, text: str) -> str:
        """Ensure text reads as flowing prose, not stitched fragments."""
        if not text:
            return text
        # Fix double spaces
        text = re.sub(r'\s+', ' ', text)
        # Ensure first letter is capitalized
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        # Ensure ends with punctuation
        if text and text[-1] not in '.!?।':
            text += '.'
        # Remove duplicate sentences
        sentences = re.split(r'(?<=[.!?।])\s+', text)
        seen = set()
        unique = []
        for s in sentences:
            key = s.lower().strip()[:40]
            if key not in seen:
                seen.add(key)
                unique.append(s.strip())
        return ' '.join(unique)

    def compose(self, question: str, evidence: list[dict],
                knowledge: list[dict] = None, language: str = "english",
                detail_level: str = "normal",
                contradictions: list[dict] = None,
                confidence: float = 0.0) -> str:
        """Compose a response from evidence.

        Pipeline:
        1. Rule-based template composition (always runs)
        2. Language model rephrasing (if model available, as final polish)
        3. Fallback to rule-based if LM fails
        """
        plan = self._plan_response(question, language, detail_level, confidence)

        if evidence or knowledge:
            response = self._synthesize_from_evidence(
                question, evidence, knowledge, plan, contradictions
            )
        else:
            response = self._compose_no_evidence(question, plan)

        response = self._format_language(response, plan)

        # Phase 1: Try language model rephrasing as final polish
        if response and len(response) > 30:
            lm_response = self._try_lm_rephrase(question, response, language, detail_level)
            if lm_response and len(lm_response) > 20:
                response = lm_response

        return response

    def _try_lm_rephrase(self, question: str, rule_based_response: str,
                          language: str, detail_level: str) -> Optional[str]:
        """Try to rephrase using the language model. Returns None on failure.

        Only loads the model if GENESIS_USE_LANGUAGE_ENGINE env var is set
        or if the model has already been loaded in the process.
        """
        import os
        # Only use LM if explicitly enabled or already loaded
        use_lm = os.environ.get("GENESIS_USE_LANGUAGE_ENGINE", "0") == "1"
        if not use_lm:
            return None

        try:
            from genesis_ai.research.response.language_engine import _model_loaded
            if not _model_loaded:
                return None

            from genesis_ai.research.response.language_engine import LanguageEngine
            engine = LanguageEngine()
            if not engine.is_model_loaded():
                return None

            claims = [rule_based_response]
            tone = "formal" if detail_level == "detailed" else "normal"

            return engine.compose_natural_response(
                query=question,
                verified_claims=claims,
                language=language,
                tone_hint=tone,
            )
        except Exception as e:
            logger.debug("LM rephrase failed, using rule-based: %s", e)
            return None

    def _plan_response(self, question: str, language: str,
                        detail_level: str, confidence: float) -> ResponsePlan:
        """Plan the response structure based on question TYPE."""
        plan = ResponsePlan(
            language=language,
            detail_level=detail_level,
            include_confidence=confidence < 0.5,
        )
        q_lower = question.lower()

        if re.search(r'\b(why|kyon|kyun)\b', q_lower):
            plan.response_type = "cause"
        elif re.search(r'\b(how\s+(does|do|did|is|are|was|were)|kaise\b)', q_lower):
            plan.response_type = "mechanism"
        elif any(w in q_lower for w in ["what is", "what are", "kya hai", "kya hota", "define"]):
            plan.response_type = "definition"
        elif any(w in q_lower for w in ["who is", "who was", "kaun hai", "kaun tha"]):
            plan.response_type = "person"
        elif any(w in q_lower for w in ["how to", "steps", "process", "guide", "tarika"]):
            plan.response_type = "howto"
        elif any(w in q_lower for w in ["compare", "vs", "difference", "better", "versus", "alag"]):
            plan.response_type = "comparison"
        elif any(w in q_lower for w in ["code", "program", "function", "api"]):
            plan.response_type = "code"
        elif any(w in q_lower for w in ["latest", "current", "recent", "price", "version"]):
            plan.response_type = "current"
        else:
            plan.response_type = "generic"

        plan.include_sources = plan.response_type in ("current", "comparison")
        return plan

    def _synthesize_from_evidence(self, question: str, evidence: list[dict],
                                   knowledge: list[dict], plan: ResponsePlan,
                                   contradictions: list[dict] = None) -> str:
        """Synthesize a response from evidence."""
        claims = []
        sources = []

        if evidence:
            for e in evidence:
                claim = e.get("claim", e.get("statement", ""))
                if claim:
                    cleaned = self._clean_claim(claim)
                    if cleaned and len(cleaned) > 15 and self._is_quality_claim(cleaned, question):
                        claims.append(cleaned)
                source = e.get("source", e.get("source_name", ""))
                if source:
                    sources.append(source)

        if knowledge:
            for k in knowledge:
                if isinstance(k, dict):
                    claim = k.get("claim", "")
                    if claim:
                        cleaned = self._clean_claim(claim)
                        if cleaned and len(cleaned) > 15:
                            claims.append(cleaned)
                elif hasattr(k, "claim"):
                    cleaned = self._clean_claim(k.claim)
                    if cleaned and len(cleaned) > 15:
                        claims.append(cleaned)

        if not claims:
            return self._compose_no_evidence(question, plan)

        # Remove duplicate/redundant claims
        claims = self._deduplicate_claims(claims)

        # Route to appropriate template
        if plan.response_type == "cause":
            return self._compose_cause(claims, sources, plan)
        elif plan.response_type == "mechanism":
            return self._compose_mechanism(claims, sources, plan)
        elif plan.response_type == "definition":
            return self._compose_definition(claims, sources, plan)
        elif plan.response_type == "person":
            return self._compose_person(claims, sources, plan)
        elif plan.response_type == "howto":
            return self._compose_howto(claims, sources, plan)
        elif plan.response_type == "comparison":
            return self._compose_comparison(claims, sources, plan)
        elif plan.response_type == "current":
            return self._compose_current(claims, sources, plan, contradictions)
        elif plan.response_type == "code":
            return self._compose_code(claims, sources, plan)
        else:
            return self._compose_generic(claims, sources, plan)

    def _deduplicate_claims(self, claims: list) -> list:
        """Remove redundant/duplicate claims."""
        seen = set()
        unique = []
        for c in claims:
            key = c.lower().strip()[:50]
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique

    def _lowercase_after_connector(self, connector: str, text: str) -> str:
        """Lowercase the first letter of text if connector expects it."""
        # Connectors ending with prepositions/conjunctions expect lowercase
        connectors_needing_lowercase = [
            "this works by", "this happens because", "this occurs when",
            "this is due to", "the underlying cause is that",
            "this process involves", "the way it functions is that",
            "the key mechanism is that",
            "the reason for this is that",
            "yeh is tarah kaam karta hai ki",
            "iska mechanism yeh hai ki",
        ]
        connector_lower = connector.lower().strip().rstrip(',').rstrip()
        for prefix in connectors_needing_lowercase:
            if connector_lower.endswith(prefix.split()[-1]):
                if text and text[0].isupper():
                    text = text[0].lower() + text[1:]
                break
        return text

    def _compose_cause(self, claims: list, sources: list,
                        plan: ResponsePlan) -> str:
        """Compose a cause-explanation response."""
        # Simply join claims as flowing sentences
        response = self._merge_claims_flowing(claims[:3])
        return self._ensure_flowing(response)

    def _compose_mechanism(self, claims: list, sources: list,
                            plan: ResponsePlan) -> str:
        """Compose a mechanism/how-it-works response."""
        response = self._merge_claims_flowing(claims[:3])
        return self._ensure_flowing(response)

    def _compose_definition(self, claims: list, sources: list,
                             plan: ResponsePlan) -> str:
        """Compose a definition/explanation response."""
        response = self._merge_claims_flowing(claims[:3])
        return self._ensure_flowing(response)

    def _compose_person(self, claims: list, sources: list,
                         plan: ResponsePlan) -> str:
        """Compose a person biography response."""
        response = self._merge_claims_flowing(claims[:3])
        return self._ensure_flowing(response)

    def _compose_howto(self, claims: list, sources: list,
                        plan: ResponsePlan) -> str:
        """Compose a how-to response."""
        # Try to extract steps
        steps = []
        for claim in claims:
            numbered = re.findall(r'(?:^|\n)\s*\d+[.)]\s*(.+?)(?=\n|$)', claim)
            if numbered:
                steps.extend(numbered)
            elif len(claim) > 20:
                steps.append(claim)

        if steps:
            return "\n".join(f"{i+1}. {s.strip()}" for i, s in enumerate(steps[:7]))
        return self._merge_claims_flowing(claims[:3])

    def _compose_comparison(self, claims: list, sources: list,
                            plan: ResponsePlan) -> str:
        """Compose a comparison response."""
        if len(claims) >= 2:
            # Use contrast connector between first two claims
            lang = plan.language
            connector = self._next_connector(self._get_connectors(lang, "contrast"))
            response = claims[0] + " " + connector + " " + claims[1]
        elif claims:
            response = claims[0]
        else:
            return self._compose_no_evidence("", plan)

        if plan.detail_level == "detailed" and len(claims) > 2:
            response += " " + claims[2]

        return self._ensure_flowing(response)

    def _compose_current(self, claims: list, sources: list,
                          plan: ResponsePlan,
                          contradictions: list[dict] = None) -> str:
        """Compose a current information response."""
        response = claims[0] if claims else ""

        if contradictions:
            response += " However, sources may have conflicting information."

        return self._ensure_flowing(response)

    def _compose_code(self, claims: list, sources: list,
                       plan: ResponsePlan) -> str:
        """Compose a code-related response."""
        code_blocks = []
        explanations = []
        for claim in claims:
            if "```" in claim:
                code_blocks.append(claim)
            else:
                explanations.append(claim)

        response = ""
        if explanations:
            response += explanations[0]
        if code_blocks:
            response += "\n\n" + code_blocks[0]
        elif not response and claims:
            response = claims[0]

        return self._ensure_flowing(response)

    def _compose_generic(self, claims: list, sources: list,
                          plan: ResponsePlan) -> str:
        """Compose a generic response."""
        if not claims:
            return self._compose_no_evidence("", plan)
        return self._merge_claims_flowing(claims[:3])

    def _merge_claims_flowing(self, claims: list) -> str:
        """Merge claims into a flowing paragraph without explicit connectors."""
        if not claims:
            return ""
        # Join claims as sentences — remove trailing punctuation from each
        # except the last, and ensure proper spacing
        parts = []
        for c in claims:
            c = c.strip()
            if not c:
                continue
            # Remove trailing punctuation to avoid double-punctuation
            if c[-1] in '.!?।':
                c = c[:-1]
            parts.append(c)
        return '. '.join(parts) + '.' if parts else ''

    def _compose_no_evidence(self, question: str, plan: ResponsePlan) -> str:
        """Compose a response when no evidence is available."""
        if plan.language == "hindi":
            return "मुझे इस विषय पर पर्याप्त जानकारी नहीं है। कृपया और विस्तार से बताइए।"
        elif plan.language == "hinglish":
            return "Mujhe is topic pe enough info nahi hai. Thoda aur batao?"
        else:
            return "I don't have enough information on this topic. Could you provide more details?"

    def _format_language(self, response: str, plan: ResponsePlan) -> str:
        """Format response for the target language."""
        # Remove "According to..." prefixes
        response = re.sub(r'^(According to.*?(?:research|search|sources|my research)[\s:,-]*)', '', response, flags=re.IGNORECASE)
        response = re.sub(r'^(Based on.*?(?:search|results|research)[\s:,-]*)', '', response, flags=re.IGNORECASE)
        response = re.sub(r'^(I found.*?information[\s:,-]*)', '', response, flags=re.IGNORECASE)
        # Clean up markdown artifacts
        response = re.sub(r'\n{3,}', '\n\n', response)
        response = response.strip()
        # Ensure first letter is capitalized
        if response and response[0].islower():
            response = response[0].upper() + response[1:]
        return response
