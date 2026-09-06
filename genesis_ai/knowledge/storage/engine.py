"""Knowledge storage engine with TF-IDF-like search scoring."""

import json
import math
import re
from collections import Counter
from typing import Optional

from genesis_ai.database.db import DatabaseManager

VALID_STATUSES = {"VERIFIED", "PROBABLE", "UNCERTAIN", "CONTRADICTED", "OUTDATED"}


class KnowledgeStorage:
    """Stores and retrieves knowledge claims with TF-IDF search scoring."""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._idf_cache = {}
        self._doc_count = 0

    def store_knowledge(self, claim: str, source_id: int = None, confidence: float = 0.5, evidence: str = None, topic: str = None) -> int:
        concept = self.db.get_concept_by_name(topic) if topic else None
        if not concept and topic:
            concept_id = self.db.insert_concept(name=topic, description=topic, confidence=confidence)
        elif concept:
            concept_id = concept["id"]
        else:
            concept_id = self.db.insert_concept(name=claim[:50], description=claim, confidence=confidence)
        knowledge_id = self.db.insert_knowledge(
            concept_id=concept_id,
            claim=claim,
            source_id=source_id,
            claim_type="fact",
            confidence=confidence,
        )
        if evidence:
            claim_row = self.db.get_knowledge(knowledge_id)
            if claim_row:
                claim_id = self.db.insert_claim(
                    knowledge_id=knowledge_id,
                    claim_text=claim,
                    claim_type="fact",
                    confidence=confidence,
                )
                self.db.insert_evidence(
                    claim_id=claim_id,
                    evidence_text=evidence,
                    source_id=source_id,
                    evidence_type="supporting",
                    strength=confidence,
                )
        return knowledge_id

    def get_knowledge(self, topic: str = None, min_confidence: float = 0.5) -> list[dict]:
        if topic:
            concept = self.db.get_concept_by_name(topic)
            if not concept:
                return []
            items = self.db.get_knowledge_for_concept(concept["id"])
        else:
            with self.db.get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM knowledge WHERE confidence >= ? ORDER BY confidence DESC",
                    (min_confidence,),
                ).fetchall()
                items = [dict(r) for r in rows]
        return [self._enrich_knowledge(k) for k in items if k.get("confidence", 0) >= min_confidence]

    def search_knowledge(self, query: str) -> list[dict]:
        self._rebuild_idf()
        query_terms = self._tokenize(query)
        with self.db.get_conn() as conn:
            rows = conn.execute("SELECT * FROM knowledge").fetchall()
            items = [dict(r) for r in rows]
        scored = []
        for item in items:
            text = item.get("claim", "") + " " + (item.get("metadata") or "")
            doc_terms = self._tokenize(text)
            score = self._tfidf_score(query_terms, doc_terms, len(items))
            if score > 0:
                enriched = self._enrich_knowledge(item)
                enriched["relevance_score"] = round(score, 4)
                scored.append(enriched)
        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored

    def update_knowledge(self, knowledge_id: int, new_data: dict):
        allowed = {"claim", "claim_type", "confidence", "verification_status", "source_id", "metadata"}
        fields = {k: v for k, v in new_data.items() if k in allowed}
        if "metadata" in fields and isinstance(fields["metadata"], dict):
            fields["metadata"] = json.dumps(fields["metadata"])
        if fields:
            self.db.update_knowledge(knowledge_id, **fields)

    def mark_knowledge(self, knowledge_id: int, status: str) -> bool:
        status_upper = status.upper()
        if status_upper not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}. Must be one of {VALID_STATUSES}")
        status_map = {
            "VERIFIED": "verified",
            "PROBABLE": "verified",
            "UNCERTAIN": "unverified",
            "CONTRADICTED": "disputed",
            "OUTDATED": "unverified",
        }
        return self.db.update_knowledge(
            knowledge_id,
            verification_status=status_map.get(status_upper, "unverified"),
        )

    def get_by_topic(self, topic: str) -> list[dict]:
        concept = self.db.get_concept_by_name(topic)
        if not concept:
            return []
        items = self.db.get_knowledge_for_concept(concept["id"])
        return [self._enrich_knowledge(k) for k in items]

    def _rebuild_idf(self):
        with self.db.get_conn() as conn:
            rows = conn.execute("SELECT id, claim, metadata FROM knowledge").fetchall()
            items = [dict(r) for r in rows]
        self._doc_count = len(items)
        df = Counter()
        for item in items:
            text = item.get("claim", "") + " " + (item.get("metadata") or "")
            terms = set(self._tokenize(text))
            for t in terms:
                df[t] += 1
        self._idf_cache = {}
        for term, freq in df.items():
            self._idf_cache[term] = math.log((self._doc_count + 1) / (freq + 1)) + 1

    def _tokenize(self, text: str) -> list[str]:
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        tokens = text.split()
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'shall', 'can', 'to', 'of', 'in', 'for',
            'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'out', 'off', 'over',
            'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when',
            'where', 'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
            'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
            'same', 'so', 'than', 'too', 'very', 'just', 'because', 'but', 'and',
            'or', 'if', 'while', 'that', 'this', 'these', 'those', 'it', 'its',
        }
        return [t for t in tokens if t not in stopwords and len(t) > 1]

    def _tfidf_score(self, query_terms: list[str], doc_terms: list[str], total_docs: int) -> float:
        doc_tf = Counter(doc_terms)
        doc_len = len(doc_terms) if doc_terms else 1
        score = 0.0
        for term in query_terms:
            tf = doc_tf.get(term, 0) / doc_len
            idf = self._idf_cache.get(term, math.log((total_docs + 1) / 2) + 1)
            score += tf * idf
        return score

    def _enrich_knowledge(self, item: dict) -> dict:
        concept = self.db.get_concept(item.get("concept_id")) if item.get("concept_id") else None
        source = self.db.get_source(item.get("source_id")) if item.get("source_id") else None
        claims = self.db.get_claims_for_knowledge(item["id"]) if item.get("id") else []
        return {
            "id": item["id"],
            "claim": item.get("claim"),
            "claim_type": item.get("claim_type"),
            "confidence": item.get("confidence"),
            "verification_status": item.get("verification_status"),
            "topic": concept["name"] if concept else None,
            "source": source["name"] if source else None,
            "source_reliability": source["reliability"] if source else None,
            "claims": [
                {"text": c["claim_text"], "confidence": c["confidence"], "status": c["status"]}
                for c in claims
            ],
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        }
