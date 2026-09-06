from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time
import math
import re
import uuid

from genesis_ai.database.db import DatabaseManager


@dataclass
class Memory:
    memory_id: str
    content: str
    memory_type: str
    metadata: Dict = field(default_factory=dict)
    access_count: int = 0
    relevance_score: float = 1.0
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    decay_factor: float = 1.0


class MemoryEngine:
    MEMORY_TYPES = ["SHORT_TERM", "LONG_TERM", "EPISODIC", "SEMANTIC", "PROCEDURAL", "SKILL"]
    SHORT_TERM_LIMIT = 100
    DECAY_RATE = 0.95
    DECAY_INTERVAL = 3600
    PROMOTE_THRESHOLD = 5

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._ensure_tables()
        self._idf_cache: Dict[str, float] = {}
        self._doc_count = 0

    def _ensure_tables(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS memory_entries (
                memory_id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                access_count INTEGER DEFAULT 0,
                relevance_score REAL DEFAULT 1.0,
                created_at REAL NOT NULL,
                last_accessed REAL NOT NULL,
                decay_factor REAL DEFAULT 1.0
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS memory_tags (
                memory_id TEXT,
                tag TEXT,
                FOREIGN KEY (memory_id) REFERENCES memory_entries(memory_id) ON DELETE CASCADE
            )
        """)

    def store_memory(self, content: str, memory_type: str, metadata: Optional[Dict] = None) -> str:
        if memory_type not in self.MEMORY_TYPES:
            raise ValueError(f"Invalid memory type: {memory_type}. Must be one of {self.MEMORY_TYPES}")
        if metadata is None:
            metadata = {}
        memory_id = str(uuid.uuid4())[:12]
        now = time.time()
        if memory_type == "SHORT_TERM":
            count = self.db.fetch_one(
                "SELECT COUNT(*) FROM memory_entries WHERE memory_type = 'SHORT_TERM'"
            )
            if count and count[0] >= self.SHORT_TERM_LIMIT:
                oldest = self.db.fetch_one(
                    "SELECT memory_id FROM memory_entries WHERE memory_type = 'SHORT_TERM' ORDER BY last_accessed ASC LIMIT 1"
                )
                if oldest:
                    self.db.execute("DELETE FROM memory_tags WHERE memory_id = ?", (oldest[0],))
                    self.db.execute("DELETE FROM memory_entries WHERE memory_id = ?", (oldest[0],))
        self.db.execute(
            """INSERT INTO memory_entries (memory_id, content, memory_type, metadata, access_count, relevance_score, created_at, last_accessed, decay_factor)
               VALUES (?, ?, ?, ?, 0, 1.0, ?, ?, 1.0)""",
            (memory_id, content, memory_type, str(metadata), now, now),
        )
        tokens = self._tokenize(content)
        unique_tokens = set(tokens)
        for tag in unique_tokens:
            if len(tag) > 2:
                self.db.execute(
                    "INSERT INTO memory_tags (memory_id, tag) VALUES (?, ?)",
                    (memory_id, tag),
                )
        return memory_id

    def retrieve_memories(
        self, query: str, memory_type: Optional[str] = None, limit: int = 10
    ) -> List[Dict]:
        if memory_type and memory_type not in self.MEMORY_TYPES:
            raise ValueError(f"Invalid memory type: {memory_type}")
        if memory_type:
            rows = self.db.fetch_all(
                "SELECT * FROM memory_entries WHERE memory_type = ? ORDER BY last_accessed DESC",
                (memory_type,),
            )
        else:
            rows = self.db.fetch_all(
                "SELECT * FROM memory_entries ORDER BY last_accessed DESC"
            )
        if not rows:
            return []
        scored = []
        for row in rows:
            score = self._compute_relevance(query, row)
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, row in scored[:limit]:
            memory_dict = self._row_to_dict(row)
            memory_dict["relevance"] = round(score, 4)
            now = time.time()
            self.db.execute(
                "UPDATE memory_entries SET access_count = access_count + 1, last_accessed = ? WHERE memory_id = ?",
                (now, memory_dict["memory_id"]),
            )
            results.append(memory_dict)
        return results

    def search_memories(self, query: str, limit: int = 10) -> List[Dict]:
        return self.retrieve_memories(query, memory_type=None, limit=limit)

    def decay_old_memories(self) -> int:
        now = time.time()
        rows = self.db.fetch_all(
            "SELECT memory_id, last_accessed, memory_type FROM memory_entries"
        )
        if not rows:
            return 0
        decayed = 0
        for row in rows:
            memory_id = row[0]
            last_accessed = row[1]
            memory_type = row[2]
            time_elapsed = now - last_accessed
            intervals = time_elapsed / self.DECAY_INTERVAL
            new_decay = math.pow(self.DECAY_RATE, intervals)
            self.db.execute(
                "UPDATE memory_entries SET decay_factor = ? WHERE memory_id = ?",
                (new_decay, memory_id),
            )
            if memory_type == "SHORT_TERM" and new_decay < 0.1:
                self.db.execute(
                    "DELETE FROM memory_tags WHERE memory_id = ?", (memory_id,)
                )
                self.db.execute(
                    "DELETE FROM memory_entries WHERE memory_id = ?", (memory_id,)
                )
                decayed += 1
        return decayed

    def promote_short_to_long(self) -> int:
        rows = self.db.fetch_all(
            "SELECT memory_id, access_count, content, metadata, created_at FROM memory_entries WHERE memory_type = 'SHORT_TERM' AND access_count >= ?",
            (self.PROMOTE_THRESHOLD,),
        )
        if not rows:
            return 0
        promoted = 0
        now = time.time()
        for row in rows:
            memory_id = row[0]
            self.db.execute(
                "UPDATE memory_entries SET memory_type = 'LONG_TERM', decay_factor = 1.0, last_accessed = ? WHERE memory_id = ?",
                (now, memory_id),
            )
            promoted += 1
        return promoted

    def get_recent_memories(self, limit: int = 10) -> List[Dict]:
        rows = self.db.fetch_all(
            "SELECT * FROM memory_entries ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_dict(row) for row in rows]

    def get_memory(self, memory_id: str) -> Optional[Dict]:
        row = self.db.fetch_one(
            "SELECT * FROM memory_entries WHERE memory_id = ?", (memory_id,)
        )
        if row:
            return self._row_to_dict(row)
        return None

    def delete_memory(self, memory_id: str) -> bool:
        row = self.db.fetch_one(
            "SELECT memory_id FROM memory_entries WHERE memory_id = ?", (memory_id,)
        )
        if not row:
            return False
        self.db.execute("DELETE FROM memory_tags WHERE memory_id = ?", (memory_id,))
        self.db.execute("DELETE FROM memory_entries WHERE memory_id = ?", (memory_id,))
        return True

    def get_memory_stats(self) -> Dict:
        total = self.db.fetch_one("SELECT COUNT(*) FROM memory_entries")
        by_type = self.db.fetch_all(
            "SELECT memory_type, COUNT(*) FROM memory_entries GROUP BY memory_type"
        )
        avg_access = self.db.fetch_one("SELECT AVG(access_count) FROM memory_entries")
        return {
            "total_memories": total[0] if total else 0,
            "by_type": {row[0]: row[1] for row in by_type} if by_type else {},
            "average_access_count": round(avg_access[0], 2) if avg_access and avg_access[0] else 0,
        }

    def _compute_relevance(self, query: str, row: tuple) -> float:
        content = row[1]
        memory_type = row[2]
        access_count = row[4]
        decay_factor = row[8]
        query_tokens = self._tokenize(query)
        content_tokens = self._tokenize(content)
        if not query_tokens or not content_tokens:
            return 0.0
        query_set = set(query_tokens)
        content_set = set(content_tokens)
        intersection = query_set & content_set
        if not intersection:
            return 0.0
        tf_scores = []
        for token in intersection:
            tf = content_tokens.count(token) / len(content_tokens)
            idf = self._get_idf(token)
            tfidf = tf * idf
            tf_scores.append(tfidf)
        if not tf_scores:
            return 0.0
        tfidf_score = sum(tf_scores) / len(tf_scores)
        access_boost = math.log1p(access_count) * 0.1
        type_boost = {
            "LONG_TERM": 0.15,
            "SEMANTIC": 0.12,
            "PROCEDURAL": 0.10,
            "SKILL": 0.10,
            "EPISODIC": 0.08,
            "SHORT_TERM": 0.05,
        }.get(memory_type, 0.0)
        final_score = (tfidf_score + access_boost + type_boost) * decay_factor
        return min(final_score, 1.0)

    def _get_idf(self, token: str) -> float:
        if token in self._idf_cache:
            return self._idf_cache[token]
        count_row = self.db.fetch_one(
            "SELECT COUNT(*) FROM memory_tags WHERE tag = ?", (token,)
        )
        doc_freq = count_row[0] if count_row else 0
        total_row = self.db.fetch_one("SELECT COUNT(DISTINCT memory_id) FROM memory_tags")
        total_docs = total_row[0] if total_row else 1
        if doc_freq == 0:
            idf = math.log(total_docs + 1)
        else:
            idf = math.log(total_docs / doc_freq)
        self._idf_cache[token] = idf
        return idf

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        tokens = text.split()
        stopwords = {
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
            "me", "my", "we", "our", "you", "your", "he", "him", "his", "she",
            "her", "it", "its", "they", "them", "their", "what", "which", "who",
            "whom", "hain", "hai", "ka", "ki", "ke", "ko", "se", "me", "par",
            "ye", "woh", "yeh", "kya", "kaise", "kyu", "aur", "bhi", "to",
        }
        return [t for t in tokens if t not in stopwords and len(t) > 1]

    def _row_to_dict(self, row: tuple) -> Dict:
        metadata_str = row[3] if row[3] else "{}"
        try:
            metadata = eval(metadata_str) if metadata_str.startswith("{") else {}
        except (SyntaxError, NameError):
            metadata = {}
        return {
            "memory_id": row[0],
            "content": row[1],
            "memory_type": row[2],
            "metadata": metadata,
            "access_count": row[4],
            "relevance_score": row[5],
            "created_at": row[6],
            "last_accessed": row[7],
            "decay_factor": row[8],
        }
