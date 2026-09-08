"""Clean legacy garbage entries from learned_knowledge table."""
import sqlite3

conn = sqlite3.connect('genesis_data.db')
c = conn.cursor()

# Count before
c.execute('SELECT COUNT(*) FROM learned_knowledge')
before = c.fetchone()[0]

# Remove 'Task involved' entries
c.execute("DELETE FROM learned_knowledge WHERE claim LIKE 'Task involved %'")
task_involved = c.rowcount

# Remove web-sourced entries
c.execute("DELETE FROM learned_knowledge WHERE source LIKE 'http%' OR source LIKE 'www.%' OR source LIKE '%duckduckgo%' OR source LIKE '%web_research%'")
web_sourced = c.rowcount

# Remove 'general' concept entries with short claims
c.execute("DELETE FROM learned_knowledge WHERE concept = 'general' AND length(claim) < 50")
general_garbage = c.rowcount

# Count after
c.execute('SELECT COUNT(*) FROM learned_knowledge')
after = c.fetchone()[0]

conn.commit()
conn.close()

print(f'Before: {before} entries')
print(f'Removed: {task_involved} Task involved + {web_sourced} web-sourced + {general_garbage} general garbage')
print(f'After: {after} entries')
