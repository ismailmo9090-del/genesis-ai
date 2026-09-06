"""Conversation manager — persistent conversation IDs and history."""

from __future__ import annotations

import json
import logging
import time
import uuid

logger = logging.getLogger(__name__)

_db = None


def init_conversation_manager(db):
    """Initialize with database reference."""
    global _db
    _db = db


def create_conversation(api_key_prefix: str = None, title: str = None) -> str:
    """Create a new conversation and return its ID."""
    conv_id = f"gen_{uuid.uuid4().hex[:12]}"
    _db.execute(
        """INSERT INTO api_conversations (conversation_id, api_key_prefix, title, created_at, updated_at, message_count)
           VALUES (?, ?, ?, ?, ?, 0)""",
        (conv_id, api_key_prefix, title, time.time(), time.time()),
    )
    logger.info("Created conversation: %s (key=%s)", conv_id, api_key_prefix)
    return conv_id


def append_message(conversation_id: str, role: str, content: str):
    """Append a message to a conversation."""
    _db.execute(
        """UPDATE api_conversations
           SET message_count = message_count + 1, updated_at = ?
           WHERE conversation_id = ?""",
        (time.time(), conversation_id),
    )


def get_conversation(conversation_id: str) -> dict | None:
    """Get conversation metadata."""
    row = _db.fetch_one(
        "SELECT conversation_id, api_key_prefix, title, created_at, updated_at, message_count FROM api_conversations WHERE conversation_id = ?",
        (conversation_id,),
    )
    if not row:
        return None
    return {
        "conversation_id": row[0],
        "api_key_prefix": row[1],
        "title": row[2],
        "created_at": row[3],
        "updated_at": row[4],
        "message_count": row[5],
    }


def conversation_exists(conversation_id: str) -> bool:
    """Check if a conversation exists."""
    row = _db.fetch_one(
        "SELECT 1 FROM api_conversations WHERE conversation_id = ?",
        (conversation_id,),
    )
    return row is not None
