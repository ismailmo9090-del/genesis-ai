"""Privacy engine enforcing data protection and transparency."""

import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from genesis_ai.database.db import DatabaseManager
from genesis_ai.config.settings import PRIVACY_LEVEL


class RequestType:
    WEB_SEARCH = "web_search"
    API_CALL = "api_call"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    DATABASE_QUERY = "database_query"
    LOCAL_PROCESS = "local_process"


DANGEROUS_DATA_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),  # Credit card
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # Email
    re.compile(r"\b\d{3}[\s.-]?\d{3}[\s.-]?\d{4}\b"),  # Phone number
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),  # IP address
    re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+"),  # Passwords
    re.compile(r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?key)\s*[:=]\s*\S+"),  # API keys
]

SENSITIVE_FIELDS = {
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "access_key", "private_key", "ssn", "credit_card", "card_number",
}


@dataclass
class PrivacyCheck:
    allowed: bool
    reason: str = ""
    data_filtered: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExternalRequest:
    timestamp: str
    request_type: str
    url: Optional[str] = None
    data_sent: dict = field(default_factory=dict)
    data_filtered: bool = False
    user_id: Optional[int] = None


class PrivacyEngine:
    """Enforces privacy rules: no telemetry, no background uploads, minimal web data."""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.privacy_level = PRIVACY_LEVEL
        self._request_log: list[ExternalRequest] = []
        self._web_requests_this_hour = 0
        self._hour_start = time.time()
        self._ensure_tables()

    def _ensure_tables(self):
        with self.db.get_conn() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS privacy_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    request_type TEXT NOT NULL,
                    url TEXT,
                    data_sent TEXT DEFAULT '{}',
                    data_filtered INTEGER DEFAULT 0,
                    user_id INTEGER,
                    created_at TEXT DEFAULT (datetime('now'))
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS user_data_inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    data_type TEXT NOT NULL,
                    location TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )"""
            )
            conn.commit()

    def check_request(self, request_type: str, data: dict = None) -> PrivacyCheck:
        data = data or {}
        check = PrivacyCheck(allowed=True)
        if request_type == RequestType.WEB_SEARCH:
            check = self._check_web_request(data)
        elif request_type == RequestType.API_CALL:
            check = self._check_api_call(data)
        elif request_type == RequestType.FILE_READ:
            check = self._check_file_request(data, is_write=False)
        elif request_type == RequestType.FILE_WRITE:
            check = self._check_file_request(data, is_write=True)
        elif request_type == RequestType.DATABASE_QUERY:
            check = self._check_database_request(data)
        elif request_type == RequestType.LOCAL_PROCESS:
            check = PrivacyCheck(allowed=True)
        else:
            check = PrivacyCheck(allowed=False, reason=f"Unknown request type: {request_type}")
        self._log_request(
            ExternalRequest(
                timestamp=datetime.now(timezone.utc).isoformat(),
                request_type=request_type,
                data_sent=data,
                data_filtered=bool(check.data_filtered),
            )
        )
        return check

    def sanitize_for_web(self, data: dict) -> dict:
        cleaned = {}
        for key, value in data.items():
            key_lower = key.lower()
            if key_lower in SENSITIVE_FIELDS:
                continue
            if isinstance(value, str):
                sanitized_value = self._sanitize_string(value)
                if sanitized_value != value:
                    cleaned[key] = sanitized_value
                else:
                    cleaned[key] = value
            elif isinstance(value, dict):
                cleaned[key] = self.sanitize_for_web(value)
            elif isinstance(value, list):
                cleaned[key] = [
                    self.sanitize_for_web(item) if isinstance(item, dict)
                    else self._sanitize_string(str(item)) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                cleaned[key] = value
        return cleaned

    def get_privacy_report(self) -> dict:
        with self.db.get_conn() as conn:
            user_count = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
            memory_count = conn.execute("SELECT COUNT(*) as cnt FROM memories").fetchone()["cnt"]
            knowledge_count = conn.execute("SELECT COUNT(*) as cnt FROM knowledge").fetchone()["cnt"]
            conversation_count = conn.execute("SELECT COUNT(*) as cnt FROM conversations").fetchone()["cnt"]
            message_count = conn.execute("SELECT COUNT(*) as cnt FROM messages").fetchone()["cnt"]
            feedback_count = conn.execute("SELECT COUNT(*) as cnt FROM feedback").fetchone()["cnt"]
            request_count = conn.execute("SELECT COUNT(*) as cnt FROM privacy_log").fetchone()["cnt"]
            recent_requests = conn.execute(
                "SELECT request_type, COUNT(*) as cnt FROM privacy_log GROUP BY request_type"
            ).fetchall()
        return {
            "privacy_level": self.privacy_level,
            "data_stored": {
                "users": user_count,
                "memories": memory_count,
                "knowledge_claims": knowledge_count,
                "conversations": conversation_count,
                "messages": message_count,
                "feedback_entries": feedback_count,
            },
            "external_requests_total": request_count,
            "requests_by_type": {row["request_type"]: row["cnt"] for row in recent_requests},
            "telemetry_enabled": False,
            "background_uploads": False,
            "data_retention": "user-controlled",
            "encryption": "local-only",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def export_user_data(self, user_id: int) -> dict:
        with self.db.get_conn() as conn:
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            memories = conn.execute(
                "SELECT * FROM memories WHERE user_id = ?", (user_id,)
            ).fetchall()
            conversations = conn.execute(
                "SELECT * FROM conversations WHERE user_id = ?", (user_id,)
            ).fetchall()
            messages = conn.execute(
                """SELECT m.* FROM messages m
                   JOIN conversations c ON m.conversation_id = c.id
                   WHERE c.user_id = ?""",
                (user_id,),
            ).fetchall()
            feedback = conn.execute(
                "SELECT * FROM feedback WHERE user_id = ?", (user_id,)
            ).fetchall()
            learning = conn.execute(
                "SELECT * FROM learning_sessions WHERE user_id = ?", (user_id,)
            ).fetchall()
            research = conn.execute(
                "SELECT * FROM research_sessions WHERE user_id = ?", (user_id,)
            ).fetchall()
            curiosity = conn.execute(
                "SELECT * FROM curiosity_queue WHERE user_id = ?", (user_id,)
            ).fetchall()
        return {
            "user": dict(user) if user else None,
            "memories": [dict(r) for r in memories],
            "conversations": [dict(r) for r in conversations],
            "messages": [dict(r) for r in messages],
            "feedback": [dict(r) for r in feedback],
            "learning_sessions": [dict(r) for r in learning],
            "research_sessions": [dict(r) for r in research],
            "curiosity_queue": [dict(r) for r in curiosity],
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "data_format": "JSON",
            "total_items": (
                len(memories) + len(conversations) + len(messages)
                + len(feedback) + len(learning) + len(research)
            ),
        }

    def delete_user_data(self, user_id: int) -> bool:
        try:
            with self.db.get_conn() as conn:
                conn.execute("DELETE FROM curiosity_queue WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM research_sessions WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM learning_sessions WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM feedback WHERE user_id = ?", (user_id,))
                conv_ids = [
                    r["id"]
                    for r in conn.execute(
                        "SELECT id FROM conversations WHERE user_id = ?", (user_id,)
                    ).fetchall()
                ]
                if conv_ids:
                    placeholders = ",".join("?" * len(conv_ids))
                    conn.execute(
                        f"DELETE FROM messages WHERE conversation_id IN ({placeholders})",
                        conv_ids,
                    )
                conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
            return True
        except Exception:
            return False

    def get_data_inventory(self, user_id: int = None) -> list[dict]:
        inventory = []
        with self.db.get_conn() as conn:
            if user_id:
                inventory.append(
                    {
                        "data_type": "user_profile",
                        "location": "users table",
                        "description": "Username, display name, email, preferences",
                        "user_id": user_id,
                    }
                )
                mem_count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM memories WHERE user_id = ?", (user_id,)
                ).fetchone()["cnt"]
                inventory.append(
                    {
                        "data_type": "memories",
                        "location": "memories table",
                        "description": f"{mem_count} memory entries",
                        "user_id": user_id,
                        "count": mem_count,
                    }
                )
                conv_count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM conversations WHERE user_id = ?", (user_id,)
                ).fetchone()["cnt"]
                inventory.append(
                    {
                        "data_type": "conversations",
                        "location": "conversations table",
                        "description": f"{conv_count} conversations",
                        "user_id": user_id,
                        "count": conv_count,
                    }
                )
                msg_count = conn.execute(
                    """SELECT COUNT(*) as cnt FROM messages m
                       JOIN conversations c ON m.conversation_id = c.id
                       WHERE c.user_id = ?""",
                    (user_id,),
                ).fetchone()["cnt"]
                inventory.append(
                    {
                        "data_type": "messages",
                        "location": "messages table",
                        "description": f"{msg_count} messages",
                        "user_id": user_id,
                        "count": msg_count,
                    }
                )
                fb_count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM feedback WHERE user_id = ?", (user_id,)
                ).fetchone()["cnt"]
                inventory.append(
                    {
                        "data_type": "feedback",
                        "location": "feedback table",
                        "description": f"{fb_count} feedback entries",
                        "user_id": user_id,
                        "count": fb_count,
                    }
                )
            else:
                tables = [
                    ("users", "user profiles"),
                    ("memories", "memory entries"),
                    ("conversations", "conversations"),
                    ("messages", "messages"),
                    ("knowledge", "knowledge claims"),
                    ("concepts", "concepts"),
                    ("relationships", "relationships"),
                    ("feedback", "feedback entries"),
                    ("learning_sessions", "learning sessions"),
                    ("research_sessions", "research sessions"),
                    ("privacy_log", "privacy audit log"),
                ]
                for table_name, desc in tables:
                    count = conn.execute(f"SELECT COUNT(*) as cnt FROM {table_name}").fetchone()["cnt"]
                    inventory.append(
                        {
                            "data_type": table_name,
                            "location": f"{table_name} table",
                            "description": f"{count} {desc}",
                            "count": count,
                        }
                    )
        return inventory

    def _check_web_request(self, data: dict) -> PrivacyCheck:
        check = PrivacyCheck(allowed=True)
        self._reset_hourly_counter()
        if self._web_requests_this_hour >= 20:
            check.allowed = False
            check.reason = "Hourly web request limit exceeded"
            return check
        sanitized = self.sanitize_for_web(data)
        if sanitized != data:
            check.data_filtered = sanitized
            check.warnings.append("Sensitive data filtered from web request")
        if self.privacy_level == "high":
            minimal_keys = {"query", "search_term", "topic", "url"}
            filtered = {k: v for k, v in sanitized.items() if k in minimal_keys}
            if filtered != sanitized:
                check.data_filtered = filtered
                check.warnings.append("Additional fields removed for high privacy")
        self._web_requests_this_hour += 1
        return check

    def _check_api_call(self, data: dict) -> PrivacyCheck:
        check = PrivacyCheck(allowed=True)
        sanitized = self.sanitize_for_web(data)
        if sanitized != data:
            check.data_filtered = sanitized
            check.warnings.append("Sensitive data filtered from API call")
        return check

    def _check_file_request(self, data: dict, is_write: bool) -> PrivacyCheck:
        check = PrivacyCheck(allowed=True)
        file_path = data.get("path", data.get("file_path", ""))
        if file_path:
            sensitive_patterns = [
                r"/etc/passwd", r"/etc/shadow", r"\.ssh/", r"\.env",
                r"credentials", r"secrets", r"\.key$",
            ]
            for pattern in sensitive_patterns:
                if re.search(pattern, file_path, re.IGNORECASE):
                    check.allowed = False
                    check.reason = f"Access to sensitive file blocked: {file_path}"
                    return check
        return check

    def _check_database_request(self, data: dict) -> PrivacyCheck:
        check = PrivacyCheck(allowed=True)
        query = data.get("query", "")
        if query:
            dangerous_ops = ["DROP", "TRUNCATE", "ALTER TABLE"]
            query_upper = query.upper()
            for op in dangerous_ops:
                if op in query_upper:
                    check.allowed = False
                    check.reason = f"Dangerous database operation blocked: {op}"
                    return check
        return check

    def _sanitize_string(self, text: str) -> str:
        sanitized = text
        for pattern in DANGEROUS_DATA_PATTERNS:
            sanitized = pattern.sub("[REDACTED]", sanitized)
        return sanitized

    def _log_request(self, request: ExternalRequest):
        with self.db.get_conn() as conn:
            conn.execute(
                """INSERT INTO privacy_log (timestamp, request_type, url, data_sent, data_filtered, user_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    request.timestamp,
                    request.request_type,
                    request.url,
                    json.dumps(request.data_sent),
                    int(request.data_filtered),
                    request.user_id,
                ),
            )
            conn.commit()

    def _reset_hourly_counter(self):
        now = time.time()
        if now - self._hour_start >= 3600:
            self._web_requests_this_hour = 0
            self._hour_start = now
