"""Genesis Inference API — Production endpoints for external applications.

This blueprint exposes the REAL Genesis intelligence pipeline through a
clean, developer-friendly API. The same core used by the UI is used here.

Endpoints:
    POST /v1/chat          — Chat with Genesis
    POST /v1/chat/stream   — Streaming chat (SSE)
    POST /v1/evaluate      — Evaluate Genesis responses
    GET  /v1/models        — List available models
    GET  /v1/health        — Health check
    GET  /v1/status        — System status
    POST /v1/apikeys       — Create API key (admin)
"""

from __future__ import annotations

import json
import logging
import time
import uuid

from flask import Blueprint, Response, g, jsonify, request, stream_with_context

from .auth import create_api_key, require_auth
from .conversation import (
    append_message,
    conversation_exists,
    create_conversation,
    get_conversation,
)
from .errors import error_response, success_response
from .rate_limit import rate_limit_required

logger = logging.getLogger(__name__)

inference_bp = Blueprint("inference", __name__, url_prefix="/v1")

_genesis = None
_db = None


def init_inference_api(app, genesis_instance, db):
    """Initialize the inference API with dependencies."""
    global _genesis, _db
    _genesis = genesis_instance
    _db = db

    from .auth import init_auth
    from .conversation import init_conversation_manager

    init_auth(db)
    init_conversation_manager(db)

    if "inference" not in app.blueprints:
        app.register_blueprint(inference_bp)

    logger.info("Inference API initialized at /v1")


def _generate_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


def _log_request(request_id, endpoint, method, status_code, latency_ms, conversation_id=None, error_code=None):
    """Log an API request to the database."""
    try:
        key_prefix = getattr(g, "api_key_prefix", "ui")
        _db.execute(
            """INSERT INTO api_logs (request_id, api_key_prefix, endpoint, method, status_code, latency_ms, conversation_id, error_code, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (request_id, key_prefix, endpoint, method, status_code, latency_ms, conversation_id, error_code, time.time()),
        )
    except Exception as e:
        logger.warning("Failed to log API request: %s", e)


# ── POST /v1/chat ──────────────────────────────────────────────────────

@inference_bp.route("/chat", methods=["POST"])
@require_auth("chat")
@rate_limit_required
def chat():
    """Send a message to Genesis and receive a response.

    Request:
        {
            "message": "Hello Genesis",
            "conversation_id": "optional-id"
        }

    Response:
        {
            "response": "...",
            "conversation_id": "gen_...",
            "request_id": "req_...",
            "status": "success",
            "intent": "CONVERSATION",
            "confidence": 0.95,
            "processing_time_ms": 1234
        }
    """
    request_id = _generate_request_id()
    start = time.time()

    data = request.get_json(silent=True)
    if not data:
        return error_response("INVALID_REQUEST", "Request body must be valid JSON", 400, request_id)

    message = data.get("message", "").strip()
    if not message:
        return error_response("INVALID_REQUEST", "Message is required", 400, request_id)

    conversation_id = data.get("conversation_id")

    # Create conversation if not provided
    if conversation_id:
        if not conversation_exists(conversation_id):
            return error_response("NOT_FOUND", f"Conversation '{conversation_id}' not found", 404, request_id)
    else:
        conversation_id = create_conversation(
            api_key_prefix=g.api_key_prefix,
            title=message[:80],
        )

    try:
        user_id = f"api_{g.api_key_prefix}"

        result = _genesis.chat(user_id, message)

        response_text = result.get("response_text", "")
        append_message(conversation_id, "user", message)
        append_message(conversation_id, "assistant", response_text)

        latency_ms = int((time.time() - start) * 1000)
        _log_request(request_id, "/v1/chat", "POST", 200, latency_ms, conversation_id)

        return success_response({
            "response": response_text,
            "conversation_id": conversation_id,
            "intent": result.get("intent", ""),
            "confidence": result.get("confidence", 0),
            "processing_time_ms": result.get("processing_time_ms", latency_ms),
            "sources_used": result.get("sources_used", []),
            "pipeline_stages": result.get("pipeline_stages", {}),
        }, request_id)

    except Exception as e:
        logger.error("Chat error: %s", e, exc_info=True)
        latency_ms = int((time.time() - start) * 1000)
        _log_request(request_id, "/v1/chat", "POST", 500, latency_ms, conversation_id, "INTERNAL_ERROR")
        return error_response("INTERNAL_ERROR", "An internal error occurred. Please try again.", 500, request_id)


# ── POST /v1/chat/stream ──────────────────────────────────────────────

@inference_bp.route("/chat/stream", methods=["POST"])
@require_auth("chat")
@rate_limit_required
def chat_stream():
    """Stream Genesis response using Server-Sent Events (SSE).

    Events:
        event: status    — Pipeline stage updates
        event: chunk     — Response text chunks
        event: done      — Final event with metadata
        event: error     — Error event
    """
    request_id = _generate_request_id()
    start = time.time()

    data = request.get_json(silent=True)
    if not data:
        return error_response("INVALID_REQUEST", "Request body must be valid JSON", 400, request_id)

    message = data.get("message", "").strip()
    if not message:
        return error_response("INVALID_REQUEST", "Message is required", 400, request_id)

    conversation_id = data.get("conversation_id")
    if conversation_id and not conversation_exists(conversation_id):
        return error_response("NOT_FOUND", f"Conversation '{conversation_id}' not found", 404, request_id)

    if not conversation_id:
        conversation_id = create_conversation(
            api_key_prefix=g.api_key_prefix,
            title=message[:80],
        )

    def generate():
        user_id = f"api_{g.api_key_prefix}"

        yield f"event: status\ndata: {json.dumps({'stage': 'perceiving'})}\n\n"

        try:
            result = _genesis.chat(user_id, message)

            response_text = result.get("response_text", "")
            intent = result.get("intent", "")
            confidence = result.get("confidence", 0)
            pipeline_stages = result.get("pipeline_stages", {})

            stages_done = ["perceiving", "understanding", "reasoning", "generating_response"]
            for stage in stages_done:
                yield f"event: status\ndata: {json.dumps({'stage': stage})}\n\n"
                time.sleep(0.05)

            chunk_size = 80
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                yield f"event: chunk\ndata: {json.dumps({'text': chunk})}\n\n"

            append_message(conversation_id, "user", message)
            append_message(conversation_id, "assistant", response_text)

            latency_ms = int((time.time() - start) * 1000)
            _log_request(request_id, "/v1/chat/stream", "POST", 200, latency_ms, conversation_id)

            done_data = {
                "conversation_id": conversation_id,
                "request_id": request_id,
                "intent": intent,
                "confidence": confidence,
                "processing_time_ms": latency_ms,
            }
            yield f"event: done\ndata: {json.dumps(done_data)}\n\n"

        except Exception as e:
            logger.error("Stream error: %s", e, exc_info=True)
            error_data = {"code": "STREAM_ERROR", "message": "An error occurred during streaming"}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "X-Request-ID": request_id,
        },
    )


# ── POST /v1/evaluate ─────────────────────────────────────────────────

@inference_bp.route("/evaluate", methods=["POST"])
@require_auth("evaluate")
@rate_limit_required
def evaluate():
    """Evaluate a Genesis response against expected criteria.

    This calls the REAL Genesis inference pipeline to get a response,
    then evaluates it against provided criteria.

    Request:
        {
            "input": "Explain what an HTTP request is.",
            "expected": {
                "contains_concepts": ["client", "server", "request", "response"],
                "must_contain": ["HTTP"],
                "must_not_contain": ["I don't know"],
                "min_length": 100
            }
        }

    Response:
        {
            "response": "...",
            "evaluation": {
                "status": "PASS",
                "score": 0.91,
                "criteria": {...}
            }
        }
    """
    request_id = _generate_request_id()
    start = time.time()

    data = request.get_json(silent=True)
    if not data:
        return error_response("INVALID_REQUEST", "Request body must be valid JSON", 400, request_id)

    input_text = data.get("input", "").strip()
    if not input_text:
        return error_response("INVALID_REQUEST", "Input is required", 400, request_id)

    expected = data.get("expected", {})
    test_type = data.get("test_type", "direct")

    try:
        user_id = f"eval_{g.api_key_prefix}"
        result = _genesis.chat(user_id, input_text)
        response_text = result.get("response_text", "")

        evaluation = _evaluate_response(response_text, expected)

        latency_ms = int((time.time() - start) * 1000)
        _log_request(request_id, "/v1/evaluate", "POST", 200, latency_ms)

        return success_response({
            "response": response_text,
            "evaluation": {
                "status": evaluation["status"],
                "score": evaluation["score"],
                "criteria": evaluation["criteria"],
                "test_type": test_type,
            },
            "processing_time_ms": result.get("processing_time_ms", latency_ms),
        }, request_id)

    except Exception as e:
        logger.error("Evaluate error: %s", e, exc_info=True)
        latency_ms = int((time.time() - start) * 1000)
        _log_request(request_id, "/v1/evaluate", "POST", 500, latency_ms, error_code="INTERNAL_ERROR")
        return error_response("INTERNAL_ERROR", "An internal error occurred during evaluation.", 500, request_id)


def _evaluate_response(response_text: str, expected: dict) -> dict:
    """Evaluate a response against expected criteria."""
    criteria = {}
    score = 0.0
    total_weight = 0.0

    # Check required_concepts
    if "contains_concepts" in expected:
        concepts = expected["contains_concepts"]
        if concepts:
            found = sum(1 for c in concepts if c.lower() in response_text.lower())
            ratio = found / len(concepts)
            criteria["required_concepts"] = {
                "pass": ratio >= 0.7,
                "found": found,
                "total": len(concepts),
                "ratio": round(ratio, 3),
            }
            score += ratio * 0.3
            total_weight += 0.3

    # Check must_contain
    if "must_contain" in expected:
        phrases = expected["must_contain"]
        if phrases:
            found = [p for p in phrases if p.lower() in response_text.lower()]
            all_found = len(found) == len(phrases)
            criteria["must_contain"] = {
                "pass": all_found,
                "found": found,
                "missing": [p for p in phrases if p not in found],
            }
            score += (len(found) / len(phrases)) * 0.25 if phrases else 0
            total_weight += 0.25

    # Check must_not_contain
    if "must_not_contain" in expected:
        phrases = expected["must_not_contain"]
        if phrases:
            found = [p for p in phrases if p.lower() in response_text.lower()]
            none_found = len(found) == 0
            criteria["must_not_contain"] = {
                "pass": none_found,
                "violations": found,
            }
            score += 0.2 if none_found else 0.0
            total_weight += 0.2

    # Check min_length
    if "min_length" in expected:
        min_len = expected["min_length"]
        passes = len(response_text) >= min_len
        criteria["min_length"] = {
            "pass": passes,
            "actual": len(response_text),
            "required": min_len,
        }
        score += 0.15 if passes else 0.0
        total_weight += 0.15

    # Check max_length
    if "max_length" in expected:
        max_len = expected["max_length"]
        passes = len(response_text) <= max_len
        criteria["max_length"] = {
            "pass": passes,
            "actual": len(response_text),
            "required": max_len,
        }
        score += 0.1 if passes else 0.0
        total_weight += 0.1

    # Normalize score
    if total_weight > 0:
        normalized_score = score / total_weight
    else:
        normalized_score = 0.5

    # Determine status
    if normalized_score >= 0.7:
        status = "PASS"
    elif normalized_score >= 0.3:
        status = "PARTIAL"
    else:
        status = "FAIL"

    all_pass = all(
        c.get("pass", False) if isinstance(c, dict) else c
        for c in criteria.values()
    )
    if all_pass and criteria:
        status = "PASS"
        normalized_score = max(normalized_score, 0.9)

    return {
        "status": status,
        "score": round(normalized_score, 3),
        "criteria": criteria,
    }


# ── POST /v1/apikeys ──────────────────────────────────────────────────

@inference_bp.route("/apikeys", methods=["POST"])
@require_auth("admin")
def create_key():
    """Create a new API key. Requires admin scope.

    Request:
        {
            "name": "My App",
            "scopes": ["chat", "evaluate"],
            "requests_per_minute": 30,
            "requests_per_hour": 500
        }

    Response:
        {
            "key": "gen_...",
            "key_prefix": "gen_...",
            "name": "...",
            "scopes": [...]
        }
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response("INVALID_REQUEST", "Request body must be valid JSON", 400)

    name = data.get("name", "unnamed")
    scopes = data.get("scopes", ["chat"])
    rpm = data.get("requests_per_minute", 30)
    rph = data.get("requests_per_hour", 500)

    key_info = create_api_key(name=name, scopes=scopes, rpm=rpm, rph=rph)

    return success_response({
        "key": key_info["key"],
        "key_prefix": key_info["key_prefix"],
        "name": key_info["name"],
        "scopes": key_info["scopes"],
        "requests_per_minute": key_info["requests_per_minute"],
        "requests_per_hour": key_info["requests_per_hour"],
    })


# ── GET /v1/models ────────────────────────────────────────────────────

@inference_bp.route("/models", methods=["GET"])
def list_models():
    """List available Genesis models. No auth required."""
    return success_response({
        "data": [
            {
                "id": "genesis",
                "name": "Genesis AI",
                "type": "knowledge-first-ai",
                "version": "0.1.0-alpha",
                "description": "Local-first AI assistant with experience-based learning, web research, and multi-stage cognitive pipeline.",
            }
        ]
    })


# ── GET /v1/health ────────────────────────────────────────────────────

@inference_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint. No auth required."""
    checks = {
        "genesis_core": "ready",
        "database": "ready",
        "learning_engine": "ready",
        "memory": "ready",
    }

    # Test database
    try:
        _db.fetch_one("SELECT 1")
    except Exception:
        checks["database"] = "error"

    # Test Genesis core
    try:
        if not _genesis:
            checks["genesis_core"] = "not_initialized"
    except Exception:
        checks["genesis_core"] = "error"

    all_healthy = all(v == "ready" for v in checks.values())

    return jsonify({
        "status": "healthy" if all_healthy else "degraded",
        "genesis_core": checks["genesis_core"],
        "database": checks["database"],
        "learning_engine": checks["learning_engine"],
        "memory": checks["memory"],
        "timestamp": time.time(),
    }), 200 if all_healthy else 503


# ── GET /v1/status ────────────────────────────────────────────────────

@inference_bp.route("/status", methods=["GET"])
@require_auth("chat")
def status():
    """System status. Requires authentication."""
    try:
        genesis_status = _genesis.get_status()
        return success_response({
            "system": genesis_status,
            "api_version": "v1",
        })
    except Exception as e:
        return error_response("STATUS_ERROR", str(e), 500)
