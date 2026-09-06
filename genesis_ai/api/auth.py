"""API Key authentication and permission middleware."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from functools import wraps

from flask import g, request

from .errors import error_response

logger = logging.getLogger(__name__)

_VALID_SCOPES = {"chat", "evaluate", "learning", "admin"}
_db = None


def init_auth(db):
    """Initialize auth with database reference."""
    global _db
    _db = db


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        (raw_key, key_hash, key_prefix)
    """
    raw_key = f"gen_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(raw_key)
    key_prefix = raw_key[:12]
    return raw_key, key_hash, key_prefix


def _hash_key(key: str) -> str:
    """SHA256 hash of an API key."""
    return hashlib.sha256(key.encode()).hexdigest()


def create_api_key(name: str, scopes: list[str] = None, rpm: int = 30, rph: int = 500) -> dict:
    """Create and store a new API key. Returns key info (raw key shown once)."""
    raw_key, key_hash, key_prefix = generate_api_key()
    if scopes is None:
        scopes = ["chat"]
    valid_scopes = [s for s in scopes if s in _VALID_SCOPES]
    if not valid_scopes:
        valid_scopes = ["chat"]

    _db.execute(
        """INSERT INTO api_keys (key_hash, key_prefix, name, scopes, requests_per_minute, requests_per_hour, is_active, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
        (key_hash, key_prefix, name, json.dumps(valid_scopes), rpm, rph, time.time()),
    )

    logger.info("Created API key: %s (name=%s, scopes=%s)", key_prefix, name, valid_scopes)

    return {
        "key": raw_key,
        "key_prefix": key_prefix,
        "name": name,
        "scopes": valid_scopes,
        "requests_per_minute": rpm,
        "requests_per_hour": rph,
    }


def validate_api_key(raw_key: str) -> dict | None:
    """Validate an API key and return its record, or None if invalid."""
    key_hash = _hash_key(raw_key)
    row = _db.fetch_one(
        "SELECT key_prefix, name, scopes, requests_per_minute, requests_per_hour, is_active FROM api_keys WHERE key_hash = ?",
        (key_hash,),
    )
    if not row:
        return None
    key_prefix, name, scopes_json, rpm, rph, is_active = row
    if not is_active:
        return None
    return {
        "key_prefix": key_prefix,
        "name": name,
        "scopes": json.loads(scopes_json),
        "requests_per_minute": rpm,
        "requests_per_hour": rph,
    }


def require_auth(required_scope: str):
    """Decorator: require a valid API key with the given scope.

    Usage:
        @require_auth("chat")
        def my_endpoint():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return error_response("UNAUTHORIZED", "Missing or invalid Authorization header. Use: Bearer <api_key>", 401)

            raw_key = auth_header[7:].strip()
            if not raw_key:
                return error_response("UNAUTHORIZED", "Empty API key", 401)

            key_info = validate_api_key(raw_key)
            if not key_info:
                return error_response("INVALID_API_KEY", "Invalid or inactive API key", 401)

            if required_scope not in key_info["scopes"] and "admin" not in key_info["scopes"]:
                return error_response(
                    "FORBIDDEN",
                    f"API key does not have '{required_scope}' scope. Available: {key_info['scopes']}",
                    403,
                )

            g.api_key = key_info
            g.api_key_prefix = key_info["key_prefix"]

            _update_last_used(key_info["key_prefix"])

            return f(*args, **kwargs)
        return decorated
    return decorator


def _update_last_used(key_prefix: str):
    """Update the last_used_at timestamp for a key."""
    try:
        _db.execute(
            "UPDATE api_keys SET last_used_at = ? WHERE key_prefix = ?",
            (time.time(), key_prefix),
        )
    except Exception:
        pass
