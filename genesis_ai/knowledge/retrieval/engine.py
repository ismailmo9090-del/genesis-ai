"""Knowledge retrieval engine combining graph traversal and text search."""

import json
import math
import re
from collections import Counter
from typing import Optional

from genesis_ai.database.db import DatabaseManager
from genesis_ai.knowledge.graph.engine import KnowledgeGraph
from genesis_ai.knowledge.storage.engine import KnowledgeStorage


class KnowledgeRetrieval:
    """Retrieves and ranks knowledge by combining graph traversal with text search."""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.graph = KnowledgeGraph(db)
        self.storage = KnowledgeStorage(db)

    def retrieve(self, query: str, context: dict = None, confidence_threshold: float = 0.3) -> list[dict]:
        context = context or {}
        text_results = self._text_search(query)
        graph_results = self._graph_search(query, context)
        merged = self._merge_results(text_results, graph_results)
        filtered = [r for r in merged if r.get("confidence", 0) >= confidence_threshold]
        filtered.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return filtered

    def _text_search(self, query: str) -> list[dict]:
        results = self.storage.search_knowledge(query)
        for r in results:
            r["source_method"] = "text_search"
        return results

    def _graph_search(self, query: str, context: dict) -> list[dict]:
        query_concepts = self._extract_concepts(query)
        context_topic = context.get("topic")
        if context_topic:
            query_concepts.append(context_topic)
        results = []
        seen_knowledge_ids = set()
        for concept_name in query_concepts:
            concept = self.db.get_concept_by_name(concept_name)
            if not concept:
                continue
            knowledge_items = self.db.get_knowledge_for_concept(concept["id"])
            for ki in knowledge_items:
                if ki["id"] not in seen_knowledge_ids:
                    seen_knowledge_ids.add(ki["id"])
                    enriched = self.storage._enrich_knowledge(ki)
                    enriched["source_method"] = "graph_traversal"
                    enriched["graph_concept"] = concept_name
                    enriched["relevance_score"] = self._graph_relevance_score(ki, concept_name, query)
                    results.append(enriched)
            related = self.graph.get_related(concept_name)
            for rel in related[:5]:
                rel_concept = self.db.get_concept_by_name(rel["concept_name"])
                if rel_concept:
                    rel_knowledge = self.db.get_knowledge_for_concept(rel_concept["id"])
                    for ki in rel_knowledge:
                        if ki["id"] not in seen_knowledge_ids:
                            seen_knowledge_ids.add(ki["id"])
                            enriched = self.storage._enrich_knowledge(ki)
                            enriched["source_method"] = "graph_related"
                            enriched["graph_concept"] = rel["concept_name"]
                            enriched["relation_type"] = rel["relation_type"]
                            enriched["relevance_score"] = self._graph_relevance_score(ki, rel["concept_name"], query) * 0.7
                            results.append(enriched)
        return results

    def _merge_results(self, text_results: list[dict], graph_results: list[dict]) -> list[dict]:
        merged = {}
        for item in text_results:
            kid = item["id"]
            merged[kid] = item
        for item in graph_results:
            kid = item["id"]
            if kid in merged:
                existing = merged[kid]
                existing["relevance_score"] = max(
                    existing.get("relevance_score", 0),
                    item.get("relevance_score", 0),
                )
                existing["source_method"] = "combined"
                if "graph_concept" in item:
                    existing["graph_concept"] = item["graph_concept"]
                if "relation_type" in item:
                    existing["relation_type"] = item["relation_type"]
            else:
                merged[kid] = item
        results = list(merged.values())
        for r in results:
            conf = r.get("confidence", 0.5)
            rel = r.get("relevance_score", 0)
            r["relevance_score"] = round(rel * (0.5 + conf * 0.5), 4)
        return results

    def _extract_concepts(self, query: str) -> list[str]:
        query_lower = query.lower()
        all_concepts = self.graph.list_all_concepts()
        matched = []
        for c in all_concepts:
            name = c["name"].lower()
            if name in query_lower or query_lower in name:
                matched.append(c["name"])
            elif any(word in name for word in query_lower.split() if len(word) > 3):
                matched.append(c["name"])
        if not matched:
            words = re.findall(r'[a-zA-Z]{4,}', query_lower)
            matched = [w.capitalize() for w in words[:5]]
        return matched

    def _graph_relevance_score(self, knowledge_item: dict, concept_name: str, query: str) -> float:
        score = 0.0
        conf = knowledge_item.get("confidence", 0.5)
        score += conf * 0.3
        claim = (knowledge_item.get("claim") or "").lower()
        query_lower = query.lower()
        claim_words = set(claim.split())
        query_words = set(query_lower.split())
        overlap = claim_words & query_words
        if query_words:
            score += (len(overlap) / len(query_words)) * 0.4
        if knowledge_item.get("verification_status") == "verified":
            score += 0.2
        elif knowledge_item.get("verification_status") == "disputed":
            score -= 0.1
        concept_lower = concept_name.lower()
        if concept_lower in claim:
            score += 0.1
        return min(score, 1.0)

    def get_related_knowledge(self, knowledge_id: int, max_depth: int = 2) -> list[dict]:
        item = self.db.get_knowledge(knowledge_id)
        if not item:
            return []
        concept = self.db.get_concept(item.get("concept_id")) if item.get("concept_id") else None
        if not concept:
            return []
        subgraph = self.graph.get_subgraph(concept["name"], depth=max_depth)
        related = []
        seen = {knowledge_id}
        for c in subgraph.get("concepts", []):
            concept_items = self.db.get_knowledge_for_concept(c["id"])
            for ki in concept_items:
                if ki["id"] not in seen:
                    seen.add(ki["id"])
                    enriched = self.storage._enrich_knowledge(ki)
                    enriched["graph_distance"] = self._calculate_distance(concept["name"], c["name"])
                    related.append(enriched)
        related.sort(key=lambda x: x.get("graph_distance", 999))
        return related

    def _calculate_distance(self, source: str, target: str) -> int:
        path = self.graph.find_path(source, target)
        return len(path) if path else 999

    def summarize_topic(self, topic: str) -> dict:
        knowledge = self.storage.get_by_topic(topic)
        if not knowledge:
            return {"topic": topic, "items": 0, "avg_confidence": 0, "summary": "No knowledge found"}
        avg_conf = sum(k.get("confidence", 0) for k in knowledge) / len(knowledge)
        statuses = {}
        for k in knowledge:
            s = k.get("verification_status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1
        subgraph = self.graph.get_subgraph(topic, depth=1)
        return {
            "topic": topic,
            "items": len(knowledge),
            "avg_confidence": round(avg_conf, 3),
            "verification_distribution": statuses,
            "related_concepts": len(subgraph.get("concepts", [])),
            "related_relations": len(subgraph.get("relations", [])),
            "top_claims": [
                {"claim": k["claim"], "confidence": k["confidence"]}
                for k in sorted(knowledge, key=lambda x: x.get("confidence", 0), reverse=True)[:5]
            ],
        }
