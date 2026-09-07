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


MIGRATION_V3_SQL = """
-- API Keys table
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT UNIQUE NOT NULL,
    key_prefix TEXT NOT NULL,
    name TEXT,
    scopes TEXT DEFAULT '["chat"]',
    requests_per_minute INTEGER DEFAULT 30,
    requests_per_hour INTEGER DEFAULT 500,
    is_active INTEGER DEFAULT 1,
    created_at REAL,
    last_used_at REAL
);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active);

-- API request logs
CREATE TABLE IF NOT EXISTS api_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    api_key_prefix TEXT,
    endpoint TEXT,
    method TEXT,
    status_code INTEGER,
    latency_ms REAL,
    conversation_id TEXT,
    error_code TEXT,
    created_at REAL
);
CREATE INDEX IF NOT EXISTS idx_api_logs_request ON api_logs(request_id);
CREATE INDEX IF NOT EXISTS idx_api_logs_key ON api_logs(api_key_prefix);
CREATE INDEX IF NOT EXISTS idx_api_logs_endpoint ON api_logs(endpoint);
CREATE INDEX IF NOT EXISTS idx_api_logs_created ON api_logs(created_at);

-- API conversations (persistent conversation tracking)
CREATE TABLE IF NOT EXISTS api_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT UNIQUE NOT NULL,
    api_key_prefix TEXT,
    title TEXT,
    created_at REAL,
    updated_at REAL,
    message_count INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_api_conv_id ON api_conversations(conversation_id);
CREATE INDEX IF NOT EXISTS idx_api_conv_key ON api_conversations(api_key_prefix);
"""


def run_v3_migration(conn):
    """Apply migration v3: API infrastructure tables."""
    conn.executescript(MIGRATION_V3_SQL)


MIGRATION_V4_SQL = """
-- Learned intent patterns (Learning → Inference Bridge)
CREATE TABLE IF NOT EXISTS learned_intent_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_text TEXT NOT NULL,
    intent TEXT NOT NULL,
    concept TEXT DEFAULT '',
    conditions TEXT DEFAULT '[]',
    positive_examples TEXT DEFAULT '[]',
    negative_examples TEXT DEFAULT '[]',
    confidence REAL DEFAULT 0.5,
    status TEXT DEFAULT 'ACTIVE',
    source TEXT DEFAULT 'experience',
    created_at REAL NOT NULL,
    last_used REAL,
    use_count INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_lip_intent ON learned_intent_patterns(intent);
CREATE INDEX IF NOT EXISTS idx_lip_status ON learned_intent_patterns(status);
CREATE INDEX IF NOT EXISTS idx_lip_confidence ON learned_intent_patterns(confidence);

-- Intent inference outcomes (feedback loop)
CREATE TABLE IF NOT EXISTS intent_inference_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    message TEXT NOT NULL,
    classified_intent TEXT NOT NULL,
    learned_intent TEXT,
    final_intent TEXT NOT NULL,
    response_text TEXT,
    outcome TEXT DEFAULT 'pending',
    user_feedback TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_iio_session ON intent_inference_outcomes(session_id);
"""


def run_v4_migration(conn):
    """Apply migration v4: Learning → Inference Bridge tables."""
    conn.executescript(MIGRATION_V4_SQL)
