"""Investigate 'how are you' regression — run 5 times with fresh conversation IDs."""
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

# Run "how are you" 5 times with fresh conversation IDs
print("=== 'how are you' REGRESSION INVESTIGATION ===\n")
for i in range(5):
    conv_id = f"regression_test_{i}_{int(time.time())}"
    result = genesis.chat(conv_id, "how are you")
    resp = result.get("response_text", "")
    intent = result.get("intent", "")
    confidence = result.get("confidence", 0)
    knowledge_used = result.get("knowledge_used", [])
    
    print(f"Run {i+1}:")
    print(f"  Intent: {intent} | Confidence: {confidence:.2f}")
    print(f"  Response: {repr(resp[:150])}")
    print(f"  Knowledge used: {knowledge_used}")
    print()
    time.sleep(1)

# Also check what's in the knowledge base for greetings
print("\n=== CHECKING GREETING KNOWLEDGE IN DB ===")
try:
    rows = genesis.db.execute(
        "SELECT concept, claim, confidence, source FROM learned_knowledge WHERE concept LIKE '%greet%' OR claim LIKE '%how are you%' OR claim LIKE '%kaise ho%' LIMIT 10"
    ).fetchall()
    for row in rows:
        print(f"  Concept: {row[0]} | Claim: {row[1][:80]} | Conf: {row[2]:.2f} | Source: {row[3]}")
except Exception as e:
    print(f"  Error querying DB: {e}")

# Check intent patterns
print("\n=== CHECKING INTENT PATTERNS ===")
try:
    rows = genesis.db.execute(
        "SELECT pattern_text, intent, confidence FROM learned_intent_patterns WHERE intent LIKE '%greet%' OR pattern_text LIKE '%how%are%' LIMIT 10"
    ).fetchall()
    for row in rows:
        print(f"  Pattern: {row[0]} | Intent: {row[1]} | Conf: {row[2]:.2f}")
except Exception as e:
    print(f"  Error querying patterns: {e}")
