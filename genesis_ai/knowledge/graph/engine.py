"""Knowledge graph engine for storing and querying concept relationships."""

import json
from collections import defaultdict
from typing import Optional

from genesis_ai.database.db import DatabaseManager

VALID_RELATION_TYPES = {
    "is_a", "used_for", "has", "supports", "related_to",
    "requires", "produces", "contradicts", "part_of", "example_of"
}


class KnowledgeGraph:
    """Graph-based knowledge storage using concepts and relationships in SQLite."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def add_concept(self, name: str, concept_type: str = None, properties: dict = None) -> int:
        props = properties or {}
        existing = self.db.get_concept_by_name(name)
        if existing:
            update_fields = {}
            if concept_type and concept_type != existing.get("domain"):
                update_fields["domain"] = concept_type
            if props.get("description") and props["description"] != existing.get("description"):
                update_fields["description"] = props["description"]
            if props.get("definition") and props["definition"] != existing.get("definition"):
                update_fields["definition"] = props["definition"]
            if props.get("confidence") is not None:
                update_fields["confidence"] = props["confidence"]
            if props.get("examples"):
                update_fields["examples"] = props["examples"]
            if update_fields:
                self.db.update_concept(existing["id"], **update_fields)
            return existing["id"]
        return self.db.insert_concept(
            name=name,
            description=props.get("description"),
            domain=concept_type,
            definition=props.get("definition"),
            examples=props.get("examples", []),
            confidence=props.get("confidence", 0.5),
        )

    def add_relation(self, source_concept: str, target_concept: str, relation_type: str, properties: dict = None) -> int:
        if relation_type not in VALID_RELATION_TYPES:
            raise ValueError(f"Invalid relation type: {relation_type}. Must be one of {VALID_RELATION_TYPES}")
        props = properties or {}
        src = self.db.get_concept_by_name(source_concept)
        if not src:
            src_id = self.add_concept(source_concept)
        else:
            src_id = src["id"]
        tgt = self.db.get_concept_by_name(target_concept)
        if not tgt:
            tgt_id = self.add_concept(target_concept)
        else:
            tgt_id = tgt["id"]
        return self.db.insert_relationship(
            source_concept_id=src_id,
            target_concept_id=tgt_id,
            relation_type=relation_type,
            strength=props.get("strength", 0.5),
            metadata=props.get("metadata"),
        )

    def get_concept(self, name: str) -> Optional[dict]:
        concept = self.db.get_concept_by_name(name)
        if not concept:
            return None
        rels = self.db.get_relationships_for_concept(concept["id"])
        enriched_rels = []
        for r in rels:
            other_id = r["target_concept_id"] if r["source_concept_id"] == concept["id"] else r["source_concept_id"]
            other = self.db.get_concept(other_id)
            enriched_rels.append({
                "id": r["id"],
                "relation_type": r["relation_type"],
                "strength": r["strength"],
                "metadata": json.loads(r["metadata"]) if isinstance(r["metadata"], str) else r["metadata"],
                "direction": "outgoing" if r["source_concept_id"] == concept["id"] else "incoming",
                "other_concept": other["name"] if other else None,
            })
        return {
            "id": concept["id"],
            "name": concept["name"],
            "type": concept["domain"],
            "description": concept["description"],
            "definition": concept["definition"],
            "examples": json.loads(concept["examples"]) if isinstance(concept["examples"], str) else concept["examples"],
            "confidence": concept["confidence"],
            "relations": enriched_rels,
        }

    def get_related(self, concept_name: str, relation_type: str = None) -> list[dict]:
        concept = self.db.get_concept_by_name(concept_name)
        if not concept:
            return []
        rels = self.db.get_relationships_for_concept(concept["id"], relation_type=relation_type)
        results = []
        for r in rels:
            other_id = r["target_concept_id"] if r["source_concept_id"] == concept["id"] else r["source_concept_id"]
            other = self.db.get_concept(other_id)
            if other:
                results.append({
                    "concept_name": other["name"],
                    "concept_type": other["domain"],
                    "relation_type": r["relation_type"],
                    "strength": r["strength"],
                    "direction": "outgoing" if r["source_concept_id"] == concept["id"] else "incoming",
                })
        return results

    def find_path(self, source: str, target: str) -> list[dict]:
        src = self.db.get_concept_by_name(source)
        tgt = self.db.get_concept_by_name(target)
        if not src or not tgt:
            return []
        raw_path = self.db.find_path(src["id"], tgt["id"])
        enriched = []
        for step in raw_path:
            from_concept = self.db.get_concept(step["from"])
            to_concept = self.db.get_concept(step["to"])
            enriched.append({
                "from": from_concept["name"] if from_concept else step["from"],
                "to": to_concept["name"] if to_concept else step["to"],
                "relation_type": step["relationship"]["relation_type"],
                "strength": step["relationship"]["strength"],
            })
        return enriched

    def search_concepts(self, query: str) -> list[dict]:
        raw = self.db.search_concepts(query)
        return [
            {
                "id": c["id"],
                "name": c["name"],
                "type": c["domain"],
                "description": c["description"],
                "confidence": c["confidence"],
            }
            for c in raw
        ]

    def get_concept_type(self, name: str) -> Optional[str]:
        concept = self.db.get_concept_by_name(name)
        return concept["domain"] if concept else None

    def update_confidence(self, concept_name: str, new_confidence: float):
        concept = self.db.get_concept_by_name(concept_name)
        if concept:
            self.db.update_concept(concept["id"], confidence=new_confidence)

    def get_subgraph(self, concept_name: str, depth: int = 2) -> dict:
        concept = self.db.get_concept_by_name(concept_name)
        if not concept:
            return {"concepts": [], "relations": []}
        raw = self.db.traverse_knowledge_graph(concept["id"], max_depth=depth)
        concepts = []
        relations = []
        visited_concepts = set()
        visited_relations = set()
        self._flatten_subgraph(raw, concepts, relations, visited_concepts, visited_relations)
        return {"concepts": concepts, "relations": relations}

    def _flatten_subgraph(self, node: dict, concepts: list, relations: list, visited_concepts: set, visited_relations: set):
        if not node or "concept" not in node:
            return
        c = node["concept"]
        if c["id"] not in visited_concepts:
            visited_concepts.add(c["id"])
            concepts.append({
                "id": c["id"],
                "name": c["name"],
                "type": c["domain"],
                "description": c["description"],
                "confidence": c["confidence"],
            })
        for neighbor in node.get("relationships", []):
            rel = neighbor.get("relationship", {})
            rel_id = rel.get("id")
            if rel_id and rel_id not in visited_relations:
                visited_relations.add(rel_id)
                src = self.db.get_concept(rel.get("source_concept_id"))
                tgt = self.db.get_concept(rel.get("target_concept_id"))
                relations.append({
                    "id": rel_id,
                    "source": src["name"] if src else rel.get("source_concept_id"),
                    "target": tgt["name"] if tgt else rel.get("target_concept_id"),
                    "relation_type": rel.get("relation_type"),
                    "strength": rel.get("strength"),
                })
            self._flatten_subgraph(neighbor.get("concept", {}), concepts, relations, visited_concepts, visited_relations)

    def detect_contradictions(self, concept_name: str) -> list[dict]:
        concept = self.db.get_concept_by_name(concept_name)
        if not concept:
            return []
        rels = self.db.get_relationships_for_concept(concept["id"])
        contradictions = []
        relation_map = defaultdict(list)
        for r in rels:
            other_id = r["target_concept_id"] if r["source_concept_id"] == concept["id"] else r["source_concept_id"]
            other = self.db.get_concept(other_id)
            other_name = other["name"] if other else str(other_id)
            relation_map[r["relation_type"]].append({
                "other_concept": other_name,
                "strength": r["strength"],
                "direction": "outgoing" if r["source_concept_id"] == concept["id"] else "incoming",
            })
        has_contradicts = any(
            other["other_concept"] == concept_name
            for r_type in relation_map
            for other in relation_map[r_type]
            if r_type == "contradicts"
        )
        if has_contradicts:
            contradictions.append({
                "type": "explicit_contradiction",
                "concept": concept_name,
                "details": "This concept has explicit 'contradicts' relationships",
            })
        if "supports" in relation_map and "contradicts" in relation_map:
            supports_set = {o["other_concept"] for o in relation_map["supports"]}
            contradicts_set = {o["other_concept"] for o in relation_map["contradicts"]}
            overlap = supports_set & contradicts_set
            if overlap:
                contradictions.append({
                    "type": "mixed_relationships",
                    "concept": concept_name,
                    "conflicting_concepts": list(overlap),
                    "details": f"Concept both supports and contradicts: {overlap}",
                })
        subgraph = self.get_subgraph(concept_name, depth=2)
        for rel in subgraph.get("relations", []):
            if rel.get("relation_type") == "contradicts":
                contradictions.append({
                    "type": "graph_contradiction",
                    "source": rel["source"],
                    "target": rel["target"],
                    "strength": rel["strength"],
                })
        return contradictions

    def list_all_concepts(self) -> list[dict]:
        raw = self.db.list_concepts()
        return [
            {"id": c["id"], "name": c["name"], "type": c["domain"], "confidence": c["confidence"]}
            for c in raw
        ]

    def list_all_relations(self) -> list[dict]:
        with self.db.get_conn() as conn:
            rows = conn.execute(
                """SELECT r.*, s.name as source_name, t.name as target_name
                   FROM relationships r
                   JOIN concepts s ON r.source_concept_id = s.id
                   JOIN concepts t ON r.target_concept_id = t.id"""
            ).fetchall()
        return [dict(r) for r in rows]
