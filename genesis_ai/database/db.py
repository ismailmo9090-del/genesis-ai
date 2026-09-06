"""Database manager for Genesis AI with connection pooling and CRUD operations."""

import sqlite3
import json
import threading
from contextlib import contextmanager
from typing import Any, Optional

from genesis_ai.config.settings import DATABASE_PATH
from genesis_ai.database.schema import run_migrations


class DatabaseManager:
    """Thread-safe SQLite database manager with connection pooling."""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path)
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA foreign_keys=ON")
            self._local.connection.execute("PRAGMA busy_timeout=5000")
        return self._local.connection

    @contextmanager
    def get_conn(self):
        conn = self._get_connection()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise

    def execute(self, query: str, params: tuple = ()):
        with self.get_conn() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[tuple]:
        with self.get_conn() as conn:
            row = conn.execute(query, params).fetchone()
            return tuple(row) if row else None

    def fetch_all(self, query: str, params: tuple = ()) -> list[tuple]:
        with self.get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [tuple(r) for r in rows]

    def init_db(self):
        with self.get_conn() as conn:
            run_migrations(conn)

    # ── Users ──────────────────────────────────────────────

    def insert_user(self, username: str, display_name: str = None, email: str = None, preferences: dict = None) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, display_name, email, preferences) VALUES (?, ?, ?, ?)",
                (username, display_name, email, json.dumps(preferences or {})),
            )
            conn.commit()
            return cursor.lastrowid

    def get_user(self, user_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return dict(row) if row else None

    def update_user(self, user_id: int, **kwargs) -> bool:
        allowed = {"display_name", "email", "preferences"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        if "preferences" in fields:
            fields["preferences"] = json.dumps(fields["preferences"])
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [user_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE users SET {set_clause}, updated_at = datetime('now') WHERE id = ?", values)
            conn.commit()
            return conn.total_changes > 0

    def delete_user(self, user_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return conn.total_changes > 0

    def list_users(self, limit: int = 100) -> list[dict]:
        with self.get_conn() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ── Conversations ──────────────────────────────────────

    def insert_conversation(self, user_id: int, title: str = None, summary: str = None) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO conversations (user_id, title, summary) VALUES (?, ?, ?)",
                (user_id, title, summary),
            )
            conn.commit()
            return cursor.lastrowid

    def get_conversation(self, conv_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
            return dict(row) if row else None

    def update_conversation(self, conv_id: int, **kwargs) -> bool:
        allowed = {"title", "summary", "status"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [conv_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE conversations SET {set_clause}, updated_at = datetime('now') WHERE id = ?", values)
            conn.commit()
            return conn.total_changes > 0

    def delete_conversation(self, conv_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            conn.commit()
            return conn.total_changes > 0

    def list_conversations(self, user_id: int, status: str = None, limit: int = 50) -> list[dict]:
        with self.get_conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM conversations WHERE user_id = ? AND status = ? ORDER BY updated_at DESC LIMIT ?",
                    (user_id, status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Messages ───────────────────────────────────────────

    def insert_message(self, conversation_id: int, role: str, content: str, token_count: int = 0, metadata: dict = None) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO messages (conversation_id, role, content, token_count, metadata) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, role, content, token_count, json.dumps(metadata or {})),
            )
            conn.execute("UPDATE conversations SET updated_at = datetime('now') WHERE id = ?", (conversation_id,))
            conn.commit()
            return cursor.lastrowid

    def get_message(self, msg_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)).fetchone()
            return dict(row) if row else None

    def get_conversation_messages(self, conversation_id: int, limit: int = 100) -> list[dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_message(self, msg_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
            conn.commit()
            return conn.total_changes > 0

    def search_messages(self, query: str, user_id: int = None, limit: int = 20) -> list[dict]:
        with self.get_conn() as conn:
            if user_id:
                rows = conn.execute(
                    """SELECT m.* FROM messages m
                       JOIN conversations c ON m.conversation_id = c.id
                       WHERE m.content LIKE ? AND c.user_id = ?
                       ORDER BY m.created_at DESC LIMIT ?""",
                    (f"%{query}%", user_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM messages WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
                    (f"%{query}%", limit),
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Memories ───────────────────────────────────────────

    def insert_memory(self, user_id: int, key: str, value: str, memory_type: str = "episodic", importance: float = 0.5) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO memories (user_id, key, value, memory_type, importance) VALUES (?, ?, ?, ?, ?)",
                (user_id, key, value, memory_type, importance),
            )
            conn.commit()
            return cursor.lastrowid

    def get_memory(self, memory_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            return dict(row) if row else None

    def get_memories_by_key(self, user_id: int, key: str) -> list[dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE user_id = ? AND key = ? ORDER BY importance DESC",
                (user_id, key),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_memory(self, memory_id: int, **kwargs) -> bool:
        allowed = {"value", "memory_type", "importance", "decay_rate"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [memory_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE memories SET {set_clause}, updated_at = datetime('now') WHERE id = ?", values)
            conn.commit()
            return conn.total_changes > 0

    def touch_memory(self, memory_id: int):
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id = ?",
                (memory_id,),
            )
            conn.commit()

    def delete_memory(self, memory_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            return conn.total_changes > 0

    def search_memories(self, user_id: int, query: str, memory_type: str = None, limit: int = 20) -> list[dict]:
        with self.get_conn() as conn:
            if memory_type:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE user_id = ? AND key LIKE ? AND memory_type = ? ORDER BY importance DESC LIMIT ?",
                    (user_id, f"%{query}%", memory_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE user_id = ? AND (key LIKE ? OR value LIKE ?) ORDER BY importance DESC LIMIT ?",
                    (user_id, f"%{query}%", f"%{query}%", limit),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_top_memories(self, user_id: int, limit: int = 10) -> list[dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE user_id = ? ORDER BY importance DESC, access_count DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def decay_memories(self, user_id: int):
        with self.get_conn() as conn:
            conn.execute(
                """UPDATE memories SET importance = MAX(0.01, importance - decay_rate)
                   WHERE user_id = ? AND importance > 0""",
                (user_id,),
            )
            conn.commit()

    # ── Concepts ───────────────────────────────────────────

    def insert_concept(self, name: str, description: str = None, domain: str = None, definition: str = None, examples: list = None, confidence: float = 0.5) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO concepts (name, description, domain, definition, examples, confidence) VALUES (?, ?, ?, ?, ?, ?)",
                (name, description, domain, definition, json.dumps(examples or []), confidence),
            )
            conn.commit()
            return cursor.lastrowid

    def get_concept(self, concept_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM concepts WHERE id = ?", (concept_id,)).fetchone()
            return dict(row) if row else None

    def get_concept_by_name(self, name: str) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM concepts WHERE name = ?", (name,)).fetchone()
            return dict(row) if row else None

    def update_concept(self, concept_id: int, **kwargs) -> bool:
        allowed = {"description", "domain", "definition", "examples", "confidence"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        if "examples" in fields:
            fields["examples"] = json.dumps(fields["examples"])
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [concept_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE concepts SET {set_clause}, updated_at = datetime('now') WHERE id = ?", values)
            conn.commit()
            return conn.total_changes > 0

    def delete_concept(self, concept_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM concepts WHERE id = ?", (concept_id,))
            conn.commit()
            return conn.total_changes > 0

    def search_concepts(self, query: str, domain: str = None, limit: int = 20) -> list[dict]:
        with self.get_conn() as conn:
            if domain:
                rows = conn.execute(
                    "SELECT * FROM concepts WHERE (name LIKE ? OR description LIKE ?) AND domain = ? ORDER BY confidence DESC LIMIT ?",
                    (f"%{query}%", f"%{query}%", domain, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM concepts WHERE name LIKE ? OR description LIKE ? ORDER BY confidence DESC LIMIT ?",
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()
            return [dict(r) for r in rows]

    def list_concepts(self, domain: str = None, limit: int = 100) -> list[dict]:
        with self.get_conn() as conn:
            if domain:
                rows = conn.execute(
                    "SELECT * FROM concepts WHERE domain = ? ORDER BY name LIMIT ?",
                    (domain, limit),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM concepts ORDER BY name LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ── Relationships ──────────────────────────────────────

    def insert_relationship(self, source_concept_id: int, target_concept_id: int, relation_type: str, strength: float = 0.5, metadata: dict = None) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO relationships (source_concept_id, target_concept_id, relation_type, strength, metadata) VALUES (?, ?, ?, ?, ?)",
                (source_concept_id, target_concept_id, relation_type, strength, json.dumps(metadata or {})),
            )
            conn.commit()
            return cursor.lastrowid

    def get_relationship(self, rel_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM relationships WHERE id = ?", (rel_id,)).fetchone()
            return dict(row) if row else None

    def update_relationship(self, rel_id: int, **kwargs) -> bool:
        allowed = {"strength", "metadata", "evidence_count"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        if "metadata" in fields:
            fields["metadata"] = json.dumps(fields["metadata"])
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [rel_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE relationships SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return conn.total_changes > 0

    def delete_relationship(self, rel_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM relationships WHERE id = ?", (rel_id,))
            conn.commit()
            return conn.total_changes > 0

    def get_relationships_for_concept(self, concept_id: int, relation_type: str = None) -> list[dict]:
        with self.get_conn() as conn:
            if relation_type:
                rows = conn.execute(
                    """SELECT * FROM relationships
                       WHERE (source_concept_id = ? OR target_concept_id = ?) AND relation_type = ?
                       ORDER BY strength DESC""",
                    (concept_id, concept_id, relation_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM relationships WHERE source_concept_id = ? OR target_concept_id = ? ORDER BY strength DESC",
                    (concept_id, concept_id),
                ).fetchall()
            return [dict(r) for r in rows]

    def traverse_knowledge_graph(self, concept_id: int, max_depth: int = 3, visited: set = None) -> dict:
        if visited is None:
            visited = set()
        if concept_id in visited:
            return {}
        visited.add(concept_id)

        concept = self.get_concept(concept_id)
        if not concept:
            return {}

        relationships = self.get_relationships_for_concept(concept_id)
        neighbors = []
        for rel in relationships:
            neighbor_id = rel["target_concept_id"] if rel["source_concept_id"] == concept_id else rel["source_concept_id"]
            if max_depth > 0 and neighbor_id not in visited:
                subgraph = self.traverse_knowledge_graph(neighbor_id, max_depth - 1, visited)
                neighbors.append({"relationship": rel, "concept": subgraph})

        return {"concept": concept, "relationships": neighbors}

    def find_path(self, source_id: int, target_id: int, max_depth: int = 5) -> list[dict]:
        queue = [(source_id, [])]
        visited = {source_id}
        while queue:
            current, path = queue.pop(0)
            if current == target_id:
                return path
            if len(path) >= max_depth:
                continue
            rels = self.get_relationships_for_concept(current)
            for rel in rels:
                neighbor = rel["target_concept_id"] if rel["source_concept_id"] == current else rel["source_concept_id"]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [{"from": current, "to": neighbor, "relationship": rel}]))
        return []

    # ── Knowledge ──────────────────────────────────────────

    def insert_knowledge(self, concept_id: int, claim: str, source_id: int = None, claim_type: str = "fact", confidence: float = 0.5) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO knowledge (concept_id, source_id, claim, claim_type, confidence) VALUES (?, ?, ?, ?, ?)",
                (concept_id, source_id, claim, claim_type, confidence),
            )
            conn.commit()
            return cursor.lastrowid

    def get_knowledge(self, knowledge_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM knowledge WHERE id = ?", (knowledge_id,)).fetchone()
            return dict(row) if row else None

    def update_knowledge(self, knowledge_id: int, **kwargs) -> bool:
        allowed = {"claim", "claim_type", "confidence", "verification_status", "source_id"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [knowledge_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE knowledge SET {set_clause}, updated_at = datetime('now') WHERE id = ?", values)
            conn.commit()
            return conn.total_changes > 0

    def delete_knowledge(self, knowledge_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM knowledge WHERE id = ?", (knowledge_id,))
            conn.commit()
            return conn.total_changes > 0

    def search_knowledge(self, query: str, claim_type: str = None, verification_status: str = None, limit: int = 20) -> list[dict]:
        with self.get_conn() as conn:
            conditions = ["k.claim LIKE ?"]
            params = [f"%{query}%"]
            if claim_type:
                conditions.append("k.claim_type = ?")
                params.append(claim_type)
            if verification_status:
                conditions.append("k.verification_status = ?")
                params.append(verification_status)
            where = " AND ".join(conditions)
            params.append(limit)
            rows = conn.execute(
                f"SELECT k.* FROM knowledge k WHERE {where} ORDER BY k.confidence DESC LIMIT ?",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def get_knowledge_for_concept(self, concept_id: int) -> list[dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM knowledge WHERE concept_id = ? ORDER BY confidence DESC",
                (concept_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Sources ────────────────────────────────────────────

    def insert_source(self, name: str, source_type: str = "web", url: str = None, reliability: float = 0.5) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO sources (name, source_type, url, reliability) VALUES (?, ?, ?, ?)",
                (name, source_type, url, reliability),
            )
            conn.commit()
            return cursor.lastrowid

    def get_source(self, source_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
            return dict(row) if row else None

    def update_source(self, source_id: int, **kwargs) -> bool:
        allowed = {"name", "source_type", "url", "reliability", "last_fetched"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [source_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE sources SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return conn.total_changes > 0

    def delete_source(self, source_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
            conn.commit()
            return conn.total_changes > 0

    def list_sources(self, source_type: str = None, limit: int = 100) -> list[dict]:
        with self.get_conn() as conn:
            if source_type:
                rows = conn.execute(
                    "SELECT * FROM sources WHERE source_type = ? ORDER BY reliability DESC LIMIT ?",
                    (source_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sources ORDER BY reliability DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Claims ─────────────────────────────────────────────

    def insert_claim(self, knowledge_id: int, claim_text: str, claim_type: str = "fact", confidence: float = 0.5) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO claims (knowledge_id, claim_text, claim_type, confidence) VALUES (?, ?, ?, ?)",
                (knowledge_id, claim_text, claim_type, confidence),
            )
            conn.commit()
            return cursor.lastrowid

    def get_claim(self, claim_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
            return dict(row) if row else None

    def update_claim(self, claim_id: int, **kwargs) -> bool:
        allowed = {"claim_text", "claim_type", "confidence", "status", "supporting_evidence", "contradicting_evidence"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [claim_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE claims SET {set_clause}, updated_at = datetime('now') WHERE id = ?", values)
            conn.commit()
            return conn.total_changes > 0

    def delete_claim(self, claim_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM claims WHERE id = ?", (claim_id,))
            conn.commit()
            return conn.total_changes > 0

    def search_claims(self, query: str, claim_type: str = None, status: str = None, limit: int = 20) -> list[dict]:
        with self.get_conn() as conn:
            conditions = ["c.claim_text LIKE ?"]
            params = [f"%{query}%"]
            if claim_type:
                conditions.append("c.claim_type = ?")
                params.append(claim_type)
            if status:
                conditions.append("c.status = ?")
                params.append(status)
            where = " AND ".join(conditions)
            params.append(limit)
            rows = conn.execute(
                f"SELECT c.* FROM claims c WHERE {where} ORDER BY c.confidence DESC LIMIT ?",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def get_claims_for_knowledge(self, knowledge_id: int) -> list[dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM claims WHERE knowledge_id = ? ORDER BY confidence DESC",
                (knowledge_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Evidence ───────────────────────────────────────────

    def insert_evidence(self, claim_id: int, evidence_text: str, source_id: int = None, evidence_type: str = "supporting", strength: float = 0.5) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO evidence (claim_id, source_id, evidence_text, evidence_type, strength) VALUES (?, ?, ?, ?, ?)",
                (claim_id, source_id, evidence_text, evidence_type, strength),
            )
            if evidence_type == "supporting":
                conn.execute("UPDATE claims SET supporting_evidence = supporting_evidence + 1 WHERE id = ?", (claim_id,))
            else:
                conn.execute("UPDATE claims SET contradicting_evidence = contradicting_evidence + 1 WHERE id = ?", (claim_id,))
            conn.commit()
            return cursor.lastrowid

    def get_evidence(self, evidence_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
            return dict(row) if row else None

    def delete_evidence(self, evidence_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM evidence WHERE id = ?", (evidence_id,))
            conn.commit()
            return conn.total_changes > 0

    def get_evidence_for_claim(self, claim_id: int, evidence_type: str = None) -> list[dict]:
        with self.get_conn() as conn:
            if evidence_type:
                rows = conn.execute(
                    "SELECT * FROM evidence WHERE claim_id = ? AND evidence_type = ? ORDER BY strength DESC",
                    (claim_id, evidence_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM evidence WHERE claim_id = ? ORDER BY strength DESC",
                    (claim_id,),
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Skills ─────────────────────────────────────────────

    def insert_skill(self, name: str, description: str = None, skill_type: str = "general", proficiency: float = 0.0) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (name, description, skill_type, proficiency) VALUES (?, ?, ?, ?)",
                (name, description, skill_type, proficiency),
            )
            conn.commit()
            return cursor.lastrowid

    def get_skill(self, skill_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
            return dict(row) if row else None

    def get_skill_by_name(self, name: str) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM skills WHERE name = ?", (name,)).fetchone()
            return dict(row) if row else None

    def update_skill(self, skill_id: int, **kwargs) -> bool:
        allowed = {"description", "skill_type", "proficiency", "usage_count", "last_used"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [skill_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE skills SET {set_clause}, updated_at = datetime('now') WHERE id = ?", values)
            conn.commit()
            return conn.total_changes > 0

    def delete_skill(self, skill_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
            conn.commit()
            return conn.total_changes > 0

    def list_skills(self, skill_type: str = None, limit: int = 100) -> list[dict]:
        with self.get_conn() as conn:
            if skill_type:
                rows = conn.execute(
                    "SELECT * FROM skills WHERE skill_type = ? ORDER BY proficiency DESC LIMIT ?",
                    (skill_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM skills ORDER BY proficiency DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def use_skill(self, skill_id: int):
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE skills SET usage_count = usage_count + 1, last_used = datetime('now') WHERE id = ?",
                (skill_id,),
            )
            conn.commit()

    # ── Skill Steps ────────────────────────────────────────

    def insert_skill_step(self, skill_id: int, step_order: int, action: str, description: str = None, expected_outcome: str = None) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO skill_steps (skill_id, step_order, action, description, expected_outcome) VALUES (?, ?, ?, ?, ?)",
                (skill_id, step_order, action, description, expected_outcome),
            )
            conn.commit()
            return cursor.lastrowid

    def get_skill_steps(self, skill_id: int) -> list[dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM skill_steps WHERE skill_id = ? ORDER BY step_order ASC",
                (skill_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_skill_step(self, step_id: int, **kwargs) -> bool:
        allowed = {"action", "description", "expected_outcome", "success_rate"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [step_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE skill_steps SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return conn.total_changes > 0

    def delete_skill_step(self, step_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM skill_steps WHERE id = ?", (step_id,))
            conn.commit()
            return conn.total_changes > 0

    # ── Experiences ────────────────────────────────────────

    def insert_experience(self, task_description: str, user_id: int = None, skill_id: int = None, outcome: str = None, success: bool = False, duration_ms: int = None, error_message: str = None, lessons_learned: str = None) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO experiences (user_id, skill_id, task_description, outcome, success, duration_ms, error_message, lessons_learned) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, skill_id, task_description, outcome, int(success), duration_ms, error_message, lessons_learned),
            )
            conn.commit()
            return cursor.lastrowid

    def get_experience(self, experience_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM experiences WHERE id = ?", (experience_id,)).fetchone()
            return dict(row) if row else None

    def list_experiences(self, user_id: int = None, skill_id: int = None, success_only: bool = False, limit: int = 50) -> list[dict]:
        with self.get_conn() as conn:
            conditions = []
            params = []
            if user_id is not None:
                conditions.append("user_id = ?")
                params.append(user_id)
            if skill_id is not None:
                conditions.append("skill_id = ?")
                params.append(skill_id)
            if success_only:
                conditions.append("success = 1")
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(limit)
            rows = conn.execute(
                f"SELECT * FROM experiences {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_experience(self, experience_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM experiences WHERE id = ?", (experience_id,))
            conn.commit()
            return conn.total_changes > 0

    # ── Feedback ───────────────────────────────────────────

    def insert_feedback(self, user_id: int, rating: int, comment: str = None, experience_id: int = None, feedback_type: str = "general") -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO feedback (user_id, experience_id, rating, comment, feedback_type) VALUES (?, ?, ?, ?, ?)",
                (user_id, experience_id, rating, comment, feedback_type),
            )
            conn.commit()
            return cursor.lastrowid

    def get_feedback(self, feedback_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM feedback WHERE id = ?", (feedback_id,)).fetchone()
            return dict(row) if row else None

    def list_feedback(self, user_id: int = None, feedback_type: str = None, limit: int = 50) -> list[dict]:
        with self.get_conn() as conn:
            conditions = []
            params = []
            if user_id is not None:
                conditions.append("user_id = ?")
                params.append(user_id)
            if feedback_type:
                conditions.append("feedback_type = ?")
                params.append(feedback_type)
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(limit)
            rows = conn.execute(
                f"SELECT * FROM feedback {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_feedback(self, feedback_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM feedback WHERE id = ?", (feedback_id,))
            conn.commit()
            return conn.total_changes > 0

    def get_average_rating(self, user_id: int = None) -> Optional[float]:
        with self.get_conn() as conn:
            if user_id:
                row = conn.execute(
                    "SELECT AVG(rating) as avg_rating FROM feedback WHERE user_id = ?", (user_id,)
                ).fetchone()
            else:
                row = conn.execute("SELECT AVG(rating) as avg_rating FROM feedback").fetchone()
            return row["avg_rating"] if row and row["avg_rating"] is not None else None

    # ── Learning Sessions ──────────────────────────────────

    def insert_learning_session(self, user_id: int, topic: str, session_type: str = "exploration", goals: list = None) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO learning_sessions (user_id, topic, session_type, goals) VALUES (?, ?, ?, ?)",
                (user_id, topic, session_type, json.dumps(goals or [])),
            )
            conn.commit()
            return cursor.lastrowid

    def get_learning_session(self, session_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM learning_sessions WHERE id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    def update_learning_session(self, session_id: int, **kwargs) -> bool:
        allowed = {"outcomes", "knowledge_gained", "duration_minutes", "status", "ended_at"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        for k in ("outcomes", "knowledge_gained"):
            if k in fields and isinstance(fields[k], list):
                fields[k] = json.dumps(fields[k])
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [session_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE learning_sessions SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return conn.total_changes > 0

    def list_learning_sessions(self, user_id: int, status: str = None, limit: int = 50) -> list[dict]:
        with self.get_conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM learning_sessions WHERE user_id = ? AND status = ? ORDER BY started_at DESC LIMIT ?",
                    (user_id, status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM learning_sessions WHERE user_id = ? ORDER BY started_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
            return [dict(r) for r in rows]

    def count_learning_sessions_today(self, user_id: int) -> int:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM learning_sessions WHERE user_id = ? AND date(started_at) = date('now')",
                (user_id,),
            ).fetchone()
            return row["cnt"] if row else 0

    def delete_learning_session(self, session_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM learning_sessions WHERE id = ?", (session_id,))
            conn.commit()
            return conn.total_changes > 0

    # ── Research Sessions ──────────────────────────────────

    def insert_research_session(self, user_id: int, query: str) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO research_sessions (user_id, query) VALUES (?, ?)",
                (user_id, query),
            )
            conn.commit()
            return cursor.lastrowid

    def get_research_session(self, session_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM research_sessions WHERE id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    def update_research_session(self, session_id: int, **kwargs) -> bool:
        allowed = {"sources_checked", "findings", "confidence", "contradictions_found", "status", "completed_at"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        if "findings" in fields and isinstance(fields["findings"], list):
            fields["findings"] = json.dumps(fields["findings"])
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [session_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE research_sessions SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return conn.total_changes > 0

    def list_research_sessions(self, user_id: int, status: str = None, limit: int = 50) -> list[dict]:
        with self.get_conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM research_sessions WHERE user_id = ? AND status = ? ORDER BY started_at DESC LIMIT ?",
                    (user_id, status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM research_sessions WHERE user_id = ? ORDER BY started_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
            return [dict(r) for r in rows]

    def delete_research_session(self, session_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM research_sessions WHERE id = ?", (session_id,))
            conn.commit()
            return conn.total_changes > 0

    # ── Contradictions ─────────────────────────────────────

    def insert_contradiction(self, claim_a_id: int, claim_b_id: int, contradiction_type: str = "direct") -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO contradictions (claim_a_id, claim_b_id, contradiction_type) VALUES (?, ?, ?)",
                (claim_a_id, claim_b_id, contradiction_type),
            )
            conn.commit()
            return cursor.lastrowid

    def get_contradiction(self, contradiction_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM contradictions WHERE id = ?", (contradiction_id,)).fetchone()
            return dict(row) if row else None

    def resolve_contradiction(self, contradiction_id: int, resolution: str) -> bool:
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE contradictions SET resolved = 1, resolution = ?, resolved_at = datetime('now') WHERE id = ?",
                (resolution, contradiction_id),
            )
            conn.commit()
            return conn.total_changes > 0

    def list_contradictions(self, resolved: bool = None, limit: int = 50) -> list[dict]:
        with self.get_conn() as conn:
            if resolved is not None:
                rows = conn.execute(
                    "SELECT * FROM contradictions WHERE resolved = ? ORDER BY detected_at DESC LIMIT ?",
                    (int(resolved), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM contradictions ORDER BY detected_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def delete_contradiction(self, contradiction_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM contradictions WHERE id = ?", (contradiction_id,))
            conn.commit()
            return conn.total_changes > 0

    # ── Tasks ──────────────────────────────────────────────

    def insert_task(self, title: str, user_id: int = None, description: str = None, task_type: str = "general", priority: int = 0, due_date: str = None) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (user_id, title, description, task_type, priority, due_date) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, title, description, task_type, priority, due_date),
            )
            conn.commit()
            return cursor.lastrowid

    def get_task(self, task_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return dict(row) if row else None

    def update_task(self, task_id: int, **kwargs) -> bool:
        allowed = {"title", "description", "task_type", "priority", "status", "assigned_to", "due_date", "result"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [task_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE tasks SET {set_clause}, updated_at = datetime('now') WHERE id = ?", values)
            conn.commit()
            return conn.total_changes > 0

    def delete_task(self, task_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return conn.total_changes > 0

    def list_tasks(self, user_id: int = None, status: str = None, task_type: str = None, limit: int = 50) -> list[dict]:
        with self.get_conn() as conn:
            conditions = []
            params = []
            if user_id is not None:
                conditions.append("user_id = ?")
                params.append(user_id)
            if status:
                conditions.append("status = ?")
                params.append(status)
            if task_type:
                conditions.append("task_type = ?")
                params.append(task_type)
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(limit)
            rows = conn.execute(
                f"SELECT * FROM tasks {where} ORDER BY priority DESC, created_at DESC LIMIT ?",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Tool Usage ─────────────────────────────────────────

    def insert_tool_usage(self, tool_name: str, task_id: int = None, conversation_id: int = None, input_data: dict = None, output_data: dict = None, success: bool = True, duration_ms: int = None, error_message: str = None) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO tool_usage (task_id, conversation_id, tool_name, input_data, output_data, success, duration_ms, error_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (task_id, conversation_id, tool_name, json.dumps(input_data or {}), json.dumps(output_data or {}), int(success), duration_ms, error_message),
            )
            conn.commit()
            return cursor.lastrowid

    def get_tool_usage(self, usage_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM tool_usage WHERE id = ?", (usage_id,)).fetchone()
            return dict(row) if row else None

    def list_tool_usage(self, tool_name: str = None, task_id: int = None, limit: int = 100) -> list[dict]:
        with self.get_conn() as conn:
            conditions = []
            params = []
            if tool_name:
                conditions.append("tool_name = ?")
                params.append(tool_name)
            if task_id is not None:
                conditions.append("task_id = ?")
                params.append(task_id)
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(limit)
            rows = conn.execute(
                f"SELECT * FROM tool_usage {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def get_tool_stats(self, tool_name: str) -> dict:
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as total,
                          SUM(success) as successes,
                          AVG(duration_ms) as avg_duration
                   FROM tool_usage WHERE tool_name = ?""",
                (tool_name,),
            ).fetchone()
            if row:
                return {
                    "total": row["total"],
                    "successes": row["successes"] or 0,
                    "failures": row["total"] - (row["successes"] or 0),
                    "avg_duration_ms": row["avg_duration"] or 0,
                }
            return {"total": 0, "successes": 0, "failures": 0, "avg_duration_ms": 0}

    def delete_tool_usage(self, usage_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM tool_usage WHERE id = ?", (usage_id,))
            conn.commit()
            return conn.total_changes > 0

    # ── Curiosity Queue ────────────────────────────────────

    def insert_curiosity(self, topic: str, user_id: int = None, priority: float = 0.5, reason: str = None) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO curiosity_queue (user_id, topic, priority, reason) VALUES (?, ?, ?, ?)",
                (user_id, topic, priority, reason),
            )
            conn.commit()
            return cursor.lastrowid

    def get_curiosity(self, curiosity_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM curiosity_queue WHERE id = ?", (curiosity_id,)).fetchone()
            return dict(row) if row else None

    def get_next_curiosity(self, user_id: int = None) -> Optional[dict]:
        with self.get_conn() as conn:
            if user_id:
                row = conn.execute(
                    """SELECT * FROM curiosity_queue
                       WHERE status = 'pending' AND user_id = ? AND attempts < max_attempts
                       ORDER BY priority DESC LIMIT 1""",
                    (user_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT * FROM curiosity_queue
                       WHERE status = 'pending' AND attempts < max_attempts
                       ORDER BY priority DESC LIMIT 1"""
                ).fetchone()
            return dict(row) if row else None

    def update_curiosity(self, curiosity_id: int, **kwargs) -> bool:
        allowed = {"priority", "reason", "status", "attempts"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [curiosity_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE curiosity_queue SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return conn.total_changes > 0

    def process_curiosity(self, curiosity_id: int):
        with self.get_conn() as conn:
            conn.execute(
                """UPDATE curiosity_queue
                   SET status = 'processed', attempts = attempts + 1, processed_at = datetime('now')
                   WHERE id = ?""",
                (curiosity_id,),
            )
            conn.commit()

    def list_curiosity(self, user_id: int = None, status: str = None, limit: int = 50) -> list[dict]:
        with self.get_conn() as conn:
            conditions = []
            params = []
            if user_id is not None:
                conditions.append("user_id = ?")
                params.append(user_id)
            if status:
                conditions.append("status = ?")
                params.append(status)
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(limit)
            rows = conn.execute(
                f"SELECT * FROM curiosity_queue {where} ORDER BY priority DESC LIMIT ?",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_curiosity(self, curiosity_id: int) -> bool:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM curiosity_queue WHERE id = ?", (curiosity_id,))
            conn.commit()
            return conn.total_changes > 0

    # ── Utility ────────────────────────────────────────────

    def execute_raw(self, query: str, params: tuple = ()) -> list[dict]:
        with self.get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def close(self):
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None

    def backup(self, dest_path: str):
        source = self._get_connection()
        dest = sqlite3.connect(dest_path)
        source.backup(dest)
        dest.close()
