"""Research memory engine that caches web search results with TTL-based expiry."""

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from genesis_ai.database.db import DatabaseManager


@dataclass
class ResearchCache:
    """A cached research query with its results, sources, and expiry metadata."""

    query: str
    results: List = field(default_factory=list)
    sources: List = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    expiry: float = 0.0
    hit_count: int = 0


class ResearchMemory:
    """Caches web search results to avoid redundant requests.

    Features:
        - TTL-based expiry (default 24 h for general, 1 h for news)
        - Partial matching for similar queries via keyword overlap
        - Hit-count tracking for cache efficiency analysis
        - Automatic cleanup of expired entries
    """

    DEFAULT_TTL = 86400       # 24 hours
    NEWS_TTL = 3600           # 1 hour
    STOPWORDS = frozenset({
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "can", "could", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "under", "again",
        "further", "then", "once", "here", "there", "when", "where", "why",
        "how", "all", "each", "every", "both", "few", "more", "most", "other",
        "some", "such", "no", "nor", "not", "only", "own", "same", "so",
        "than", "too", "very", "just", "because", "but", "and", "or", "if",
        "while", "about", "against", "that", "this", "these", "those",
    })

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._ensure_tables()

    def _ensure_tables(self):
        """Create the research_cache table if it does not exist."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS research_cache (
                cache_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                results TEXT DEFAULT '[]',
                sources TEXT DEFAULT '[]',
                timestamp REAL NOT NULL,
                expiry REAL NOT NULL,
                hit_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_research_cache_query ON research_cache(query)
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_research_cache_expiry ON research_cache(expiry)
        """)

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into lowercase words, removing stopwords."""
        text = re.sub(r"[^\w\s]", " ", text.lower())
        return [t for t in text.split() if t not in self.STOPWORDS and len(t) > 1]

    def _similarity(self, tokens_a: List[str], tokens_b: List[str]) -> float:
        """Compute overlap-based similarity between two token lists."""
        if not tokens_a or not tokens_b:
            return 0.0
        set_a, set_b = set(tokens_a), set(tokens_b)
        intersection = set_a & set_b
        if not intersection:
            return 0.0
        union = set_a | set_b
        jaccard = len(intersection) / len(union)
        coverage = len(intersection) / len(set_a)
        return 0.6 * jaccard + 0.4 * coverage

    def _row_to_cache(self, row: tuple) -> ResearchCache:
        """Convert a database row into a ResearchCache dataclass."""
        return ResearchCache(
            query=row[1],
            results=json.loads(row[2]) if row[2] else [],
            sources=json.loads(row[3]) if row[3] else [],
            timestamp=row[4],
            expiry=row[5],
            hit_count=row[6] or 0,
        )

    def store_research(
        self,
        query: str,
        results: list,
        sources: list,
        ttl: float = None,
    ) -> str:
        """Cache a set of research results for a query.

        Args:
            query: The search query string.
            results: List of result dicts (contents, titles, etc.).
            sources: List of source identifiers or URLs.
            ttl: Time-to-live in seconds. Defaults to DEFAULT_TTL (24 h).

        Returns:
            The cache_id of the stored entry.
        """
        if ttl is None:
            ttl = self.DEFAULT_TTL
        # If a cache entry for this exact query exists, update it instead
        existing = self.db.fetch_one(
            "SELECT cache_id FROM research_cache WHERE query = ?", (query,)
        )
        if existing:
            cache_id = existing[0]
            self.db.execute(
                """UPDATE research_cache
                   SET results = ?, sources = ?, expiry = ?, hit_count = hit_count + 1
                   WHERE cache_id = ?""",
                (json.dumps(results), json.dumps(sources), time.time() + ttl, cache_id),
            )
            return cache_id

        cache_id = str(uuid.uuid4())[:12]
        now = time.time()
        self.db.execute(
            """INSERT INTO research_cache (cache_id, query, results, sources, timestamp, expiry, hit_count)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (cache_id, query, json.dumps(results), json.dumps(sources), now, now + ttl),
        )
        return cache_id

    def get_cached_research(self, query: str) -> Optional[ResearchCache]:
        """Retrieve cached research for an exact query match.

        Increments the hit count if found and not expired.

        Args:
            query: The exact query string to look up.

        Returns:
            ResearchCache if a valid (non-expired) entry exists, otherwise None.
        """
        row = self.db.fetch_one(
            "SELECT * FROM research_cache WHERE query = ?", (query,)
        )
        if not row:
            return None
        cache = self._row_to_cache(row)
        if time.time() > cache.expiry:
            return None
        # Increment hit count
        self.db.execute(
            "UPDATE research_cache SET hit_count = hit_count + 1 WHERE cache_id = ?",
            (row[0],),
        )
        cache.hit_count += 1
        return cache

    def is_fresh(self, query: str) -> bool:
        """Check whether a cached entry exists and has not expired.

        Args:
            query: The query string to check.

        Returns:
            True if a fresh cache entry exists.
        """
        row = self.db.fetch_one(
            "SELECT expiry FROM research_cache WHERE query = ?", (query,)
        )
        if not row:
            return False
        return time.time() <= row[0]

    def invalidate(self, query: str):
        """Remove the cache entry for a specific query.

        Args:
            query: The query whose cache entry should be deleted.
        """
        self.db.execute(
            "DELETE FROM research_cache WHERE query = ?", (query,)
        )

    def get_similar_research(self, topic: str, limit: int = 5) -> List[Dict]:
        """Find cached research entries whose queries are similar to the given topic.

        Uses keyword overlap scoring and returns non-expired entries only.

        Args:
            topic: The topic string to match against cached queries.
            limit: Maximum number of results.

        Returns:
            List of dicts with query, results, sources, similarity, and hit_count.
        """
        query_tokens = self._tokenize(topic)
        if not query_tokens:
            return []

        rows = self.db.fetch_all(
            "SELECT * FROM research_cache ORDER BY timestamp DESC"
        )
        if not rows:
            return []

        now = time.time()
        scored = []
        for row in rows:
            cache = self._row_to_cache(row)
            if now > cache.expiry:
                continue
            cached_tokens = self._tokenize(cache.query)
            score = self._similarity(query_tokens, cached_tokens)
            if score > 0.0:
                scored.append({
                    "query": cache.query,
                    "results": cache.results,
                    "sources": cache.sources,
                    "similarity": round(score, 4),
                    "hit_count": cache.hit_count,
                    "timestamp": cache.timestamp,
                })

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:limit]

    def cleanup_expired(self) -> int:
        """Delete all expired cache entries.

        Returns:
            Number of entries removed (always True on completion).
        """
        now = time.time()
        self.db.execute(
            "DELETE FROM research_cache WHERE expiry < ?", (now,)
        )
        return True

    def get_stats(self) -> Dict:
        """Return aggregate statistics about the research cache.

        Includes total entries, expired count, total and average hit counts,
        and cache size estimate.
        """
        total_row = self.db.fetch_one("SELECT COUNT(*) FROM research_cache")
        total = total_row[0] if total_row else 0

        now = time.time()
        expired_row = self.db.fetch_one(
            "SELECT COUNT(*) FROM research_cache WHERE expiry < ?", (now,)
        )
        expired = expired_row[0] if expired_row else 0

        hits_row = self.db.fetch_one(
            "SELECT SUM(hit_count), AVG(hit_count) FROM research_cache"
        )
        total_hits = hits_row[0] if hits_row and hits_row[0] else 0
        avg_hits = round(hits_row[1], 2) if hits_row and hits_row[1] else 0.0

        # Rough size estimate based on stored JSON lengths
        size_row = self.db.fetch_one(
            "SELECT SUM(LENGTH(results) + LENGTH(sources)) FROM research_cache"
        )
        size_bytes = size_row[0] if size_row and size_row[0] else 0

        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
            "total_hits": total_hits,
            "average_hits": avg_hits,
            "estimated_size_bytes": size_bytes,
        }

    def get_all_queries(self, limit: int = 100) -> List[Dict]:
        """Return a list of all cached queries with their metadata.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of dicts with query, hit_count, timestamp, and expiry info.
        """
        rows = self.db.fetch_all(
            "SELECT query, hit_count, timestamp, expiry FROM research_cache ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        now = time.time()
        return [
            {
                "query": r[0],
                "hit_count": r[1],
                "timestamp": r[2],
                "is_expired": now > r[3],
            }
            for r in rows
        ]
