"""Database migrations for Genesis AI - upgraded architecture tables."""

MIGRATION_V2_SQL = """
-- 1. Understanding results cache
CREATE TABLE IF NOT EXISTS understanding_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_hash TEXT UNIQUE NOT NULL,
    understanding_json TEXT NOT NULL,
    created_at REAL NOT NULL
);

-- 2. Analysis results cache
CREATE TABLE IF NOT EXISTS analysis_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_hash TEXT UNIQUE NOT NULL,
    analysis_json TEXT NOT NULL,
    created_at REAL NOT NULL
);

-- 3. Event log
CREATE TABLE IF NOT EXISTS event_log (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    session_id TEXT NOT NULL,
    data TEXT,
    duration REAL DEFAULT 0.0,
    timestamp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_session ON event_log(session_id);
CREATE INDEX IF NOT EXISTS idx_event_type ON event_log(event_type);
CREATE INDEX IF NOT EXISTS idx_event_timestamp ON event_log(timestamp);

-- 4. Research cache
CREATE TABLE IF NOT EXISTS research_cache (
    cache_id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    results TEXT DEFAULT '[]',
    sources TEXT DEFAULT '[]',
    timestamp REAL NOT NULL,
    expiry REAL NOT NULL,
    hit_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_research_cache_query ON research_cache(query);

-- 5. Contradictions tracking (extended from existing contradictions table)
CREATE TABLE IF NOT EXISTS contradiction_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_a TEXT NOT NULL,
    claim_b TEXT NOT NULL,
    source_a TEXT,
    source_b TEXT,
    topic TEXT,
    severity TEXT DEFAULT 'medium',
    resolution TEXT DEFAULT 'unresolved',
    resolution_notes TEXT,
    created_at REAL NOT NULL
);

-- 6. Knowledge confidence tracking
CREATE TABLE IF NOT EXISTS knowledge_confidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id INTEGER,
    confidence REAL DEFAULT 0.5,
    source TEXT,
    evidence TEXT,
    usage_count INTEGER DEFAULT 0,
    last_verified REAL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY (knowledge_id) REFERENCES knowledge(id) ON DELETE CASCADE
);

-- 7. Task pipeline tracking
CREATE TABLE IF NOT EXISTS task_pipeline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    task_description TEXT NOT NULL,
    current_stage TEXT,
    stages_completed TEXT,
    understanding_json TEXT,
    analysis_json TEXT,
    plan_json TEXT,
    research_json TEXT,
    solution_json TEXT,
    critique_json TEXT,
    result TEXT,
    started_at REAL NOT NULL,
    completed_at REAL,
    total_duration REAL
);
CREATE INDEX IF NOT EXISTS idx_pipeline_session ON task_pipeline(session_id);

-- 8. Skill composition tracking
CREATE TABLE IF NOT EXISTS skill_compositions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    component_skills TEXT NOT NULL,
    result_skill_id INTEGER,
    created_at REAL NOT NULL,
    FOREIGN KEY (result_skill_id) REFERENCES skills(id) ON DELETE SET NULL
);

-- Extend experiences table with new columns
ALTER TABLE experiences ADD COLUMN approach TEXT;
ALTER TABLE experiences ADD COLUMN knowledge_used TEXT;
ALTER TABLE experiences ADD COLUMN research_used TEXT;
ALTER TABLE experiences ADD COLUMN lessons TEXT;
ALTER TABLE experiences ADD COLUMN duration REAL;
"""


def run_v2_migration(conn):
    """Apply migration v2: upgraded architecture tables."""
    conn.executescript(MIGRATION_V2_SQL)
