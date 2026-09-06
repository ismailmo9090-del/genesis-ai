"""Source management and reliability tracking."""

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from genesis_ai.database.db import DatabaseManager


DEFAULT_RELIABILITY: dict[str, float] = {
    "stackoverflow": 0.9,
    "github": 0.85,
    "wikipedia": 0.8,
    "official_docs": 0.95,
    "medium": 0.6,
    "random_blog": 0.4,
}

DOMAIN_SOURCE_MAP: dict[str, str] = {
    "stackoverflow.com": "stackoverflow",
    "github.com": "github",
    "wikipedia.org": "wikipedia",
    "medium.com": "medium",
    "docs.python.org": "official_docs",
    "developer.mozilla.org": "official_docs",
    "docs.microsoft.com": "official_docs",
    "cloud.google.com": "official_docs",
    "docs.aws.amazon.com": "official_docs",
}


@dataclass
class SourceComparison:
    claim: str
    supporting_sources: list[dict] = field(default_factory=list)
    contradicting_sources: list[dict] = field(default_factory=list)
    avg_reliability: float = 0.0
    agreement_ratio: float = 0.0
    verdict: str = "uncertain"


class SourceManager:
    """Track source reliability and compare information across sources."""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._reliability_cache: dict[str, float] = dict(DEFAULT_RELIABILITY)
        self._load_existing_sources()

    def _load_existing_sources(self):
        try:
            sources = self.db.list_sources(limit=500)
            for src in sources:
                name = src.get("name", "")
                reliability = src.get("reliability", 0.5)
                if name:
                    self._reliability_cache[name.lower()] = reliability
        except Exception:
            pass

    def register_source(self, name: str, url: str = "", reliability_score: float = 0.5) -> int:
        source_id = self.db.insert_source(
            name=name,
            url=url,
            reliability=reliability_score,
        )
        self._reliability_cache[name.lower()] = reliability_score
        return source_id

    def get_source_reliability(self, source_name: str) -> float:
        key = source_name.lower().strip()
        if key in self._reliability_cache:
            return self._reliability_cache[key]
        db_source = self._find_source_in_db(key)
        if db_source:
            reliability = db_source.get("reliability", 0.5)
            self._reliability_cache[key] = reliability
            return reliability
        domain_score = self._estimate_from_domain(key)
        self._reliability_cache[key] = domain_score
        return domain_score

    def compare_sources(self, claim: str, sources: list[dict]) -> SourceComparison:
        result = SourceComparison(claim=claim)
        supporting = []
        contradicting = []
        for source in sources:
            source_name = source.get("source_name", source.get("name", "unknown"))
            reliability = self.get_source_reliability(source_name)
            entry = {
                "source_name": source_name,
                "url": source.get("url", ""),
                "reliability": reliability,
                "snippet": source.get("snippet", source.get("text", "")),
            }
            source_type = self._classify_evidence(claim, entry.get("snippet", ""))
            if source_type == "supporting":
                supporting.append(entry)
            elif source_type == "contradicting":
                contradicting.append(entry)
            else:
                supporting.append(entry)
        result.supporting_sources = supporting
        result.contradicting_sources = contradicting
        all_sources = supporting + contradicting
        if all_sources:
            result.avg_reliability = sum(s["reliability"] for s in all_sources) / len(all_sources)
        total = len(supporting) + len(contradicting)
        result.agreement_ratio = len(supporting) / total if total > 0 else 0.0
        result.verdict = self._determine_verdict(result)
        return result

    def track_source(self, url: str, title: str = "") -> int:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        source_name = self._resolve_source_name(domain)
        existing = self._find_source_in_db(source_name)
        if existing:
            return existing["id"]
        reliability = self._estimate_from_domain(domain)
        source_type = self._classify_source_type(domain)
        return self.db.insert_source(
            name=source_name,
            source_type=source_type,
            url=url,
            reliability=reliability,
        )

    def _find_source_in_db(self, name: str) -> Optional[dict]:
        try:
            sources = self.db.list_sources(limit=500)
            for src in sources:
                if src.get("name", "").lower() == name.lower():
                    return src
        except Exception:
            pass
        return None

    def _resolve_source_name(self, domain: str) -> str:
        for known_domain, source_name in DOMAIN_SOURCE_MAP.items():
            if known_domain in domain:
                return source_name
        return domain.split(".")[0] if domain else "unknown"

    def _estimate_from_domain(self, domain: str) -> float:
        for known_domain, score in DEFAULT_RELIABILITY.items():
            if known_domain in domain:
                return score
        tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
        if tld in ("edu", "gov"):
            return 0.85
        if tld == "org":
            return 0.7
        if domain.endswith(".com") or domain.endswith(".io"):
            return 0.5
        return 0.4

    def _classify_source_type(self, domain: str) -> str:
        for known_domain, source_name in DOMAIN_SOURCE_MAP.items():
            if known_domain in domain:
                return source_name
        if "blog" in domain:
            return "blog"
        if "news" in domain:
            return "news"
        if "forum" in domain or "discussion" in domain:
            return "forum"
        return "web"

    def _classify_evidence(self, claim: str, snippet: str) -> str:
        if not snippet:
            return "neutral"
        claim_lower = claim.lower()
        snippet_lower = snippet.lower()
        claim_words = set(re.findall(r'\b[a-z]{4,}\b', claim_lower))
        snippet_words = set(re.findall(r'\b[a-z]{4,}\b', snippet_lower))
        if not claim_words:
            return "neutral"
        overlap = claim_words & snippet_words
        overlap_ratio = len(overlap) / len(claim_words) if claim_words else 0.0
        negation_patterns = [
            r'\bnot\b', r'\bnever\b', r'\bno\b', r'\bneither\b',
            r'\bdoes not\b', r'\bis not\b', r'\bwas not\b',
            r'\bcontrary\b', r'\bdispute\b', r'\brefute\b',
        ]
        has_negation = any(re.search(p, snippet_lower) for p in negation_patterns)
        claim_has_negation = any(re.search(p, claim_lower) for p in negation_patterns)
        if overlap_ratio >= 0.3:
            if has_negation and not claim_has_negation:
                return "contradicting"
            if not has_negation and claim_has_negation:
                return "contradicting"
            return "supporting"
        if overlap_ratio < 0.15:
            return "neutral"
        return "supporting"

    def _determine_verdict(self, comparison: SourceComparison) -> str:
        if not comparison.supporting_sources and not comparison.contradicting_sources:
            return "uncertain"
        if comparison.agreement_ratio >= 0.8:
            if comparison.avg_reliability >= 0.7:
                return "well_supported"
            return "supported"
        if comparison.agreement_ratio <= 0.3:
            if len(comparison.contradicting_sources) > len(comparison.supporting_sources):
                return "disputed"
            return "uncertain"
        return "mixed"
