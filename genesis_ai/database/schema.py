"""SQLite schema definitions and migrations for Genesis AI."""

SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    email TEXT,
    preferences TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT,
    summary TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    memory_type TEXT DEFAULT 'episodic',
    importance REAL DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    last_accessed TEXT,
    decay_rate REAL DEFAULT 0.01,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS concepts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    domain TEXT,
    definition TEXT,
    examples TEXT DEFAULT '[]',
    confidence REAL DEFAULT 0.5,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_concept_id INTEGER NOT NULL,
    target_concept_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL,
    strength REAL DEFAULT 0.5,
    evidence_count INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (source_concept_id) REFERENCES concepts(id) ON DELETE CASCADE,
    FOREIGN KEY (target_concept_id) REFERENCES concepts(id) ON DELETE CASCADE,
    UNIQUE(source_concept_id, target_concept_id, relation_type)
);

CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concept_id INTEGER NOT NULL,
    source_id INTEGER,
    claim TEXT NOT NULL,
    claim_type TEXT DEFAULT 'fact',
    confidence REAL DEFAULT 0.5,
    verification_status TEXT DEFAULT 'unverified',
    last_verified TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source_type TEXT DEFAULT 'web',
    url TEXT,
    reliability REAL DEFAULT 0.5,
    last_fetched TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id INTEGER NOT NULL,
    claim_text TEXT NOT NULL,
    claim_type TEXT DEFAULT 'fact',
    confidence REAL DEFAULT 0.5,
    supporting_evidence INTEGER DEFAULT 0,
    contradicting_evidence INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (knowledge_id) REFERENCES knowledge(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NOT NULL,
    source_id INTEGER,
    evidence_text TEXT NOT NULL,
    evidence_type TEXT DEFAULT 'supporting',
    strength REAL DEFAULT 0.5,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    skill_type TEXT DEFAULT 'general',
    proficiency REAL DEFAULT 0.0,
    usage_count INTEGER DEFAULT 0,
    last_used TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS skill_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id INTEGER NOT NULL,
    step_order INTEGER NOT NULL,
    action TEXT NOT NULL,
    description TEXT,
    expected_outcome TEXT,
    success_rate REAL DEFAULT 0.0,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS experiences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    skill_id INTEGER,
    task_description TEXT NOT NULL,
    outcome TEXT,
    success INTEGER DEFAULT 0,
    duration_ms INTEGER,
    error_message TEXT,
    lessons_learned TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    experience_id INTEGER,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    feedback_type TEXT DEFAULT 'general',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (experience_id) REFERENCES experiences(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS learning_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    session_type TEXT DEFAULT 'exploration',
    goals TEXT DEFAULT '[]',
    outcomes TEXT DEFAULT '[]',
    knowledge_gained TEXT DEFAULT '[]',
    duration_minutes INTEGER,
    status TEXT DEFAULT 'active',
    started_at TEXT DEFAULT (datetime('now')),
    ended_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS research_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    sources_checked INTEGER DEFAULT 0,
    findings TEXT DEFAULT '[]',
    confidence REAL DEFAULT 0.0,
    contradictions_found INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    started_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS contradictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_a_id INTEGER NOT NULL,
    claim_b_id INTEGER NOT NULL,
    contradiction_type TEXT DEFAULT 'direct',
    resolution TEXT,
    resolved INTEGER DEFAULT 0,
    detected_at TEXT DEFAULT (datetime('now')),
    resolved_at TEXT,
    FOREIGN KEY (claim_a_id) REFERENCES claims(id) ON DELETE CASCADE,
    FOREIGN KEY (claim_b_id) REFERENCES claims(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    task_type TEXT DEFAULT 'general',
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    assigned_to TEXT,
    due_date TEXT,
    result TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tool_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    conversation_id INTEGER,
    tool_name TEXT NOT NULL,
    input_data TEXT DEFAULT '{}',
    output_data TEXT DEFAULT '{}',
    success INTEGER DEFAULT 1,
    duration_ms INTEGER,
    error_message TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS curiosity_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    topic TEXT NOT NULL,
    priority REAL DEFAULT 0.5,
    reason TEXT,
    status TEXT DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    created_at TEXT DEFAULT (datetime('now')),
    processed_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);

CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key);
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);

CREATE INDEX IF NOT EXISTS idx_concepts_name ON concepts(name);
CREATE INDEX IF NOT EXISTS idx_concepts_domain ON concepts(domain);

CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_concept_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_concept_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relation_type);

CREATE INDEX IF NOT EXISTS idx_knowledge_concept ON knowledge(concept_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_source ON knowledge(source_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_status ON knowledge(verification_status);

CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(source_type);
CREATE INDEX IF NOT EXISTS idx_sources_reliability ON sources(reliability DESC);

CREATE INDEX IF NOT EXISTS idx_claims_knowledge ON claims(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(status);
CREATE INDEX IF NOT EXISTS idx_claims_type ON claims(claim_type);

CREATE INDEX IF NOT EXISTS idx_evidence_claim ON evidence(claim_id);
CREATE INDEX IF NOT EXISTS idx_evidence_source ON evidence(source_id);
CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence(evidence_type);

CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);
CREATE INDEX IF NOT EXISTS idx_skills_type ON skills(skill_type);
CREATE INDEX IF NOT EXISTS idx_skills_proficiency ON skills(proficiency DESC);

CREATE INDEX IF NOT EXISTS idx_skill_steps_skill ON skill_steps(skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_steps_order ON skill_steps(step_order);

CREATE INDEX IF NOT EXISTS idx_experiences_user ON experiences(user_id);
CREATE INDEX IF NOT EXISTS idx_experiences_skill ON experiences(skill_id);
CREATE INDEX IF NOT EXISTS idx_experiences_success ON experiences(success);

CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_experience ON feedback(experience_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating);

CREATE INDEX IF NOT EXISTS idx_learning_sessions_user ON learning_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_learning_sessions_status ON learning_sessions(status);

CREATE INDEX IF NOT EXISTS idx_research_sessions_user ON research_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_research_sessions_status ON research_sessions(status);

CREATE INDEX IF NOT EXISTS idx_contradictions_claim_a ON contradictions(claim_a_id);
CREATE INDEX IF NOT EXISTS idx_contradictions_claim_b ON contradictions(claim_b_id);
CREATE INDEX IF NOT EXISTS idx_contradictions_resolved ON contradictions(resolved);

CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(task_type);

CREATE INDEX IF NOT EXISTS idx_tool_usage_task ON tool_usage(task_id);
CREATE INDEX IF NOT EXISTS idx_tool_usage_conversation ON tool_usage(conversation_id);
CREATE INDEX IF NOT EXISTS idx_tool_usage_tool ON tool_usage(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_usage_success ON tool_usage(success);

CREATE INDEX IF NOT EXISTS idx_curiosity_queue_user ON curiosity_queue(user_id);
CREATE INDEX IF NOT EXISTS idx_curiosity_queue_status ON curiosity_queue(status);
CREATE INDEX IF NOT EXISTS idx_curiosity_queue_priority ON curiosity_queue(priority DESC);

CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status);
"""


def get_schema_version(conn):
    """Get current schema version from database."""
    try:
        cursor = conn.execute("SELECT value FROM schema_meta WHERE key = 'version'")
        row = cursor.fetchone()
        if row:
            return int(row[0])
    except Exception:
        pass
    return 0


def set_schema_version(conn, version):
    """Set schema version in database."""
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value, updated_at) VALUES ('version', ?, datetime('now'))",
        (str(version),),
    )
    conn.commit()


def run_migrations(conn):
    """Apply schema and indexes to the database. Idempotent."""
    current_version = get_schema_version(conn)

    if current_version < 1:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(INDEXES_SQL)

    if current_version < 2:
        from genesis_ai.database.migrations import run_v2_migration
        run_v2_migration(conn)

    if current_version < SCHEMA_VERSION:
        set_schema_version(conn, SCHEMA_VERSION)

    return SCHEMA_VERSION
