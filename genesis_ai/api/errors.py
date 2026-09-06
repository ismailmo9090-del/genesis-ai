"""Standardized API error responses."""

import uuid
from flask import jsonify


def error_response(code: str, message: str, status_code: int = 400, request_id: str = None) -> tuple:
    """Return a machine-readable error response."""
    if not request_id:
        request_id = f"req_{uuid.uuid4().hex[:12]}"
    return jsonify({
        "error": {
            "code": code,
            "message": message,
        },
        "request_id": request_id,
        "status": "error",
    }), status_code


def success_response(data: dict, request_id: str = None) -> tuple:
    """Return a standardized success response."""
    if not request_id:
        request_id = f"req_{uuid.uuid4().hex[:12]}"
    data["request_id"] = request_id
    data["status"] = "success"
    return jsonify(data), 200
