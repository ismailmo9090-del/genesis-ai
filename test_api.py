"""Test the Genesis AI Inference API components."""

from genesis_ai.database.db import DatabaseManager
from genesis_ai.api.auth import generate_api_key, _hash_key, create_api_key, validate_api_key, init_auth
from genesis_ai.api.rate_limit import RateLimiter
from genesis_ai.api.conversation import create_conversation, append_message, conversation_exists, init_conversation_manager
from genesis_ai.api.errors import error_response, success_response

def test_database():
    db = DatabaseManager()
    db.init_db()
    init_auth(db)
    init_conversation_manager(db)
    print("[OK] Database initialized")
    return db

def test_api_keys(db):
    raw, hsh, prefix = generate_api_key()
    assert raw.startswith("gen_"), "Key must start with gen_"
    assert len(hsh) == 64, "Hash must be 64 chars"
    print(f"[OK] Generated key: {raw[:20]}... prefix={prefix}")

    # Create API key in DB
    key_info = create_api_key(name="test", scopes=["chat", "evaluate"], rpm=10, rph=100)
    assert "key" in key_info
    assert key_info["name"] == "test"
    assert "chat" in key_info["scopes"]
    print(f"[OK] Created API key in DB: {key_info['key_prefix']}")

    # Validate key
    validated = validate_api_key(key_info["key"])
    assert validated is not None, "Key should validate"
    assert validated["key_prefix"] == key_info["key_prefix"]
    print(f"[OK] Validated API key")

    # Invalid key
    invalid = validate_api_key("gen_INVALID_KEY_123")
    assert invalid is None, "Invalid key should return None"
    print(f"[OK] Invalid key rejected")

def test_rate_limiter():
    rl = RateLimiter()

    # First request should not be limited
    limited, info = rl.is_rate_limited("test_user", rpm=5, rph=100)
    assert not limited, "First request should not be limited"
    print("[OK] First request: not limited")

    # Simulate hitting rate limit
    for _ in range(4):
        rl.is_rate_limited("test_user", rpm=5, rph=100)
    limited, info = rl.is_rate_limited("test_user", rpm=5, rph=100)
    assert limited, "Should be limited after 5 requests"
    assert info["window"] == "minute"
    print(f"[OK] Rate limited after 5 requests (retry_after={info['retry_after']}s)")

def test_conversations(db):
    conv_id = create_conversation(api_key_prefix="test_prefix", title="Test conversation")
    assert conv_id.startswith("gen_"), "Conv ID must start with gen_"
    print(f"[OK] Created conversation: {conv_id}")

    assert conversation_exists(conv_id), "Conversation should exist"
    print("[OK] Conversation exists")

    assert not conversation_exists("gen_NONEXISTENT"), "Non-existent conversation"
    print("[OK] Non-existent conversation correctly not found")

    append_message(conv_id, "user", "Hello")
    append_message(conv_id, "assistant", "Hi there!")
    print("[OK] Messages appended")

def test_error_responses():
    from flask import Flask
    app = Flask(__name__)
    with app.app_context():
        resp, status = error_response("TEST_ERROR", "This is a test", 400)
        assert status == 400
        data = resp.get_json()
        assert data["error"]["code"] == "TEST_ERROR"
        assert data["status"] == "error"
        print("[OK] Error response format correct")

        resp, status = success_response({"data": "test"}, request_id="req_test123")
        assert status == 200
        data = resp.get_json()
        assert data["request_id"] == "req_test123"
        assert data["status"] == "success"
        print("[OK] Success response format correct")

if __name__ == "__main__":
    print("=" * 50)
    print("Genesis AI Inference API - Component Tests")
    print("=" * 50)

    db = test_database()
    test_api_keys(db)
    test_rate_limiter()
    test_conversations(db)
    test_error_responses()

    print("=" * 50)
    print("ALL TESTS PASSED")
    print("=" * 50)
