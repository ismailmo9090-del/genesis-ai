"""Learning engine implementing a full learning pipeline for Genesis AI."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from genesis_ai.database.db import DatabaseManager


@dataclass
class LearningResult:
    success: bool = False
    knowledge_id: Optional[int] = None
    concept_id: Optional[int] = None
    is_duplicate: bool = False
    duplicate_of: Optional[int] = None
    contradictions: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    steps_completed: list[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class CorrectionEvent:
    old_belief: str
    new_belief: str
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    knowledge_id: Optional[int] = None


class LearningEngine:
    """Full learning pipeline: OBSERVE -> UNDERSTAND -> EXTRACT -> COMPARE -> VERIFY ->
    GENERALIZE -> STORE -> CONNECT -> TEST -> IMPROVE."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def learn_from_interaction(
        self, user_message: str, system_response: str, feedback: dict = None
    ) -> LearningResult:
        result = LearningResult()
        feedback = feedback or {}
        try:
            result.steps_completed.append("OBSERVE")
            observations = self._observe_interaction(user_message, system_response)

            result.steps_completed.append("UNDERSTAND")
            understanding = self._understand_interaction(observations)

            result.steps_completed.append("EXTRACT")
            knowledge_items = self._extract_knowledge(understanding, user_message, system_response)

            for item in knowledge_items:
                result.steps_completed.append("COMPARE")
                is_dup, existing_id = self.duplicate_detection(item)
                if is_dup:
                    result.is_duplicate = True
                    result.duplicate_of = existing_id
                    continue

                result.steps_completed.append("VERIFY")
                contradictions = self.contradiction_detection(item)
                result.contradictions.extend(contradictions)

                result.steps_completed.append("GENERALIZE")
                generalized = self._generalize_knowledge(item)

                result.steps_completed.append("STORE")
                knowledge_id = self._store_knowledge(generalized, feedback)
                result.knowledge_id = knowledge_id

                result.steps_completed.append("CONNECT")
                concept = self.create_concept_from_text(generalized.get("claim", ""))
                if concept:
                    result.concept_id = concept.get("id")

                result.steps_completed.append("TEST")
                self._test_knowledge(knowledge_id)

                result.steps_completed.append("IMPROVE")
                self._improve_knowledge(knowledge_id, feedback)

            result.confidence = self.confidence_estimation(
                source_count=1,
                source_reliability=feedback.get("reliability", 0.5),
                agreement=1.0 if not result.contradictions else 0.3,
            )
            result.success = True
        except Exception as e:
            result.error = str(e)
        return result

    def learn_from_research(self, research_results: dict) -> LearningResult:
        result = LearningResult()
        try:
            findings = research_results.get("findings", [])
            sources = research_results.get("sources", [])

            result.steps_completed.append("OBSERVE")
            result.steps_completed.append("UNDERSTAND")

            for finding in findings:
                item = {
                    "claim": finding.get("claim", finding.get("text", "")),
                    "source": finding.get("source", ""),
                    "confidence": finding.get("confidence", 0.5),
                }

                result.steps_completed.append("EXTRACT")
                is_dup, existing_id = self.duplicate_detection(item)
                if is_dup:
                    result.is_duplicate = True
                    result.duplicate_of = existing_id
                    continue

                result.steps_completed.append("COMPARE")
                contradictions = self.contradiction_detection(item)
                result.contradictions.extend(contradictions)

                result.steps_completed.append("VERIFY")
                result.steps_completed.append("GENERALIZE")
                generalized = self._generalize_knowledge(item)

                result.steps_completed.append("STORE")
                knowledge_id = self._store_knowledge(
                    generalized,
                    {"source": item.get("source"), "reliability": item.get("confidence", 0.5)},
                )
                result.knowledge_id = knowledge_id

                result.steps_completed.append("CONNECT")
                concept = self.create_concept_from_text(generalized.get("claim", ""))
                if concept:
                    result.concept_id = concept.get("id")

                result.steps_completed.append("TEST")
                result.steps_completed.append("IMPROVE")

            result.confidence = self.confidence_estimation(
                source_count=len(sources),
                source_reliability=research_results.get("confidence", 0.5),
                agreement=1.0 - (len(result.contradictions) / max(len(findings), 1)),
            )
            result.success = True
        except Exception as e:
            result.error = str(e)
        return result

    def learn_from_experience(
        self, task: str, approach: str, result: str, success: bool
    ) -> int:
        lessons = self._extract_lessons(task, approach, result, success)
        experience_id = self.db.insert_experience(
            task_description=task,
            outcome=result,
            success=success,
            lessons_learned=lessons,
        )
        if success:
            self.db.insert_knowledge(
                concept_id=self._ensure_concept(task),
                claim=f"Approach '{approach}' succeeded for task '{task}': {result}",
                claim_type="experience",
                confidence=0.8,
            )
        else:
            self.db.insert_knowledge(
                concept_id=self._ensure_concept(task),
                claim=f"Approach '{approach}' failed for task '{task}': {result}",
                claim_type="experience",
                confidence=0.7,
            )
        return experience_id

    def duplicate_detection(self, new_knowledge: dict) -> tuple[bool, Optional[int]]:
        claim = new_knowledge.get("claim", "")
        if not claim:
            return False, None
        existing = self.db.search_knowledge(claim, limit=10)
        for item in existing:
            similarity = self._text_similarity(claim, item.get("claim", ""))
            if similarity > 0.85:
                return True, item["id"]
        return False, None

    def contradiction_detection(self, new_knowledge: dict) -> list[dict]:
        claim = new_knowledge.get("claim", "")
        if not claim:
            return []
        contradictions = []
        existing = self.db.search_knowledge(claim, limit=20)
        for item in existing:
            if self._claims_contradict(claim, item.get("claim", "")):
                contradictions.append({
                    "existing_claim": item.get("claim"),
                    "existing_knowledge_id": item.get("id"),
                    "new_claim": claim,
                    "confidence": self._contradiction_confidence(claim, item.get("claim", "")),
                })
        return contradictions

    def confidence_estimation(
        self, source_count: int, source_reliability: float, agreement: float
    ) -> float:
        source_factor = min(source_count / 5.0, 1.0)
        reliability_factor = source_reliability
        agreement_factor = agreement
        score = (source_factor * 0.3) + (reliability_factor * 0.35) + (agreement_factor * 0.35)
        if source_count >= 3:
            score = min(1.0, score + 0.05)
        return round(max(0.0, min(1.0, score)), 4)

    def create_concept_from_text(self, text: str) -> Optional[dict]:
        if not text:
            return None
        name = self._extract_concept_name(text)
        if not name:
            return None
        existing = self.db.get_concept_by_name(name)
        if existing:
            return {"id": existing["id"], "name": existing["name"]}
        concept_id = self.db.insert_concept(
            name=name,
            description=text[:500] if len(text) > 500 else text,
            domain="learned",
            confidence=0.5,
        )
        return {"id": concept_id, "name": name}

    def create_relationships(
        self, concept: dict, related_concepts: list[dict]
    ) -> list[int]:
        if not concept:
            return []
        concept_id = concept.get("id")
        if not concept_id:
            return []
        relationship_ids = []
        for related in related_concepts:
            target_name = related.get("name", related.get("concept_name", ""))
            relation_type = related.get("relation_type", "related_to")
            if not target_name:
                continue
            target = self.db.get_concept_by_name(target_name)
            if not target:
                target_id = self.db.insert_concept(
                    name=target_name,
                    domain=related.get("domain", "learned"),
                    confidence=0.5,
                )
            else:
                target_id = target["id"]
            try:
                rel_id = self.db.insert_relationship(
                    source_concept_id=concept_id,
                    target_concept_id=target_id,
                    relation_type=relation_type,
                    strength=related.get("strength", 0.5),
                )
                if rel_id:
                    relationship_ids.append(rel_id)
            except Exception:
                pass
        return relationship_ids

    def get_learning_stats(self) -> dict:
        with self.db.get_conn() as conn:
            concept_count = conn.execute("SELECT COUNT(*) as cnt FROM concepts").fetchone()["cnt"]
            knowledge_count = conn.execute("SELECT COUNT(*) as cnt FROM knowledge").fetchone()["cnt"]
            experience_count = conn.execute("SELECT COUNT(*) as cnt FROM experiences").fetchone()["cnt"]
            relationship_count = conn.execute("SELECT COUNT(*) as cnt FROM relationships").fetchone()["cnt"]
            try:
                memory_count = conn.execute("SELECT COUNT(*) as cnt FROM memories").fetchone()["cnt"]
            except Exception:
                memory_count = 0
            try:
                verified = conn.execute(
                    "SELECT COUNT(*) as cnt FROM knowledge WHERE verification_status = 'verified'"
                ).fetchone()["cnt"]
            except Exception:
                verified = 0
            try:
                disputed = conn.execute(
                    "SELECT COUNT(*) as cnt FROM knowledge WHERE verification_status = 'disputed'"
                ).fetchone()["cnt"]
            except Exception:
                disputed = 0
        return {
            "concepts_learned": concept_count,
            "knowledge_claims": knowledge_count,
            "experiences_recorded": experience_count,
            "relationships_formed": relationship_count,
            "memories_stored": memory_count,
            "verified_knowledge": verified,
            "disputed_knowledge": disputed,
        }

    def process_feedback(
        self, old_belief: str, user_correction: str
    ) -> CorrectionEvent:
        event = CorrectionEvent(
            old_belief=old_belief,
            new_belief=user_correction,
            reason="user_correction",
        )
        existing = self.db.search_knowledge(old_belief, limit=5)
        if existing:
            knowledge = existing[0]
            self.db.update_knowledge(
                knowledge["id"],
                claim=user_correction,
                confidence=min(knowledge.get("confidence", 0.5) + 0.1, 1.0),
            )
            event.knowledge_id = knowledge["id"]
        else:
            concept = self.create_concept_from_text(user_correction)
            concept_id = concept["id"] if concept else self._ensure_concept(old_belief)
            knowledge_id = self.db.insert_knowledge(
                concept_id=concept_id,
                claim=user_correction,
                claim_type="correction",
                confidence=0.7,
            )
            event.knowledge_id = knowledge_id
        return event

    # ── Internal pipeline steps ──

    def _observe_interaction(self, user_message: str, system_response: str) -> dict:
        return {
            "user_message": user_message,
            "system_response": system_response,
            "user_words": set(re.findall(r'\b[a-z]{3,}\b', user_message.lower())),
            "response_words": set(re.findall(r'\b[a-z]{3,}\b', system_response.lower())),
        }

    def _understand_interaction(self, observations: dict) -> dict:
        user_words = observations["user_words"]
        response_words = observations["response_words"]
        overlap = user_words & response_words
        topic_words = [w for w in overlap if len(w) > 4]
        return {
            "topic_keywords": topic_words,
            "user_intent": observations["user_message"][:200],
            "system_knowledge": observations["system_response"][:500],
            "engagement_score": len(overlap) / max(len(user_words), 1),
        }

    def _extract_knowledge(self, understanding: dict, user_message: str, system_response: str) -> list[dict]:
        items = []
        sentences = re.split(r'[.!?]+', system_response)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20:
                items.append({
                    "claim": sentence,
                    "topic_keywords": understanding.get("topic_keywords", []),
                    "source": "interaction",
                    "confidence": 0.6,
                })
        if not items and system_response.strip():
            items.append({
                "claim": system_response.strip()[:500],
                "topic_keywords": understanding.get("topic_keywords", []),
                "source": "interaction",
                "confidence": 0.5,
            })
        return items

    def _generalize_knowledge(self, item: dict) -> dict:
        claim = item.get("claim", "")
        generalized = claim
        specific_patterns = [
            (r'\bI\b', 'the system'),
            (r'\byou\b', 'the user'),
            (r'\bmy\b', 'the user\'s'),
        ]
        for pattern, replacement in specific_patterns:
            generalized = re.sub(pattern, replacement, generalized, flags=re.IGNORECASE)
        return {
            "claim": generalized,
            "original_claim": claim,
            "topic_keywords": item.get("topic_keywords", []),
            "source": item.get("source", "interaction"),
            "confidence": item.get("confidence", 0.5),
        }

    def _store_knowledge(self, generalized: dict, feedback: dict) -> int:
        concept_name = generalized.get("topic_keywords", ["general"])[0] if generalized.get("topic_keywords") else "general"
        concept = self.db.get_concept_by_name(concept_name)
        if not concept:
            concept_id = self.db.insert_concept(
                name=concept_name,
                domain="learned",
                confidence=0.5,
            )
        else:
            concept_id = concept["id"]
        source_id = None
        source_name = generalized.get("source", "interaction")
        if source_name:
            sources = self.db.list_sources()
            for s in sources:
                if s["name"] == source_name:
                    source_id = s["id"]
                    break
            if not source_id:
                source_id = self.db.insert_source(
                    name=source_name,
                    source_type="interaction",
                    reliability=feedback.get("reliability", 0.5),
                )
        knowledge_id = self.db.insert_knowledge(
            concept_id=concept_id,
            source_id=source_id,
            claim=generalized.get("claim", ""),
            claim_type="learned",
            confidence=generalized.get("confidence", 0.5),
        )
        return knowledge_id

    def _test_knowledge(self, knowledge_id: int):
        knowledge = self.db.get_knowledge(knowledge_id)
        if not knowledge:
            return
        related = self.db.get_knowledge_for_concept(knowledge["concept_id"])
        supporting = sum(1 for k in related if k["id"] != knowledge_id)
        if supporting >= 2:
            self.db.update_knowledge(knowledge_id, verification_status="probable")

    def _improve_knowledge(self, knowledge_id: int, feedback: dict):
        if not feedback:
            return
        rating = feedback.get("rating")
        if rating is not None and rating >= 4:
            knowledge = self.db.get_knowledge(knowledge_id)
            if knowledge:
                new_conf = min(1.0, knowledge.get("confidence", 0.5) + 0.1)
                self.db.update_knowledge(knowledge_id, confidence=new_conf)

    def _extract_concept_name(self, text: str) -> str:
        text = text.strip()
        if len(text) < 3:
            return ""
        words = text.split()
        if len(words) <= 5:
            return text.title()
        return " ".join(words[:5]).title()

    def _ensure_concept(self, name: str) -> int:
        concept = self.db.get_concept_by_name(name)
        if concept:
            return concept["id"]
        return self.db.insert_concept(name=name, domain="general", confidence=0.5)

    def _extract_lessons(self, task: str, approach: str, result: str, success: bool) -> str:
        if success:
            return f"Task '{task}' completed successfully using approach: {approach}. Outcome: {result}"
        return f"Task '{task}' failed with approach: {approach}. Error: {result}. Consider alternative approaches."

    def _text_similarity(self, text_a: str, text_b: str) -> float:
        words_a = set(re.findall(r'\b[a-z]{3,}\b', text_a.lower()))
        words_b = set(re.findall(r'\b[a-z]{3,}\b', text_b.lower()))
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    def _claims_contradict(self, claim_a: str, claim_b: str) -> bool:
        words_a = set(re.findall(r'\b[a-z]{4,}\b', claim_a.lower()))
        words_b = set(re.findall(r'\b[a-z]{4,}\b', claim_b.lower()))
        common = words_a & words_b
        if len(common) < 2:
            return False
        negation_words = {"not", "never", "no", "neither", "nor", "n't", "doesn't", "isn't", "wasn't", "aren't"}
        neg_a = bool(negation_words & words_a)
        neg_b = bool(negation_words & words_b)
        if neg_a != neg_b:
            return True
        antonym_pairs = [
            ("increase", "decrease"), ("rise", "fall"), ("better", "worse"),
            ("more", "less"), ("higher", "lower"), ("true", "false"),
            ("possible", "impossible"), ("safe", "dangerous"),
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
        negation_words = {"not", "never", "no", "neither", "nor", "n't"}
        neg_a = bool(negation_words & words_a)
        neg_b = bool(negation_words & words_b)
        neg_score = 0.5 if neg_a != neg_b else 0.0
        score = 0.3 + (jaccard * 0.4) + neg_score
        return round(min(1.0, score), 4)
