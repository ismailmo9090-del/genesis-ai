"""Genesis Code Generation API — endpoints for code generation and modification.

Endpoints:
    POST /v1/code/generate   — Generate new code from a request
    POST /v1/code/modify     — Modify existing code
    POST /v1/code/debug      — Debug and fix code
    POST /v1/code/validate   — Validate code files
    GET  /v1/code/history    — Generation history
"""

from __future__ import annotations

import json
import logging
import time

from flask import Blueprint, g, jsonify, request

from .auth import require_auth
from .rate_limit import rate_limit_required

logger = logging.getLogger(__name__)

code_bp = Blueprint("code", __name__, url_prefix="/v1/code")

_genesis = None
_code_engine = None


def init_code_api(app, genesis_instance=None, code_engine=None):
    global _genesis, _code_engine
    _genesis = genesis_instance
    _code_engine = code_engine

    if "code" not in app.blueprints:
        app.register_blueprint(code_bp)

    logger.info("Code Generation API initialized at /v1/code")


@code_bp.route("/generate", methods=["POST"])
@require_auth("chat")
@rate_limit_required
def generate():
    """Generate new code from a natural language request.

    Request:
        {
            "request": "Create a REST API with Flask",
            "language": "python",
            "framework": "flask",
            "project_type": "rest_api"
        }

    Response:
        {
            "success": true,
            "files": {"src/main.py": "...", ...},
            "plan": {...},
            "validation": {...},
            "generation_time_ms": 123
        }
    """
    start = time.time()
    data = request.get_json(silent=True) or {}
    request_str = data.get("request", "")
    language = data.get("language")
    framework = data.get("framework")
    project_type = data.get("project_type")

    if not request_str:
        return jsonify({"error": "Missing 'request' field"}), 400

    if _code_engine is None:
        from genesis_ai.core.code.engine import CodeGenerationEngine
        engine = CodeGenerationEngine()
    else:
        engine = _code_engine

    response = engine.generate(request_str, language=language, framework=framework, project_type=project_type)

    latency_ms = (time.time() - start) * 1000
    result = response.to_dict()
    result["processing_time_ms"] = round(latency_ms, 1)

    return jsonify(result), 200 if response.success else 500


@code_bp.route("/modify", methods=["POST"])
@require_auth("chat")
@rate_limit_required
def modify():
    """Modify existing code based on changes.

    Request:
        {
            "code": "existing code...",
            "changes": "Add error handling",
            "language": "python"
        }

    Response: Same as generate.
    """
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    changes = data.get("changes", "")
    language = data.get("language")

    if not code:
        return jsonify({"error": "Missing 'code' field"}), 400
    if not changes:
        return jsonify({"error": "Missing 'changes' field"}), 400

    if _code_engine is None:
        from genesis_ai.core.code.engine import CodeGenerationEngine
        engine = CodeGenerationEngine()
    else:
        engine = _code_engine

    response = engine.modify(code, changes, language=language)
    return jsonify(response.to_dict()), 200 if response.success else 500


@code_bp.route("/debug", methods=["POST"])
@require_auth("chat")
@rate_limit_required
def debug():
    """Debug and fix code with an error.

    Request:
        {
            "code": "def add(a, b):\n  return a + b",
            "error": "TypeError: unsupported operand type(s)",
            "language": "python"
        }

    Response: Same as generate.
    """
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    error = data.get("error", "")
    language = data.get("language")

    if not code:
        return jsonify({"error": "Missing 'code' field"}), 400
    if not error:
        return jsonify({"error": "Missing 'error' field"}), 400

    if _code_engine is None:
        from genesis_ai.core.code.engine import CodeGenerationEngine
        engine = CodeGenerationEngine()
    else:
        engine = _code_engine

    response = engine.debug(code, error, language=language)
    return jsonify(response.to_dict()), 200 if response.success else 500


@code_bp.route("/validate", methods=["POST"])
@require_auth("chat")
@rate_limit_required
def validate():
    """Validate code files.

    Request:
        {
            "files": {"main.py": "..."},
            "language": "python"
        }

    Response:
        {
            "valid": true,
            "files_checked": 1,
            "files_passed": 1,
            "errors": [],
            "warnings": []
        }
    """
    data = request.get_json(silent=True) or {}
    files = data.get("files", {})
    language = data.get("language")

    if not files:
        return jsonify({"error": "Missing 'files' field"}), 400

    if _code_engine is None:
        from genesis_ai.core.code.engine import CodeGenerationEngine
        engine = CodeGenerationEngine()
    else:
        engine = _code_engine

    result = engine.validate_files(files, language=language)
    return jsonify({
        "valid": result.valid,
        "files_checked": result.files_checked,
        "files_passed": result.files_passed,
        "errors": [{"file": e.file_path, "line": e.line, "message": e.message, "severity": e.severity.value} for e in result.errors],
        "warnings": [{"file": w.file_path, "line": w.line, "message": w.message, "severity": w.severity.value} for w in result.warnings],
    }), 200


@code_bp.route("/history", methods=["GET"])
@require_auth("chat")
def history():
    """Get code generation history.

    Response:
        {
            "history": [...],
            "count": 10
        }
    """
    if _code_engine is None:
        return jsonify({"history": [], "count": 0}), 200

    history = _code_engine.get_history()
    entries = []
    for resp in history[-50:]:
        entries.append({
            "request_type": resp.request_type,
            "language": resp.language,
            "success": resp.success,
            "file_count": len(resp.files),
            "generation_time_ms": resp.generation_time_ms,
            "provider": resp.provider,
        })

    return jsonify({"history": entries, "count": len(entries)}), 200
