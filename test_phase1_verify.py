"""Phase 1 verification - test with LM enabled."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os
os.environ["GENESIS_USE_LANGUAGE_ENGINE"] = "1"

from genesis_ai.main import GenesisAI
import time

print("Loading Genesis with language engine enabled...")
genesis = GenesisAI()
genesis.db.init_db()

# First, trigger LM loading
print("Pre-loading language model...")
from genesis_ai.research.response.language_engine import LanguageEngine
engine = LanguageEngine()
print(f"LM loaded: {engine.is_model_loaded()}")
if engine.get_model_info().get("error"):
    print(f"LM error: {engine.get_model_info()['error']}")

queries = [
    'why do magnets attract metal?',
    'how does a thermometer measure temperature?',
    'what is photosynthesis?',
    'what is the difference between solar and wind energy?',
    'biryani kaise banti hai?',
    'what is DNA?',
]

for q in queries:
    print(f'\n=== QUERY: {q} ===')
    try:
        result = genesis.chat('test_user', q)
        resp = result.get('response_text', '')
        intent = result.get('intent', '')
        confidence = result.get('confidence', 0)
        print(f'Response ({len(resp)} chars): {resp[:600]}')
        print(f'Intent: {intent} | Confidence: {confidence:.2f}')
    except Exception as e:
        print(f'ERROR: {e}')
    time.sleep(1)
    print()
