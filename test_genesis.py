import sys
import io
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'f:/Genesis AI')
from genesis_ai.main import GenesisAI

ai = GenesisAI()
ai.db.execute("DELETE FROM response_cache")

tests = [
    ('test1', 'shayari sunao'),
    ('test1', 'love shayari sunao'),
    ('test2', 'Salman Khan kaun hai'),
    ('test2', 'uski sabse top film kaun si hai'),
    ('test3', 'calculator banao'),
    ('test4', 'hello'),
    ('test4', 'kya haal hai'),
]

for user_id, msg in tests:
    print('\n' + '='*60)
    print('USER: ' + msg)
    print('='*60)
    r = ai.chat(user_id, msg)
    resp = r['response_text']
    intent = r['intent']
    print('INTENT: ' + intent)
    print('RESPONSE:')
    print(resp[:500])
    print()
