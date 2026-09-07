"""Phase 0 verification test script - round 2."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from genesis_ai.main import GenesisAI
import time

genesis = GenesisAI()
genesis.db.init_db()

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
