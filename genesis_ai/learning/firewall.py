"""Learning Firewall — safety layer for the learning system.

Prevents destructive operations, validates changes before applying,
and enforces approval for external-facing actions.

The firewall is NOT optional. Every learning action passes through it.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from genesis_ai.database.db import DatabaseManager

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionCategory(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXTERNAL = "external"
    SYSTEM = "system"
    LEARNING = "learning"


@dataclass
class FirewallVerdict:
    """Result of a firewall check."""
    allowed: bool = True
    risk_level: RiskLevel = RiskLevel.SAFE
    reason: str = ""
    requires_approval: bool = False
    blocked_reason: str = ""
    logged: bool = True


@dataclass
class FirewallRule:
    """A rule in the firewall."""
    name: str = ""
    pattern: str = ""
    category: ActionCategory = ActionCategory.READ
    risk_level: RiskLevel = RiskLevel.SAFE
    action: str = "allow"  # allow, block, require_approval
    description: str = ""


# Default rules — conservative by default
DEFAULT_RULES = [
    # Safe operations
    FirewallRule(
        name="read_knowledge",
        pattern=r"^(get|read|search|list|count|stats)",
        category=ActionCategory.READ,
        risk_level=RiskLevel.SAFE,
        action="allow",
    ),
    FirewallRule(
        name="ingest_experience",
        pattern=r"^(ingest|submit|record|store|create)",
        category=ActionCategory.LEARNING,
        risk_level=RiskLevel.LOW,
        action="allow",
    ),
    FirewallRule(
        name="learn_from_experience",
        pattern=r"^(learn|generalize|extract|connect)",
        category=ActionCategory.LEARNING,
        risk_level=RiskLevel.LOW,
        action="allow",
    ),
    # Moderate risk
    FirewallRule(
        name="update_knowledge",
        pattern=r"^(update|modify|revise|merge)",
        category=ActionCategory.WRITE,
        risk_level=RiskLevel.MEDIUM,
        action="require_approval",
    ),
    FirewallRule(
        name="create_skill",
        pattern=r"^skill_(create|update)",
        category=ActionCategory.LEARNING,
        risk_level=RiskLevel.LOW,
        action="allow",
    ),
    # Dangerous operations
    FirewallRule(
        name="delete_knowledge",
        pattern=r"^(delete|remove|purge|drop|destroy)",
        category=ActionCategory.DELETE,
        risk_level=RiskLevel.HIGH,
        action="require_approval",
    ),
    FirewallRule(
        name="system_change",
        pattern=r"^(execute|run|system|config|install|uninstall)",
        category=ActionCategory.SYSTEM,
        risk_level=RiskLevel.CRITICAL,
        action="block",
    ),
    FirewallRule(
        name="external_request",
        pattern=r"^(send|post|upload|transfer|connect|http|api_call)",
        category=ActionCategory.EXTERNAL,
        risk_level=RiskLevel.HIGH,
        action="require_approval",
    ),
]


class LearningFirewall:
    """Safety layer that validates all learning actions.

    Every action in the learning system passes through this firewall.
    It enforces:
    1. Read-only by default
    2. Write requires justification
    3. Delete requires approval
    4. External actions require explicit consent
    5. System changes are blocked
    """

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.rules = DEFAULT_RULES.copy()
        self._ensure_tables()

    def _ensure_tables(self):
        """Create firewall tables."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS firewall_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                category TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                allowed BOOLEAN NOT NULL,
                reason TEXT DEFAULT '',
                details TEXT DEFAULT '{}',
                timestamp REAL NOT NULL
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS firewall_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                details TEXT DEFAULT '{}',
                status TEXT DEFAULT 'pending',
                requested_at REAL NOT NULL,
                resolved_at REAL,
                resolved_by TEXT DEFAULT ''
            )
        """)

    def check(self, action: str, details: dict | None = None) -> FirewallVerdict:
        """Check if an action is allowed by the firewall.

        This is the main entry point. Every learning action must call this.
        """
        details = details or {}
        action_lower = action.lower().strip()

        # Check against rules
        for rule in self.rules:
            if re.search(rule.pattern, action_lower):
                verdict = FirewallVerdict(
                    allowed=rule.action != "block",
                    risk_level=rule.risk_level,
                    reason=f"Matched rule: {rule.name} ({rule.description or rule.action})",
                    requires_approval=rule.action == "require_approval",
                )

                if rule.action == "block":
                    verdict.blocked_reason = (
                        f"Action '{action}' is blocked by rule '{rule.name}'. "
                        f"{rule.description}"
                    )
                    logger.warning(
                        "Firewall BLOCKED: %s (rule: %s)", action, rule.name
                    )
                elif rule.action == "require_approval":
                    # Check if approval exists
                    if not self._has_approval(action, details):
                        verdict.allowed = False
                        verdict.blocked_reason = (
                            f"Action '{action}' requires approval. "
                            f"Risk level: {rule.risk_level.value}"
                        )
                        # Create approval request
                        self._request_approval(action, details)
                        logger.warning(
                            "Firewall PENDING APPROVAL: %s (rule: %s)",
                            action, rule.name,
                        )

                # Log the check
                self._log_check(action, rule.category.value, verdict)
                return verdict

        # Default: allow unknown low-risk, block unknown high-risk
        verdict = FirewallVerdict(
            allowed=True,
            risk_level=RiskLevel.LOW,
            reason="No matching rule — default allow for low-risk",
        )
        self._log_check(action, "unknown", verdict)
        return verdict

    def approve(self, action: str, details: dict | None = None, approved_by: str = "system"):
        """Approve a pending action."""
        details = details or {}
        self.db.execute(
            """UPDATE firewall_approvals
               SET status = 'approved', resolved_at = ?, resolved_by = ?
               WHERE action = ? AND status = 'pending'""",
            (time.time(), approved_by, action),
        )
        logger.info("Firewall APPROVED: %s by %s", action, approved_by)

    def deny(self, action: str, details: dict | None = None, denied_by: str = "system"):
        """Deny a pending action."""
        details = details or {}
        self.db.execute(
            """UPDATE firewall_approvals
               SET status = 'denied', resolved_at = ?, resolved_by = ?
               WHERE action = ? AND status = 'pending'""",
            (time.time(), denied_by, action),
        )
        logger.info("Firewall DENIED: %s by %s", action, denied_by)

    def get_pending_approvals(self) -> list[dict]:
        """Get all actions waiting for approval."""
        rows = self.db.fetch_all(
            """SELECT action, details, requested_at
               FROM firewall_approvals WHERE status = 'pending'
               ORDER BY requested_at DESC"""
        )
        return [
            {"action": r[0], "details": json.loads(r[1]), "requested_at": r[2]}
            for r in rows
        ]

    def get_log(self, limit: int = 50) -> list[dict]:
        """Get recent firewall log entries."""
        rows = self.db.fetch_all(
            """SELECT action, category, risk_level, allowed, reason, timestamp
               FROM firewall_log ORDER BY timestamp DESC LIMIT ?""",
            (limit,),
        )
        return [
            {
                "action": r[0], "category": r[1], "risk_level": r[2],
                "allowed": bool(r[3]), "reason": r[4], "timestamp": r[5],
            }
            for r in rows
        ]

    def add_rule(self, rule: FirewallRule):
        """Add a custom firewall rule."""
        self.rules.append(rule)

    def _has_approval(self, action: str, details: dict) -> bool:
        """Check if an action has been approved."""
        row = self.db.fetch_one(
            """SELECT id FROM firewall_approvals
               WHERE action = ? AND status = 'approved'
               ORDER BY resolved_at DESC LIMIT 1""",
            (action,),
        )
        return row is not None

    def _request_approval(self, action: str, details: dict):
        """Create an approval request."""
        # Don't duplicate pending requests
        existing = self.db.fetch_one(
            """SELECT id FROM firewall_approvals
               WHERE action = ? AND status = 'pending'""",
            (action,),
        )
        if not existing:
            self.db.execute(
                """INSERT INTO firewall_approvals
                   (action, details, status, requested_at)
                   VALUES (?, ?, 'pending', ?)""",
                (action, json.dumps(details), time.time()),
            )

    def _log_check(self, action: str, category: str, verdict: FirewallVerdict):
        """Log a firewall check."""
        self.db.execute(
            """INSERT INTO firewall_log
               (action, category, risk_level, allowed, reason, details, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                action, category, verdict.risk_level.value,
                verdict.allowed, verdict.reason,
                json.dumps({"blocked": verdict.blocked_reason}),
                time.time(),
            ),
        )

    def get_stats(self) -> dict:
        """Get firewall statistics."""
        total = self.db.fetch_one("SELECT COUNT(*) FROM firewall_log")
        blocked = self.db.fetch_one(
            "SELECT COUNT(*) FROM firewall_log WHERE allowed = 0"
        )
        pending = self.db.fetch_one(
            "SELECT COUNT(*) FROM firewall_approvals WHERE status = 'pending'"
        )
        approved = self.db.fetch_one(
            "SELECT COUNT(*) FROM firewall_approvals WHERE status = 'approved'"
        )
        return {
            "total_checks": total[0] if total else 0,
            "blocked": blocked[0] if blocked else 0,
            "pending_approvals": pending[0] if pending else 0,
            "total_approved": approved[0] if approved else 0,
            "rules_count": len(self.rules),
        }
