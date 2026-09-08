"""Genesis Knowledge Provider — connects to external AI Knowledge Network."""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from genesis_ai.core.code.knowledge_provider import (
    CodingKnowledge,
    InternalKnowledgeProvider,
    KnowledgeProvider,
)

logger = logging.getLogger(__name__)

DEFAULT_NETWORK_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 5
DEFAULT_MAX_RETRIES = 2
RETRY_BACKOFF = 0.5


@dataclass
class NetworkKnowledgeItem:
    """Raw knowledge item from the Knowledge Network."""
    object_type: str
    data: dict
    relevance_score: float = 0.0
    confidence: float = 0.0
    freshness: float = 0.0


class GenesisKnowledgeProvider(KnowledgeProvider):
    """Knowledge provider that queries the external AI Knowledge Network.

    Architecture:
        GenesisKnowledgeProvider
            ├── available → external Knowledge Network (http://127.0.0.1:8000)
            └── unavailable → InternalKnowledgeProvider (fallback)
    """

    def __init__(
        self,
        network_url: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        fallback: Optional[KnowledgeProvider] = None,
    ):
        self._network_url = (
            network_url
            or os.environ.get("GENESIS_KNOWLEDGE_URL", DEFAULT_NETWORK_URL)
        ).rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._fallback = fallback or InternalKnowledgeProvider()
        self._available: Optional[bool] = None
        self._last_check: float = 0
        self._check_interval = 30.0

    def _is_available(self) -> bool:
        now = time.time()
        if self._available is not None and (now - self._last_check) < self._check_interval:
            return self._available
        self._last_check = now
        try:
            url = f"{self._network_url}/v1/knowledge/status"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                self._available = resp.status == 200
        except Exception:
            self._available = False
        return self._available

    def _post(self, endpoint: str, payload: dict) -> Optional[dict]:
        url = f"{self._network_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        last_error = None

        for attempt in range(self._max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.reason}"
                if e.code in (400, 404, 422):
                    return None
            except urllib.error.URLError as e:
                last_error = f"Connection error: {e.reason}"
            except Exception as e:
                last_error = str(e)

            if attempt < self._max_retries:
                time.sleep(RETRY_BACKOFF * (attempt + 1))

        logger.warning("Knowledge Network request failed after %d attempts: %s",
                       self._max_retries + 1, last_error)
        return None

    def _normalize_item(self, item: NetworkKnowledgeItem) -> CodingKnowledge:
        obj_type = item.object_type
        data = item.data

        if obj_type == "fact":
            return self._normalize_fact(data, item)
        elif obj_type == "entity":
            return self._normalize_entity(data, item)
        elif obj_type == "skill":
            return self._normalize_skill(data, item)
        elif obj_type == "pattern":
            return self._normalize_pattern(data, item)
        else:
            return self._normalize_generic(data, item)

    def _normalize_fact(self, data: dict, item: NetworkKnowledgeItem) -> CodingKnowledge:
        subject = data.get("subject", "")
        predicate = data.get("predicate", "")
        object_value = data.get("object_value", "")
        description = f"{subject} {predicate} {object_value}".strip()
        return CodingKnowledge(
            concept=subject,
            description=description,
            category="fact",
            confidence=item.confidence,
            source="ai_knowledge_network",
            examples=[f"{subject} {predicate} {object_value}"] if object_value else [],
            best_practices=[],
            constraints=[],
            patterns=[],
        )

    def _normalize_entity(self, data: dict, item: NetworkKnowledgeItem) -> CodingKnowledge:
        name = data.get("canonical_name", "")
        description = data.get("description", "")
        entity_type = data.get("type", "")
        domain = data.get("domain", "")
        return CodingKnowledge(
            concept=name,
            description=description,
            category=entity_type or domain or "entity",
            confidence=item.confidence,
            source="ai_knowledge_network",
            examples=[],
            best_practices=[],
            constraints=[],
            patterns=[],
        )

    def _normalize_skill(self, data: dict, item: NetworkKnowledgeItem) -> CodingKnowledge:
        name = data.get("name", "")
        purpose = data.get("purpose", "")
        procedure = data.get("procedure", [])
        best_practices = data.get("best_practices", [])
        constraints = data.get("constraints", [])
        examples = [step.get("description", "") for step in procedure if isinstance(step, dict)]
        return CodingKnowledge(
            concept=name,
            description=purpose,
            category="skill",
            confidence=item.confidence,
            source="ai_knowledge_network",
            examples=examples,
            best_practices=best_practices,
            constraints=constraints,
            patterns=[],
        )

    def _normalize_pattern(self, data: dict, item: NetworkKnowledgeItem) -> CodingKnowledge:
        name = data.get("name", data.get("pattern_name", ""))
        description = data.get("description", "")
        return CodingKnowledge(
            concept=name,
            description=description,
            category="pattern",
            confidence=item.confidence,
            source="ai_knowledge_network",
            examples=data.get("examples", []),
            best_practices=data.get("best_practices", []),
            constraints=data.get("constraints", []),
            patterns=[name],
        )

    def _normalize_generic(self, data: dict, item: NetworkKnowledgeItem) -> CodingKnowledge:
        name = data.get("name", data.get("id", "unknown"))
        description = data.get("description", "")
        return CodingKnowledge(
            concept=name,
            description=description,
            category=item.object_type,
            confidence=item.confidence,
            source="ai_knowledge_network",
        )

    def _search_network(self, query: str, knowledge_type: Optional[str] = None,
                        limit: int = 10) -> list[NetworkKnowledgeItem]:
        payload: dict = {"query": query}
        if knowledge_type:
            payload["knowledge_type"] = knowledge_type

        result = self._post("/v1/knowledge/search", payload)
        if not result:
            return []

        items = []
        for r in result.get("results", []):
            items.append(NetworkKnowledgeItem(
                object_type=r.get("object_type", "unknown"),
                data=r.get("data", {}),
                relevance_score=r.get("relevance_score", 0.0),
                confidence=r.get("confidence", 0.0),
                freshness=r.get("freshness", 0.0),
            ))
        return items

    def _filter_relevant(self, items: list[CodingKnowledge], query: str,
                         language: Optional[str] = None) -> list[CodingKnowledge]:
        query_lower = query.lower()
        query_words = set(query_lower.split())
        relevant = []

        for item in items:
            score = 0.0
            concept_lower = item.concept.lower()
            desc_lower = item.description.lower()

            if query_lower in concept_lower or concept_lower in query_lower:
                score += 1.0

            for word in query_words:
                if word in concept_lower:
                    score += 0.3
                if word in desc_lower:
                    score += 0.2

            if language:
                if item.language == language:
                    score += 0.2
                elif item.framework and language in ("python", "javascript"):
                    score += 0.1

            if score > 0.1:
                item.confidence = min(item.confidence * score, 1.0)
                relevant.append(item)

        relevant.sort(key=lambda x: x.confidence, reverse=True)
        return relevant

    def search_knowledge(self, query: str, language: Optional[str] = None,
                         category: Optional[str] = None, limit: int = 5) -> list[CodingKnowledge]:
        if not self._is_available():
            return self._fallback.search_knowledge(query, language, category, limit)

        raw_items = self._search_network(query, knowledge_type=category, limit=limit * 2)
        normalized = [self._normalize_item(item) for item in raw_items]
        relevant = self._filter_relevant(normalized, query, language)
        return relevant[:limit]

    def get_concept(self, concept: str, language: Optional[str] = None) -> Optional[CodingKnowledge]:
        if not self._is_available():
            return self._fallback.get_concept(concept, language)

        items = self._search_network(concept, limit=5)
        normalized = [self._normalize_item(item) for item in items]
        relevant = self._filter_relevant(normalized, concept, language)
        return relevant[0] if relevant else None

    def get_pattern(self, pattern_name: str, language: Optional[str] = None) -> Optional[CodingKnowledge]:
        if not self._is_available():
            return self._fallback.get_pattern(pattern_name, language)

        items = self._search_network(pattern_name, knowledge_type="pattern", limit=5)
        normalized = [self._normalize_item(item) for item in items]
        relevant = self._filter_relevant(normalized, pattern_name, language)
        return relevant[0] if relevant else None

    def get_skill(self, skill_name: str, language: Optional[str] = None) -> Optional[CodingKnowledge]:
        if not self._is_available():
            return self._fallback.get_skill(skill_name, language)

        items = self._search_network(skill_name, knowledge_type="skill", limit=5)
        normalized = [self._normalize_item(item) for item in items]
        relevant = self._filter_relevant(normalized, skill_name, language)
        return relevant[0] if relevant else None

    def get_examples(self, concept: str, language: Optional[str] = None, limit: int = 3) -> list[str]:
        if not self._is_available():
            return self._fallback.get_examples(concept, language, limit)

        kb = self.get_concept(concept, language)
        if kb and kb.examples:
            return kb.examples[:limit]
        return self._fallback.get_examples(concept, language, limit)

    def get_best_practices(self, concept: str, language: Optional[str] = None) -> list[str]:
        if not self._is_available():
            return self._fallback.get_best_practices(concept, language)

        kb = self.get_concept(concept, language)
        if kb and kb.best_practices:
            return kb.best_practices
        return self._fallback.get_best_practices(concept, language)

    def get_constraints(self, concept: str, language: Optional[str] = None) -> list[str]:
        if not self._is_available():
            return self._fallback.get_constraints(concept, language)

        kb = self.get_concept(concept, language)
        if kb and kb.constraints:
            return kb.constraints
        return self._fallback.get_constraints(concept, language)

    @property
    def is_network_available(self) -> bool:
        return self._is_available()
