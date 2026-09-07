"""FreshnessManager — time-aware knowledge management.

Knowledge must have time awareness.
Different information has different freshness requirements.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FreshnessInfo:
    """Freshness information for a piece of knowledge."""
    created_at: float = 0.0
    last_verified: float = 0.0
    freshness: str = "stable"  # stable, recent, current
    source_date: str = ""
    expires_at: float = 0.0
    is_expired: bool = False


class FreshnessManager:
    """Manages knowledge freshness and staleness.

    Uses structural patterns to determine freshness requirements.
    Does NOT hardcode individual topics.

    Freshness categories:
    - stable: rarely changes (definitions, historical facts)
    - recent: changes occasionally (technology, best practices)
    - current: changes frequently (prices, versions, news)
    """

    def __init__(self):
        # Freshness durations in seconds
        self.freshness_durations = {
            "current": 3600,      # 1 hour
            "recent": 86400,      # 1 day
            "stable": 2592000,    # 30 days
        }

    def get_freshness(self, created_at: float, last_verified: float,
                       freshness_type: str = "stable") -> FreshnessInfo:
        """Get freshness information for knowledge."""
        info = FreshnessInfo(
            created_at=created_at,
            last_verified=last_verified,
            freshness=freshness_type,
        )

        # Calculate expiration
        duration = self.freshness_durations.get(freshness_type, 2592000)
        info.expires_at = last_verified + duration
        info.is_expired = time.time() > info.expires_at

        return info

    def is_stale(self, last_verified: float, freshness_type: str = "stable") -> bool:
        """Check if knowledge is stale."""
        duration = self.freshness_durations.get(freshness_type, 2592000)
        return (time.time() - last_verified) > duration

    def should_reverify(self, question: str, last_verified: float,
                         freshness_type: str = "stable") -> bool:
        """Determine if knowledge should be re-verified based on question."""
        # Check if question asks for current information
        q_lower = question.lower()
        if any(w in q_lower for w in ["latest", "current", "today", "now"]):
            return self.is_stale(last_verified, "current")
        elif any(w in q_lower for w in ["recent", "new", "updated"]):
            return self.is_stale(last_verified, "recent")
        else:
            return self.is_stale(last_verified, freshness_type)

    def determine_freshness_requirement(self, question: str) -> str:
        """Determine freshness requirement from question structure."""
        q_lower = question.lower()

        # Current information indicators
        if any(w in q_lower for w in [
            "latest", "current", "today", "now", "price", "version",
            "2026", "2025", "this year", "this month"
        ]):
            return "current"

        # Recent information indicators
        if any(w in q_lower for w in [
            "recent", "new", "updated", "changed", "latest"
        ]):
            return "recent"

        # Default to stable
        return "stable"

    def get_freshness_label(self, freshness_type: str, language: str = "english") -> str:
        """Get a human-readable freshness label."""
        labels = {
            "current": {
                "english": "Current",
                "hindi": "वर्तमान",
                "hinglish": "Current",
            },
            "recent": {
                "english": "Recently updated",
                "hindi": "हाल ही में अपडेटेड",
                "hinglish": "Recently updated",
            },
            "stable": {
                "english": "Stable",
                "hindi": "स्थिर",
                "hinglish": "Stable",
            },
        }
        return labels.get(freshness_type, {}).get(language, freshness_type)
