"""Learned Knowledge Retrieval Engine.

Retrieves validated learning from the learning system for use during inference.
Bridges: Learning API → Database → Inference Pipeline

Design principles:
- Only ACTIVE/VERIFIED knowledge influences inference
- Confidence-gated retrieval
- Freshness-aware
- Contradiction-aware
- Efficient SQLite queries (no full-table scans)
- Returns ranked candidates, not entire database
"""

from __future__ import annotations

import re
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

from genesis_ai.database.db import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class RetrievedKnowledge:
    """A piece of learned knowledge retrieved for inference."""
    id: int = 0
    concept: str = ""
    claim: str = ""
    confidence: float = 0.5
    status: str = "UNCERTAIN"
    source: str = ""
    created_at: float = 0.0
    freshness: float = 1.0
    use_count: int = 0
    relevance_score: float = 0.0
    knowledge_type: str = "fact"  # fact, generalization, skill, intent_pattern


@dataclass
class RetrievedGeneralization:
    """A learned generalization retrieved for inference."""
    id: int = 0
    pattern: str = ""
    description: str = ""
    confidence: float = 0.5
    scope: str = "general"
    usage_count: int = 0
    success_rate: float = 0.0
    relevance_score: float = 0.0


@dataclass
class RetrievedSkill:
    """A learned skill retrieved for inference."""
    id: int = 0
    name: str = ""
    description: str = ""
    procedure: list[str] = field(default_factory=list)
    confidence: float = 0.5
    success_rate: float = 0.0
    experience_count: int = 0
    relevance_score: float = 0.0


@dataclass
class RetrievedIntentPattern:
    """A learned intent pattern retrieved for inference."""
    id: int = 0
    pattern_text: str = ""
    intent: str = ""
    concept: str = ""
    conditions: list[str] = field(default_factory=list)
    positive_examples: list[str] = field(default_factory=list)
    negative_examples: list[str] = field(default_factory=list)
    confidence: float = 0.5
    status: str = "ACTIVE"
    relevance_score: float = 0.0
    structure_match: float = 1.0  # 0.0 = structure mismatch, 1.0 = structure match


@dataclass
class LearningRetrievalResult:
    """Complete result from learning retrieval."""
    knowledge: list[RetrievedKnowledge] = field(default_factory=list)
    generalizations: list[RetrievedGeneralization] = field(default_factory=list)
    skills: list[RetrievedSkill] = field(default_factory=list)
    intent_patterns: list[RetrievedIntentPattern] = field(default_factory=list)
    retrieval_time_ms: float = 0.0
    total_candidates: int = 0


class LearningRetrieval:
    """Retrieves validated learning for inference use.

    This is the BRIDGE between the learning system and the inference pipeline.
    - Confidence (minimum threshold)
    - Minimum relevance threshold (filters out unrelated knowledge)
    It queries learned_knowledge, learned_generalizations, learned_skills,
    and learned_intent_patterns tables, filtering by:
    - Status (only ACTIVE/VERIFIED for normal use)
    - Confidence (minimum threshold)
    - Freshness (not outdated)
    - Relevance (keyword/semantic matching)
    """

    # Minimum confidence for knowledge to influence inference
    MIN_CONFIDENCE = 0.3

    # Minimum relevance score — knowledge below this threshold is NOT used
    # even if it matches the SQL query. Prevents returning unrelated cached
    # knowledge (e.g. Gravity for a virus/bacteria question).
    MIN_RELEVANCE = 0.15

    # Statuses that can influence inference
    ACTIVE_STATUSES = ("VERIFIED", "PROBABLE")

    # Statuses that can influence with reduced authority
    CANDIDATE_STATUSES = ("UNCERTAIN",)

    def __init__(self, db: DatabaseManager):
        self.db = db

    def retrieve(
        self,
        query: str,
        context: list[dict] | None = None,
        limit: int = 10,
        include_candidates: bool = False,
    ) -> LearningRetrievalResult:
        """Retrieve all relevant learning for the current inference request.

        Args:
            query: The user's current input text
            context: Optional conversation context (list of previous messages)
            limit: Maximum items per category
            include_candidates: Whether to include UNCERTAIN knowledge

        Returns:
            LearningRetrievalResult with ranked candidates
        """
        start = time.time()
        result = LearningRetrievalResult()

        # Extract search terms from query
        search_terms = self._extract_search_terms(query)
        if not search_terms:
            result.retrieval_time_ms = (time.time() - start) * 1000
            return result

        # 1. Retrieve relevant learned knowledge
        result.knowledge = self._retrieve_knowledge(
            search_terms, query, limit, include_candidates
        )

        # 2. Retrieve relevant generalizations
        result.generalizations = self._retrieve_generalizations(
            search_terms, query, limit
        )

        # 3. Retrieve relevant skills
        result.skills = self._retrieve_skills(search_terms, query, limit)

        # 4. Retrieve intent patterns
        result.intent_patterns = self._retrieve_intent_patterns(
            search_terms, query, limit
        )

        result.total_candidates = (
            len(result.knowledge) + len(result.generalizations) +
            len(result.skills) + len(result.intent_patterns)
        )
        result.retrieval_time_ms = (time.time() - start) * 1000

        return result

    def _extract_search_terms(self, text: str) -> list[str]:
        """Extract meaningful search terms from text."""
        # Simple word extraction — efficient for SQLite LIKE queries
        words = set(re.findall(r'\b[a-zA-Z]{2,}\b', text.lower()))
        # Remove common stop words
        stop_words = {
            'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but',
            'in', 'with', 'to', 'for', 'of', 'not', 'no', 'can', 'had', 'has',
            'was', 'were', 'are', 'be', 'been', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'shall', 'this', 'that',
            'these', 'those', 'it', 'its', 'my', 'your', 'his', 'her', 'our',
            'their', 'what', 'how', 'who', 'when', 'where', 'why', 'than',
            'then', 'so', 'if', 'about', 'up', 'out', 'just', 'also', 'very',
            'kya', 'hai', 'ho', 'ka', 'ki', 'ke', 'se', 'ko', 'me', 'ye',
            'wo', 'main', 'mera', 'tum', 'tumhara', 'mai', 'hain',
        }
        return [w for w in words if w not in stop_words]

    def _retrieve_knowledge(
        self,
        search_terms: list[str],
        query: str,
        limit: int,
        include_candidates: bool,
    ) -> list[RetrievedKnowledge]:
        """Retrieve relevant learned knowledge."""
        if not search_terms:
            return []

        # Build LIKE conditions for search
        like_conditions = []
        like_params = []
        for term in search_terms[:10]:  # Limit to 10 terms
            like_conditions.append("(concept LIKE ? OR claim LIKE ?)")
            like_params.extend([f"%{term}%", f"%{term}%"])

        where_clause = " OR ".join(like_conditions)

        # Status filter
        if include_candidates:
            all_statuses = list(self.ACTIVE_STATUSES) + list(self.CANDIDATE_STATUSES)
        else:
            all_statuses = list(self.ACTIVE_STATUSES)
        status_in = ",".join(["?"] * len(all_statuses))
        status_filter = f"status IN ({status_in})"

        # Params order: LIKE terms, confidence, status values, limit
        params = list(like_params)
        params.append(self.MIN_CONFIDENCE)
        params.extend(all_statuses)
        params.append(limit)

        # Try with freshness join, fall back to without it
        try:
            query_sql = f"""
                SELECT k.id, k.concept, k.claim, k.confidence, k.status,
                       k.source, k.created_at, k.usage_count,
                       COALESCE(f.freshness, 1.0) as freshness
                FROM learned_knowledge k
                LEFT JOIN knowledge_freshness f ON k.id = f.knowledge_id
                WHERE ({where_clause})
                AND k.confidence >= ?
                AND {status_filter}
                ORDER BY k.confidence DESC, freshness DESC
                LIMIT ?
            """
            rows = self.db.fetch_all(query_sql, tuple(params))
        except Exception:
            # knowledge_freshness table may not exist — simpler query
            query_sql = f"""
                SELECT id, concept, claim, confidence, status,
                       source, created_at, usage_count, 1.0 as freshness
                FROM learned_knowledge
                WHERE ({where_clause})
                AND confidence >= ?
                AND {status_filter}
                ORDER BY confidence DESC
                LIMIT ?
            """
            rows = self.db.fetch_all(query_sql, tuple(params))

        results = []
        for row in rows:
            # Calculate relevance score
            relevance = self._calculate_relevance(
                query, row[1], row[2]  # query, concept, claim
            )
            results.append(RetrievedKnowledge(
                id=row[0],
                concept=row[1],
                claim=row[2],
                confidence=row[3],
                status=row[4],
                source=row[5],
                created_at=row[6],
                use_count=row[7],
                freshness=row[8],
                relevance_score=relevance,
                knowledge_type="fact",
            ))

        # Sort by combined score (confidence * relevance * freshness)
        results.sort(
            key=lambda x: x.confidence * x.relevance_score * x.freshness,
            reverse=True,
        )
        # Filter out low-relevance results to prevent returning unrelated knowledge
        results = [r for r in results if r.relevance_score >= self.MIN_RELEVANCE]
        return results[:limit]

    def _retrieve_generalizations(
        self,
        search_terms: list[str],
        query: str,
        limit: int,
    ) -> list[RetrievedGeneralization]:
        """Retrieve relevant learned generalizations."""
        if not search_terms:
            return []

        like_conditions = []
        params = []
        for term in search_terms[:10]:
            like_conditions.append("(pattern LIKE ? OR description LIKE ?)")
            params.extend([f"%{term}%", f"%{term}%"])

        where_clause = " OR ".join(like_conditions)

        query_sql = f"""
            SELECT id, pattern, description, confidence, scope,
                   usage_count, success_rate
            FROM learned_generalizations
            WHERE ({where_clause})
            AND confidence >= ?
            ORDER BY confidence DESC, usage_count DESC
            LIMIT ?
        """
        params.extend([self.MIN_CONFIDENCE, limit])

        rows = self.db.fetch_all(query_sql, tuple(params))

        results = []
        for row in rows:
            relevance = self._calculate_relevance(query, row[1], row[2])
            results.append(RetrievedGeneralization(
                id=row[0],
                pattern=row[1],
                description=row[2],
                confidence=row[3],
                scope=row[4],
                usage_count=row[5],
                success_rate=row[6],
                relevance_score=relevance,
            ))

        results.sort(
            key=lambda x: x.confidence * x.relevance_score,
            reverse=True,
        )
        results = [r for r in results if r.relevance_score >= self.MIN_RELEVANCE]
        return results[:limit]

    def _retrieve_skills(
        self,
        search_terms: list[str],
        query: str,
        limit: int,
    ) -> list[RetrievedSkill]:
        """Retrieve relevant learned skills from BOTH skill systems.

        Queries both learned_skills (from Learning API) and
        skills/skill_steps (from SkillEngine), merging and deduplicating.
        """
        if not search_terms:
            return []

        seen_names: set[str] = set()
        results: list[RetrievedSkill] = []

        # ── Source 1: learned_skills table (Learning API) ──
        like_conditions = []
        params = []
        for term in search_terms[:10]:
            like_conditions.append("(name LIKE ? OR description LIKE ?)")
            params.extend([f"%{term}%", f"%{term}%"])

        where_clause = " OR ".join(like_conditions)

        query_sql = f"""
            SELECT id, name, description, procedure, confidence,
                   success_rate, experience_count
            FROM learned_skills
            WHERE ({where_clause})
            AND confidence >= ?
            ORDER BY confidence DESC, experience_count DESC
            LIMIT ?
        """
        params.extend([self.MIN_CONFIDENCE, limit])

        rows = self.db.fetch_all(query_sql, tuple(params))

        import json
        for row in rows:
            relevance = self._calculate_relevance(query, row[1], row[2])
            procedure = json.loads(row[3]) if row[3] else []
            name_lower = row[1].lower().strip()
            seen_names.add(name_lower)
            results.append(RetrievedSkill(
                id=row[0],
                name=row[1],
                description=row[2],
                procedure=procedure,
                confidence=row[4],
                success_rate=row[5],
                experience_count=row[6],
                relevance_score=relevance,
            ))

        # ── Source 2: skills + skill_steps tables (SkillEngine) ──
        try:
            skill_like_conditions = []
            skill_params = []
            for term in search_terms[:10]:
                skill_like_conditions.append("(s.name LIKE ? OR s.description LIKE ?)")
                skill_params.extend([f"%{term}%", f"%{term}%"])

            skill_where = " OR ".join(skill_like_conditions)
            skill_query = f"""
                SELECT s.id, s.name, s.description, s.proficiency,
                       s.usage_count,
                       GROUP_CONCAT(sa.action || '||' || sa.description, '||') as steps_raw
                FROM skills s
                LEFT JOIN skill_steps sa ON s.id = sa.skill_id
                WHERE ({skill_where})
                AND s.proficiency >= ?
                GROUP BY s.id
                ORDER BY s.proficiency DESC, s.usage_count DESC
                LIMIT ?
            """
            skill_params.extend([self.MIN_CONFIDENCE, limit])
            skill_rows = self.db.fetch_all(skill_query, tuple(skill_params))

            for row in skill_rows:
                name_lower = row[1].lower().strip()
                if name_lower in seen_names:
                    continue  # skip duplicates
                seen_names.add(name_lower)

                # Parse steps from GROUP_CONCAT
                procedure = []
                if row[5]:
                    for step_raw in row[5].split("||"):
                        parts = step_raw.split("||", 1)
                        if len(parts) == 2:
                            procedure.append({"action": parts[0], "description": parts[1]})

                relevance = self._calculate_relevance(query, row[1], row[2])
                results.append(RetrievedSkill(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    procedure=procedure,
                    confidence=row[3],
                    success_rate=0.0,
                    experience_count=row[4],
                    relevance_score=relevance,
                ))
        except Exception:
            pass  # skills table may not exist or have different schema

        results.sort(
            key=lambda x: x.confidence * x.relevance_score,
            reverse=True,
        )
        # Skills don't need MIN_RELEVANCE filter — SQL LIKE already matched them
        return results[:limit]

    def _retrieve_intent_patterns(
        self,
        search_terms: list[str],
        query: str,
        limit: int,
    ) -> list[RetrievedIntentPattern]:
        """Retrieve learned intent patterns that match the input.

        Fetches ALL active patterns, then filters by match in Python.
        This is correct because pattern matching is semantic (exact, partial,
        word overlap), not a simple SQL LIKE query.
        """
        try:
            query_sql = """
                SELECT id, pattern_text, intent, concept, conditions,
                       positive_examples, negative_examples, confidence, status
                FROM learned_intent_patterns
                WHERE status = 'ACTIVE'
                AND confidence >= ?
                ORDER BY confidence DESC
            """
            rows = self.db.fetch_all(query_sql, (self.MIN_CONFIDENCE,))
        except Exception:
            return []

        import json
        results = []
        for row in rows:
            if self._pattern_matches_query(row[1], row[3], query, search_terms):
                relevance = self._calculate_relevance(query, row[1], row[3])
                structure_match = self._compute_structure_match(query, row[2])
                # FILTER: Reject patterns with very low structure match
                # A greeting pattern should not override imperative queries
                if structure_match < 0.3:
                    continue
                conditions = json.loads(row[4]) if row[4] else []
                positive = json.loads(row[5]) if row[5] else []
                negative = json.loads(row[6]) if row[6] else []
                results.append(RetrievedIntentPattern(
                    id=row[0],
                    pattern_text=row[1],
                    intent=row[2],
                    concept=row[3],
                    conditions=conditions,
                    positive_examples=positive,
                    negative_examples=negative,
                    confidence=row[7],
                    status=row[8],
                    relevance_score=relevance,
                    structure_match=structure_match,
                ))

        results.sort(key=lambda x: x.confidence * x.relevance_score, reverse=True)
        results = [r for r in results if r.relevance_score >= self.MIN_RELEVANCE]
        return results[:limit]

    def _detect_query_structure(self, query: str) -> dict:
        """Detect the communicative structure of a query.

        Returns dict with scores for each structure type:
        - informational: information-seeking (what is, how does, explain)
        - imperative: action-requesting (write, create, make, help)
        - conversational: social/greeting (hello, how are you)
        - declarative: statement (I want, I need)
        """
        q = query.lower().strip()
        scores = {
            "informational": 0.0,
            "imperative": 0.0,
            "conversational": 0.0,
            "declarative": 0.0,
        }

        # Informational markers
        info_markers = [
            r'\bwhat is\b', r'\bwhat are\b', r'\bwhat was\b', r'\bwhat\'s\b',
            r'\bhow does\b', r'\bhow do\b', r'\bhow did\b', r'\bhow is\b',
            r'\bwho is\b', r'\bwho are\b', r'\bwho was\b',
            r'\bwhere is\b', r'\bwhere are\b',
            r'\bwhen was\b', r'\bwhen did\b',
            r'\bwhy does\b', r'\bwhy do\b', r'\bwhy is\b',
            r'\btell me about\b', r'\bexplain\b', r'\bdescribe\b',
            r'\bdefine\b', r'\bwhat does.*mean\b',
            r'\bkya hai\b', r'\bkya hain\b', r'\bkya hota\b',
            r'\bkaun hai\b', r'\bkahan hai\b', r'\bkab hua\b',
            r'\bkaise hota\b', r'\bkaise kaam\b',
            r'\bsamjhao\b', r'\bbatao\b', r'\bmeaning\b',
        ]
        for m in info_markers:
            if re.search(m, q):
                scores["informational"] += 1.0

        # Imperative markers (action requests)
        imp_markers = [
            r'^(write|create|make|build|generate|compose|draft|design)\b',
            r'\bwrite\b', r'\bcreate\b', r'\bmake\b', r'\bbuild\b',
            r'\bgenerate\b', r'\bcompose\b', r'\bdraft\b', r'\bdesign\b',
            r'\bhelp me\b', r'\bcan you\b', r'\bplease\b',
            r'\bcode\b', r'\bprogram\b', r'\bimplement\b',
            r'\bsolve\b', r'\bcalculate\b', r'\bconvert\b',
        ]
        for m in imp_markers:
            if re.search(m, q):
                scores["imperative"] += 1.0

        # Conversational markers (greetings, social)
        conv_markers = [
            r'^(hi|hello|hey|namaste|salaam|assalam|radhe|ram ram|adaab|pranam)\b',
            r'\bhow are you\b', r'\bhow\'s it going\b',
            r'\bkya haal hai\b', r'\bkya chal raha\b', r'\bkaise ho\b',
            r'\bkaisa hai\b', r'\bwhat\'s up\b', r'\bsup\b',
            r'\bgood morning\b', r'\bgood night\b', r'\bbye\b',
        ]
        for m in conv_markers:
            if re.search(m, q):
                scores["conversational"] += 1.0

        # Declarative markers (statements of intent)
        decl_markers = [
            r'\bi want\b', r'\bi need\b', r'\bi would like\b',
            r'\bcan you\b', r'\bcould you\b', r'\bi am\b',
            r'\bmai\b', r'\bmera\b', r'\bmujhe\b',
        ]
        for m in decl_markers:
            if re.search(m, q):
                scores["declarative"] += 1.0

        # Normalize
        total = sum(scores.values())
        if total > 0:
            for k in scores:
                scores[k] /= total

        return scores

    def _compute_structure_match(self, query: str, pattern_intent: str) -> float:
        """Compute how well the query structure matches the pattern's intent.

        Returns 0.0 to 1.0:
        - 1.0 = structures align (imperative query + creative/task pattern)
        - 0.5 = neutral/unclear
        - 0.0 = structures contradict (informational query + creative pattern)
        """
        structure = self._detect_query_structure(query)

        # Map intent to expected query structure
        intent_structure_map = {
            "creative": "imperative",
            "code": "imperative",
            "task": "imperative",
            "greeting": "conversational",
            "casual": "conversational",
            "conversation": "conversational",
            "factual": "informational",
            "informational": "informational",
            "research": "informational",
        }
        expected_structure = intent_structure_map.get(pattern_intent, "")

        if not expected_structure:
            return 0.5  # Unknown intent, neutral score

        # Get the dominant query structure
        dominant = max(structure, key=structure.get)
        dominant_score = structure[dominant]

        # If dominant structure matches expected, high score
        if dominant == expected_structure and dominant_score > 0.3:
            return 1.0

        # If informational query and non-factual pattern, strong mismatch
        if structure["informational"] > 0.3 and pattern_intent in ("creative", "greeting", "casual"):
            return 0.1

        # If imperative query and informational pattern, mild mismatch
        if structure["imperative"] > 0.3 and pattern_intent in ("factual", "informational"):
            return 0.3

        # If conversational query and non-conversational pattern, mismatch
        if structure["conversational"] > 0.3 and pattern_intent not in ("greeting", "casual", "conversation"):
            return 0.2

        return 0.5  # Default neutral

    def _pattern_matches_query(
        self,
        pattern_text: str,
        concept: str,
        query: str,
        search_terms: list[str],
    ) -> bool:
        """Check if an intent pattern matches the current query.

        Uses strict matching: exact, substring, or majority word overlap.
        Single-word overlap (e.g. 'what' in 'what's up' vs 'What is Python?')
        is NOT sufficient — requires >= 50% of pattern words to match.

        Informational queries (containing 'what is', 'how does', 'kya hai', etc.)
        are NOT matched by creative patterns — they are definition requests.
        """
        query_lower = query.lower().strip()
        pattern_lower = pattern_text.lower().strip()
        concept_lower = concept.lower().strip() if concept else ""

        # Detect informational queries — these should NOT match creative patterns
        _INFO_MARKERS = [
            "what is", "what are", "what was", "what's",
            "how does", "how do", "how did", "how is",
            "who is", "who are", "who was",
            "where is", "where are",
            "when was", "when did",
            "why does", "why do", "why is",
            "tell me about", "explain", "describe",
            "kya hai", "kya hain", "kya hota hai", "kya hoti hai",
            "kya hai ye", "kya hai vo",
            "kaun hai", "kahan hai", "kab hua", "kyun hai",
            "kaise hota hai", "kaise kaam karta hai",
            "samjhao", "batao about", "meaning kya hai",
            "meaning samjhao", "definition",
        ]
        is_informational = any(marker in query_lower for marker in _INFO_MARKERS)

        # Direct concept match — but NOT for informational queries matching non-factual patterns
        if concept_lower and concept_lower in query_lower:
            # If query is informational, only allow factual/informational/task patterns to match
            if is_informational:
                # Map concepts to their intent categories
                _CONCEPT_INTENT_MAP = {
                    "creative": "creative", "paraphrase_poetry": "creative",
                    "paraphrase_story": "creative", "short_poetry": "creative",
                    "short_story": "creative", "short_caption": "creative",
                    "short_humor": "creative", "short_brainstorm": "creative",
                    "short_one_liner": "creative", "short_dialogue": "creative",
                    "contrast_poetry": "creative", "contrast_creation": "creative",
                    "poetry": "creative", "story": "creative", "humor": "creative",
                    "caption": "creative", "brainstorm": "creative", "naming": "creative",
                    "slogan": "creative", "dialogue": "creative", "script": "creative",
                    "music": "creative", "one_liner": "creative", "description": "creative",
                    "inspiration": "creative", "worldbuilding": "creative",
                    "suggestion": "creative",
                    "greeting": "greeting", "casual": "casual", "conversation": "casual",
                }
                concept_intent = _CONCEPT_INTENT_MAP.get(concept_lower, "")
                if concept_intent in ("creative", "greeting", "casual"):
                    return False
            return True

        # Exact pattern match (single-word greetings like "salaam")
        if pattern_lower == query_lower:
            return True

        # Pattern is contained in query
        # For single-word patterns, require word boundary or prefix match
        # to avoid false positives like "hi" matching inside "machine"
        # but still allow "hiii" to match "hi" (prefix)
        if pattern_lower in query_lower:
            pattern_word_count = len(re.findall(r'\b[a-z]{2,}\b', pattern_lower))
            # Use UNFILTERED word count for length check (function words still count as words)
            raw_query_word_count = len(re.findall(r'\b[a-z]{2,}\b', query_lower))
            if pattern_word_count == 1:
                if raw_query_word_count <= 4:
                    # Match if pattern is a whole word OR a prefix of a query word
                    if (re.search(r'\b' + re.escape(pattern_lower) + r'\b', query_lower) or
                        any(qw.startswith(pattern_lower) for qw in re.findall(r'\b[a-z]{2,}\b', query_lower))):
                        return True
            else:
                # Multi-word pattern: require overlap ratio check, not just containment
                _FUNCTION_WORDS = {"kya", "kaise", "kab", "kahan", "kaun", "kyun", "aur",
                                   "batao", "the", "is", "are", "was", "were", "a", "an",
                                   "the", "of", "in", "on", "at", "to", "for", "what",
                                   "how", "when", "where", "who", "why", "do", "does"}
                p_words = set(re.findall(r'\b[a-z]{2,}\b', pattern_lower)) - _FUNCTION_WORDS
                q_words = set(re.findall(r'\b[a-z]{2,}\b', query_lower)) - _FUNCTION_WORDS
                if p_words:
                    overlap = set()
                    for pw in p_words:
                        for qw in q_words:
                            if pw == qw or pw.startswith(qw) or qw.startswith(pw):
                                overlap.add(pw)
                                break
                    overlap_ratio = len(overlap) / len(p_words)
                    if overlap_ratio > 0.5:
                        return True

        # Word overlap — require strict majority of pattern words to match
        # Common question/function words are excluded to avoid false positives.
        # Prefix matching is used so "recommend" matches "recommendation".
        # Informational queries should NOT match creative patterns via word overlap.
        _FUNCTION_WORDS = {"kya", "kaise", "kab", "kahan", "kaun", "kyun", "aur",
                           "batao", "the", "is", "are", "was", "were", "a", "an",
                           "the", "of", "in", "on", "at", "to", "for", "what",
                           "how", "when", "where", "who", "why", "do", "does"}
        pattern_words = set(re.findall(r'\b[a-z]{2,}\b', pattern_lower)) - _FUNCTION_WORDS
        query_words = set(re.findall(r'\b[a-z]{2,}\b', query_lower)) - _FUNCTION_WORDS
        raw_query_word_count = len(re.findall(r'\b[a-z]{2,}\b', query_lower))
        if pattern_words:
            # Check overlap with prefix matching (e.g. "recommend" matches "recommendation")
            overlap = set()
            for pw in pattern_words:
                for qw in query_words:
                    if pw == qw or pw.startswith(qw) or qw.startswith(pw):
                        overlap.add(pw)
                        break
            if len(pattern_words) == 1:
                if overlap and raw_query_word_count <= 4:
                    # Block non-factual patterns matching informational queries
                    if is_informational:
                        _NON_FACTUAL_CONCEPTS = {"poetry", "story", "humor", "caption",
                                                   "brainstorm", "naming", "slogan", "dialogue",
                                                   "script", "music", "one_liner",
                                                   "greeting", "casual", "conversation"}
                        if concept_lower in _NON_FACTUAL_CONCEPTS:
                            return False
                    return True
            else:
                overlap_ratio = len(overlap) / len(pattern_words)
                if overlap_ratio > 0.5:
                    # Block non-factual patterns matching informational queries
                    if is_informational:
                        _NON_FACTUAL_CONCEPTS = {"poetry", "story", "humor", "caption",
                                                   "brainstorm", "naming", "slogan", "dialogue",
                                                   "script", "music", "one_liner",
                                                   "paraphrase_poetry", "paraphrase_story",
                                                   "short_poetry", "short_story", "short_caption",
                                                   "short_humor", "short_brainstorm", "short_one_liner",
                                                   "short_dialogue", "contrast_poetry", "contrast_creation",
                                                   "greeting", "casual", "conversation"}
                        if concept_lower in _NON_FACTUAL_CONCEPTS:
                            return False
                    return True

        return False

    def _calculate_relevance(
        self,
        query: str,
        concept: str,
        description: str,
    ) -> float:
        """Calculate relevance score between query and a knowledge item.

        Uses a strict topical overlap approach:
        - Concept words are weighted heavily (the concept is the topic)
        - For short queries (<=2 content words), 1 concept match is sufficient
        - For longer queries, require meaningful overlap
        - Generic/common words in both are penalized
        """
        # Stop words + very generic words that appear everywhere
        relevance_stopwords = {
            'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but',
            'in', 'with', 'to', 'for', 'of', 'not', 'no', 'can', 'had', 'has',
            'was', 'were', 'are', 'be', 'been', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'shall', 'this', 'that',
            'these', 'those', 'it', 'its', 'my', 'your', 'his', 'her', 'our',
            'their', 'what', 'how', 'who', 'when', 'where', 'why', 'than',
            'then', 'so', 'if', 'about', 'up', 'out', 'just', 'also', 'very',
            'kya', 'hai', 'ho', 'ka', 'ki', 'ke', 'se', 'ko', 'me', 'ye',
            'wo', 'mai', 'mera', 'tum', 'tumhara', 'hain',
            # Very generic content words that appear in many topics
            'information', 'knowledge', 'fact', 'definition', 'process',
            'system', 'example', 'type', 'form', 'part', 'use', 'way',
            'make', 'made', 'called', 'known', 'based', 'found', 'used',
            'include', 'involves', 'related', 'similar', 'different',
            'general', 'specific', 'various', 'common', 'important',
            'matter', 'energy', 'state', 'change', 'effect', 'result',
            'cause', 'study', 'theory', 'concept', 'principle',
            # Additional generic English words
            'there', 'here', 'thing', 'things', 'something', 'nothing',
            'going', 'getting', 'having', 'being', 'doing', 'saying',
            'like', 'want', 'need', 'know', 'think', 'see', 'look',
        }
        query_words = set(re.findall(r'\b[a-zA-Z]{2,}\b', query.lower())) - relevance_stopwords
        concept_words = set(re.findall(r'\b[a-zA-Z]{2,}\b', (concept or "").lower())) - relevance_stopwords
        desc_words = set(re.findall(r'\b[a-zA-Z]{2,}\b', (description or "").lower())) - relevance_stopwords

        all_item_words = concept_words | desc_words

        if not query_words or not all_item_words:
            return 0.0

        overlap = query_words & all_item_words

        # Concept overlap is the strongest signal — the concept IS the topic
        concept_overlap = query_words & concept_words
        query_concept_ratio = len(concept_overlap) / max(len(query_words), 1)
        desc_ratio = len(overlap) / max(len(query_words | all_item_words), 1)

        # For short queries (<=2 content words), 1 concept match = strong relevance
        if len(query_words) <= 2:
            if concept_overlap:
                return max(0.3, 0.6 * query_concept_ratio + 0.4 * desc_ratio)
            elif len(overlap) >= 1:
                # Single-word query matching description — boost relevance
                # to allow retrieval when the query word appears in the claim
                return max(0.3, 0.5 * desc_ratio)
            return 0.0

        # For longer queries, require meaningful overlap
        if len(overlap) < 2:
            return 0.0

        # Weighted score: concept match dominates
        if len(concept_overlap) >= 2:
            score = 0.7 * query_concept_ratio + 0.3 * desc_ratio
        elif len(concept_overlap) == 1:
            score = 0.4 * query_concept_ratio + 0.3 * desc_ratio
        else:
            # Only description overlap — weak signal, cap low
            score = min(0.3, 0.5 * desc_ratio)

        return score

    def record_usage(self, knowledge_id: int, success: bool):
        """Record that a piece of knowledge was used during inference."""
        self.db.execute(
            """UPDATE learned_knowledge
               SET usage_count = usage_count + 1
               WHERE id = ?""",
            (knowledge_id,),
        )
        # Update freshness
        self.db.execute(
            """INSERT OR REPLACE INTO knowledge_freshness
               (knowledge_id, last_used, use_count, freshness)
               VALUES (?, ?, 1, 1.0)
               ON CONFLICT(knowledge_id) DO UPDATE SET
               last_used = excluded.last_used,
               use_count = use_count + 1,
               freshness = MIN(1.0, freshness + 0.05)""",
            (knowledge_id, time.time()),
        )

    def get_retrieval_stats(self) -> dict:
        """Get statistics about the learning retrieval system."""
        knowledge_count = self.db.fetch_one(
            "SELECT COUNT(*) FROM learned_knowledge WHERE status IN ('VERIFIED', 'PROBABLE')"
        )
        generalization_count = self.db.fetch_one(
            "SELECT COUNT(*) FROM learned_generalizations WHERE confidence >= 0.3"
        )
        skill_count = self.db.fetch_one(
            "SELECT COUNT(*) FROM learned_skills WHERE confidence >= 0.3"
        )
        return {
            "active_knowledge": knowledge_count[0] if knowledge_count else 0,
            "active_generalizations": generalization_count[0] if generalization_count else 0,
            "active_skills": skill_count[0] if skill_count else 0,
        }
