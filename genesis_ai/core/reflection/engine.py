"""Reflection engine for meta-cognitive analysis of tasks and conversations."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from genesis_ai.database.db import DatabaseManager
from genesis_ai.knowledge.graph.engine import KnowledgeGraph


@dataclass
class ReflectionResult:
    what_learned: list[str] = field(default_factory=list)
    what_failed: list[str] = field(default_factory=list)
    what_worked: list[str] = field(default_factory=list)
    missing_knowledge: list[str] = field(default_factory=list)
    contradictions_found: list[dict] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)


class ReflectionEngine:
    """Meta-cognitive engine that reflects on tasks and conversations to extract lessons."""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.graph = KnowledgeGraph(db)

    def reflect_on_task(self, task_result: dict) -> ReflectionResult:
        result = ReflectionResult()
        task = task_result.get("task", "")
        outcome = task_result.get("outcome", "")
        success = task_result.get("success", False)
        approach = task_result.get("approach", "")
        errors = task_result.get("errors", [])
        duration = task_result.get("duration_ms", 0)

        if success:
            result.what_worked.append(
                f"Task '{task}' completed successfully using approach: {approach}"
            )
            self._store_reflection_knowledge(
                task, approach, outcome, success=True
            )
        else:
            result.what_failed.append(
                f"Task '{task}' failed with approach: {approach}. Errors: {errors}"
            )
            self._store_reflection_knowledge(
                task, approach, outcome, success=False
            )

        if duration > 0:
            if duration < 5000:
                result.what_worked.append(f"Task completed quickly ({duration}ms)")
            elif duration > 30000:
                result.what_failed.append(f"Task took too long ({duration}ms)")

        if errors:
            for error in errors:
                result.what_failed.append(f"Error encountered: {error}")

        related_concepts = self.graph.search_concepts(task)
        if not related_concepts:
            result.missing_knowledge.append(
                f"No existing knowledge found for task domain: {task}"
            )

        knowledge_items = self.db.search_knowledge(task, limit=5)
        for item in knowledge_items:
            if item.get("verification_status") == "disputed":
                result.contradictions_found.append({
                    "claim": item.get("claim"),
                    "knowledge_id": item.get("id"),
                })

        if not success:
            result.improvements.append(
                f"Consider alternative approaches for task: {task}"
            )
            result.improvements.append(
                "Gather more context before attempting similar tasks"
            )
        if errors:
            result.improvements.append(
                "Add error handling and validation before execution"
            )

        return result

    def reflect_on_conversation(self, conversation: dict) -> ReflectionResult:
        result = ReflectionResult()
        messages = conversation.get("messages", [])
        user_messages = [m for m in messages if m.get("role") == "user"]
        assistant_messages = [m for m in messages if m.get("role") == "assistant"]

        total = len(messages)
        if total == 0:
            result.improvements.append("Empty conversation - no reflection possible")
            return result

        topics = set()
        for msg in user_messages:
            content = msg.get("content", "")
            words = set(re.findall(r'\b[a-z]{4,}\b', content.lower()))
            topics.update(words)

        if topics:
            result.what_learned.append(
                f"Conversation covered topics: {', '.join(list(topics)[:10])}"
            )

        unanswered = []
        for i, msg in enumerate(user_messages):
            content = msg.get("content", "")
            if "?" in content:
                has_response = False
                for j in range(i + 1, min(i + 3, total)):
                    if messages[j].get("role") == "assistant":
                        has_response = True
                        break
                if not has_response:
                    unanswered.append(content[:100])
        if unanswered:
            result.what_failed.append(
                f"{len(unanswered)} question(s) may have been unanswered"
            )

        avg_response_length = 0
        if assistant_messages:
            avg_response_length = sum(
                len(m.get("content", "")) for m in assistant_messages
            ) / len(assistant_messages)
            if avg_response_length > 500:
                result.improvements.append(
                    "Consider shorter, more focused responses"
                )
            elif avg_response_length < 50:
                result.improvements.append(
                    "Consider more detailed responses"
                )

        for msg in assistant_messages:
            content = msg.get("content", "")
            if "I don't know" in content or "I'm not sure" in content:
                result.missing_knowledge.append(
                    f"Lack of knowledge expressed: {content[:100]}"
                )

        knowledge_used = self._identify_knowledge_used(messages)
        if knowledge_used:
            result.what_worked.append(
                f"Used {len(knowledge_used)} knowledge items in conversation"
            )

        contradictions = self._check_conversation_contradictions(messages)
        result.contradictions_found.extend(contradictions)

        if len(user_messages) > 0 and len(assistant_messages) > 0:
            ratio = len(assistant_messages) / len(user_messages)
            if ratio < 0.5:
                result.improvements.append("User seems to dominate - consider more engagement")
            elif ratio > 2.0:
                result.improvements.append("Assistant dominates - listen more to user")

        self._store_conversation_reflection(conversation, result)
        return result

    def generate_reflection_record(
        self, task: str, result: dict, learning: dict, knowledge_used: list[dict]
    ) -> dict:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task": task,
            "result_summary": {
                "success": result.get("success", False),
                "outcome": result.get("outcome", ""),
                "duration_ms": result.get("duration_ms", 0),
                "approach": result.get("approach", ""),
            },
            "learning": {
                "what_learned": learning.get("what_learned", []),
                "what_failed": learning.get("what_failed", []),
                "what_worked": learning.get("what_worked", []),
                "missing_knowledge": learning.get("missing_knowledge", []),
                "improvements": learning.get("improvements", []),
            },
            "knowledge_used": [
                {
                    "claim": k.get("claim", ""),
                    "confidence": k.get("confidence", 0),
                    "source": k.get("source", ""),
                }
                for k in knowledge_used
            ],
            "meta": {
                "knowledge_count": len(knowledge_used),
                "issues_found": len(learning.get("what_failed", [])),
                "improvements_suggested": len(learning.get("improvements", [])),
            },
        }
        task_concept = self.graph.search_concepts(task)
        if task_concept:
            self.db.insert_memory(
                user_id=1,
                key=f"reflection:{task[:50]}",
                value=json.dumps(record),
                memory_type="reflection",
                importance=0.7 if result.get("success") else 0.8,
            )
        return record

    def get_reflection_history(self, limit: int = 20) -> list[dict]:
        memories = self.db.search_memories(user_id=1, query="reflection", memory_type="reflection", limit=limit)
        history = []
        for mem in memories:
            try:
                record = json.loads(mem.get("value", "{}"))
                record["memory_id"] = mem.get("id")
                record["importance"] = mem.get("importance", 0)
                history.append(record)
            except (json.JSONDecodeError, TypeError):
                continue
        return history

    def identify_knowledge_gaps(self, knowledge_graph: dict = None) -> list[dict]:
        gaps = []
        concepts = self.db.list_concepts()
        for concept in concepts:
            rels = self.db.get_relationships_for_concept(concept["id"])
            if len(rels) < 2:
                gaps.append({
                    "type": "isolated_concept",
                    "concept": concept["name"],
                    "detail": f"Concept '{concept['name']}' has only {len(rels)} relationships",
                    "suggestion": f"Research more connections for '{concept['name']}'",
                })
            knowledge = self.db.get_knowledge_for_concept(concept["id"])
            if len(knowledge) == 0:
                gaps.append({
                    "type": "no_knowledge_claims",
                    "concept": concept["name"],
                    "detail": f"Concept '{concept['name']}' has no knowledge claims",
                    "suggestion": f"Generate knowledge claims about '{concept['name']}'",
                })
            unverified = [k for k in knowledge if k.get("verification_status") == "unverified"]
            if len(unverified) > len(knowledge) * 0.5 and len(knowledge) > 0:
                gaps.append({
                    "type": "low_verification",
                    "concept": concept["name"],
                    "detail": f"Concept '{concept['name']}' has {len(unverified)}/{len(knowledge)} unverified claims",
                    "suggestion": f"Verify claims about '{concept['name']}'",
                })
        all_rels = {}
        for concept in concepts:
            rels = self.db.get_relationships_for_concept(concept["id"])
            for r in rels:
                rt = r["relation_type"]
                all_rels[rt] = all_rels.get(rt, 0) + 1
        relation_types_expected = {"is_a", "used_for", "has", "supports", "related_to", "requires", "produces", "part_of"}
        for rt in relation_types_expected:
            if all_rels.get(rt, 0) == 0:
                gaps.append({
                    "type": "missing_relation_type",
                    "relation_type": rt,
                    "detail": f"No relationships of type '{rt}' exist in the knowledge graph",
                    "suggestion": f"Discover and add '{rt}' relationships",
                })
        return gaps

    # ── Internal helpers ──

    def _store_reflection_knowledge(
        self, task: str, approach: str, outcome: str, success: bool
    ):
        concept = self.graph.search_concepts(task)
        concept_name = concept[0]["name"] if concept else task[:50]
        if not concept:
            concept_id = self.graph.add_concept(
                concept_name, concept_type="task_domain"
            )
        else:
            concept_id = concept[0]["id"]
        claim = (
            f"Task '{task}' {'succeeded' if success else 'failed'} "
            f"with approach '{approach}'. Outcome: {outcome}"
        )
        self.db.insert_knowledge(
            concept_id=concept_id,
            claim=claim,
            claim_type="reflection",
            confidence=0.7 if success else 0.6,
        )

    def _identify_knowledge_used(self, messages: list[dict]) -> list[dict]:
        knowledge_used = []
        for msg in messages:
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content", "")
            search_terms = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', content)
            for term in search_terms[:3]:
                results = self.db.search_knowledge(term, limit=1)
                for r in results:
                    knowledge_used.append({
                        "claim": r.get("claim", ""),
                        "confidence": r.get("confidence", 0),
                        "source": r.get("source_id", ""),
                    })
        return knowledge_used[:10]

    def _check_conversation_contradictions(self, messages: list[dict]) -> list[dict]:
        contradictions = []
        assistant_messages = [m for m in messages if m.get("role") == "assistant"]
        for i in range(len(assistant_messages)):
            for j in range(i + 1, len(assistant_messages)):
                content_a = assistant_messages[i].get("content", "")
                content_b = assistant_messages[j].get("content", "")
                if self._texts_contradict(content_a, content_b):
                    contradictions.append({
                        "message_a_index": i,
                        "message_b_index": j,
                        "snippet_a": content_a[:100],
                        "snippet_b": content_b[:100],
                    })
        return contradictions

    def _texts_contradict(self, text_a: str, text_b: str) -> bool:
        negation_words = {"not", "never", "no", "neither", "nor", "n't", "isn't", "wasn't", "doesn't", "don't"}
        words_a = set(re.findall(r'\b[a-z]{4,}\b', text_a.lower()))
        words_b = set(re.findall(r'\b[a-z]{4,}\b', text_b.lower()))
        common = words_a & words_b
        if len(common) < 2:
            return False
        neg_a = bool(negation_words & words_a)
        neg_b = bool(negation_words & words_b)
        if neg_a != neg_b:
            return True
        antonym_pairs = [
            ("increase", "decrease"), ("true", "false"), ("possible", "impossible"),
            ("more", "less"), ("better", "worse"), ("safe", "dangerous"),
        ]
        a_lower = text_a.lower()
        b_lower = text_b.lower()
        for pair in antonym_pairs:
            for word in pair:
                opp = [w for w in pair if w != word][0]
                if word in a_lower and opp in b_lower:
                    return True
                if opp in a_lower and word in b_lower:
                    return True
        return False

    def _store_conversation_reflection(self, conversation: dict, result: ReflectionResult):
        conv_id = conversation.get("id")
        summary = {
            "what_learned": result.what_learned,
            "what_failed": result.what_failed,
            "what_worked": result.what_worked,
            "missing_knowledge": result.missing_knowledge,
            "improvements": result.improvements,
        }
        if conv_id:
            self.db.update_conversation(
                conv_id, summary=json.dumps(summary)
            )
