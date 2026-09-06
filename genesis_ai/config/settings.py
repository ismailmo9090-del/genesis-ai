"""Genesis AI configuration settings."""

import os

DATABASE_PATH = os.environ.get("GENESIS_DB_PATH", "genesis_data.db")

UI_PORT = int(os.environ.get("GENESIS_UI_PORT", "8080"))

MAX_SEARCH_RESULTS = int(os.environ.get("GENESIS_MAX_SEARCH_RESULTS", "8"))

# Lowered so cached knowledge is only used when very confident
CONFIDENCE_THRESHOLD = float(os.environ.get("GENESIS_CONFIDENCE_THRESHOLD", "0.85"))

AUTONOMOUS_LEARNING_ENABLED = os.environ.get(
    "GENESIS_AUTONOMOUS_LEARNING", "false"
).lower() in ("true", "1", "yes")

MAX_LEARNING_SESSIONS_PER_DAY = int(
    os.environ.get("GENESIS_MAX_LEARNING_SESSIONS_PER_DAY", "10")
)

# Increased for active use — supports creative + factual queries
MAX_WEB_REQUESTS_PER_HOUR = int(
    os.environ.get("GENESIS_MAX_WEB_REQUESTS_PER_HOUR", "200")
)

PRIVACY_LEVEL = os.environ.get("GENESIS_PRIVACY_LEVEL", "high")

OFFLINE_MODE = os.environ.get("GENESIS_OFFLINE_MODE", "false").lower() in (
    "true",
    "1",
    "yes",
)

LOG_LEVEL = os.environ.get("GENESIS_LOG_LEVEL", "INFO")

MAX_TOKENS_PER_RESPONSE = int(os.environ.get("GENESIS_MAX_TOKENS", "4096"))

MEMORY_MAX_ENTRIES = int(os.environ.get("GENESIS_MEMORY_MAX_ENTRIES", "10000"))

CONTRADICTION_AUTO_RESOLVE = os.environ.get(
    "GENESIS_CONTRADICTION_AUTO_RESOLVE", "false"
).lower() in ("true", "1", "yes")

KNOWLEDGE_GRAPH_MAX_DEPTH = int(os.environ.get("GENESIS_KG_MAX_DEPTH", "3"))

CURIOUSITY_STRENGTH = float(os.environ.get("GENESIS_CURIOSITY_STRENGTH", "0.7"))

FEEDBACK_RETENTION_DAYS = int(os.environ.get("GENESIS_FEEDBACK_RETENTION", "90"))

MAX_CONCURRENT_REQUESTS = int(os.environ.get("GENESIS_MAX_CONCURRENT", "5"))

DEFAULT_LANGUAGE = os.environ.get("GENESIS_LANGUAGE", "en")

BACKUP_ENABLED = os.environ.get("GENESIS_BACKUP_ENABLED", "true").lower() in (
    "true",
    "1",
    "yes",
)

BACKUP_INTERVAL_HOURS = int(os.environ.get("GENESIS_BACKUP_INTERVAL", "24"))

DATA_DIR = os.environ.get("GENESIS_DATA_DIR", "genesis_data")
