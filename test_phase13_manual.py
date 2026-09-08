"""Test the response system fixes — Phase 13 manual API test."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os
os.environ["GENESIS_USE_LANGUAGE_ENGINE"] = "0"

import json
import time
import logging
logging.basicConfig(level=logging.WARNING)

from genesis_ai.main import GenesisAI

genesis = GenesisAI()
genesis.db.init_db()

print("=" * 70)
print("PHASE 13: MANUAL API TEST — BEFORE/AFTER PROOF")
print("=" * 70)

# Test cases: each is (query, expected_behavior)
test_cases = [
    # P0: Factual knowledge from learned_knowledge
    ("What is the capital of Bhutan?", "Should use learned knowledge"),
    ("What is quantum entanglement?", "Should attempt research or use knowledge"),
    
    # P0: Intent routing
    ("What is a young star?", "Should NOT be IDENTITY (young contains 'you')"),
    ("What are tumour cells?", "Should NOT be IDENTITY (tumour contains 'tum')"),
    ("Who is the best username?", "Should NOT be IDENTITY (username contains 'name')"),
    
    # P0: Identity questions (should still work)
    ("Who are you?", "Should be IDENTITY"),
    ("What is your name?", "Should be IDENTITY"),
    
    # P0: Greetings
    ("hello", "Should be CASUAL greeting"),
    ("how are you?", "Should be CASUAL greeting"),
    
    # P0: Factual questions
    ("what is photosynthesis?", "Should answer from knowledge or research"),
    ("explain gravity", "Should answer from knowledge or research"),
    
    # P0: Creative
    ("write a poem about rain", "Should handle creatively"),
    
    # P0: Code
    ("write Python code to reverse a string", "Should handle code"),
]

results = []
for query, expected in test_cases:
    time.sleep(1)
    try:
        result = genesis.chat("test_phase13", query)
        resp = result.get("response_text", "")
        intent = result.get("intent", "")
        goal = result.get("goal_type", "")
        confidence = result.get("confidence", 0)
        knowledge = result.get("knowledge_used", [])
        
        # Classify result
        is_garbage = any(g in resp.lower() for g in [
            "task involved", "analytic proposition", "about bhutan"
        ])
        is_empty = not resp or len(resp) < 20
        is_relevant = any(w in resp.lower() for w in query.lower().split()[:3])
        
        status = "OK" if not is_garbage and not is_empty else "FAIL"
        if "IDENTITY" in goal.upper() and "identity" not in expected.lower():
            status = "FAIL"
        
        results.append({
            "query": query,
            "expected": expected,
            "response": resp[:120],
            "intent": intent,
            "goal": goal,
            "confidence": confidence,
            "status": status,
        })
        
        icon = "✅" if status == "OK" else "❌"
        print(f"\n{icon} [{status}] Q: {query}")
        print(f"   Expected: {expected}")
        print(f"   Goal: {goal} | Intent: {intent} | Conf: {confidence:.2f}")
        print(f"   Response: {resp[:100]}...")
        
    except Exception as e:
        print(f"\n❌ [ERROR] Q: {query}")
        print(f"   Error: {e}")
        results.append({"query": query, "status": "ERROR", "error": str(e)})

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
ok = sum(1 for r in results if r.get("status") == "OK")
fail = sum(1 for r in results if r.get("status") == "FAIL")
error = sum(1 for r in results if r.get("status") == "ERROR")
print(f"Total: {len(results)} | OK: {ok} | FAIL: {fail} | ERROR: {error}")

# Save results
with open("phase13_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nResults saved to phase13_results.json")
