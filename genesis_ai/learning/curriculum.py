"""Curriculum Engine — adaptive difficulty and learning progression.

Tracks skill level per domain, adapts difficulty based on performance,
and suggests what to learn next.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from genesis_ai.database.db import DatabaseManager

logger = logging.getLogger(__name__)


class Level(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


# Level thresholds based on cumulative success score
LEVEL_THRESHOLDS = {
    Level.BEGINNER: 0,
    Level.INTERMEDIATE: 10,
    Level.ADVANCED: 30,
    Level.EXPERT: 60,
}

LEVEL_ORDER = [Level.BEGINNER, Level.INTERMEDIATE, Level.ADVANCED, Level.EXPERT]


@dataclass
class SkillProfile:
    """Tracks skill level and history for a domain."""
    domain: str = "general"
    level: Level = Level.BEGINNER
    success_score: float = 0.0
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    streak: int = 0
    best_streak: int = 0
    last_task_time: float = 0.0
    history: list[dict] = field(default_factory=list)


@dataclass
class CurriculumRecommendation:
    """What to learn next."""
    domain: str = ""
    current_level: Level = Level.BEGINNER
    recommended_tasks: list[dict] = field(default_factory=list)
    reason: str = ""
    difficulty: str = "moderate"
    estimated_time_minutes: int = 0


class CurriculumEngine:
    """Adaptive curriculum that tracks skill progression and suggests next tasks.

    NOT a hardcoded difficulty ladder. Adapts based on actual performance:
    - Success increases difficulty
    - Failure decreases difficulty
    - Streaks unlock advanced topics
    - Struggles provide easier practice
    """

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._ensure_tables()

    def _ensure_tables(self):
        """Create curriculum tracking tables."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS skill_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                user_id TEXT DEFAULT 'default',
                level TEXT DEFAULT 'beginner',
                success_score REAL DEFAULT 0.0,
                total_tasks INTEGER DEFAULT 0,
                successful_tasks INTEGER DEFAULT 0,
                failed_tasks INTEGER DEFAULT 0,
                streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                last_task_time REAL DEFAULT 0.0,
                history TEXT DEFAULT '[]',
                updated_at REAL NOT NULL,
                UNIQUE(domain, user_id)
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS curriculum_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                level TEXT NOT NULL,
                task_type TEXT NOT NULL,
                description TEXT NOT NULL,
                prerequisites TEXT DEFAULT '[]',
                skills_tested TEXT DEFAULT '[]',
                difficulty REAL DEFAULT 0.5,
                estimated_minutes INTEGER DEFAULT 5,
                created_at REAL NOT NULL
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS task_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                level TEXT NOT NULL,
                task_type TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                duration REAL DEFAULT 0.0,
                errors TEXT DEFAULT '[]',
                lessons TEXT DEFAULT '[]',
                timestamp REAL NOT NULL
            )
        """)

    def get_profile(self, domain: str, user_id: str = "default") -> SkillProfile:
        """Get skill profile for a domain."""
        row = self.db.fetch_one(
            """SELECT domain, level, success_score, total_tasks,
                      successful_tasks, failed_tasks, streak, best_streak,
                      last_task_time, history
               FROM skill_profiles WHERE domain = ? AND user_id = ?""",
            (domain, user_id),
        )
        if row:
            return SkillProfile(
                domain=row[0],
                level=Level(row[1]),
                success_score=row[2],
                total_tasks=row[3],
                successful_tasks=row[4],
                failed_tasks=row[5],
                streak=row[6],
                best_streak=row[7],
                last_task_time=row[8],
                history=json.loads(row[9]) if row[9] else [],
            )
        return SkillProfile(domain=domain)

    def record_task(
        self,
        domain: str,
        success: bool,
        task_type: str = "general",
        duration: float = 0.0,
        errors: list[str] | None = None,
        lessons: list[str] | None = None,
        user_id: str = "default",
    ) -> SkillProfile:
        """Record a task outcome and update skill profile.

        This is the core learning loop input. Every task outcome
        adjusts the skill level dynamically.
        """
        profile = self.get_profile(domain, user_id)

        # Update counters
        profile.total_tasks += 1
        if success:
            profile.successful_tasks += 1
            profile.streak += 1
            profile.best_streak = max(profile.best_streak, profile.streak)
            # Score: +1 for success, +0.5 bonus for streaks
            bonus = min(profile.streak * 0.1, 0.5)
            profile.success_score += 1.0 + bonus
        else:
            profile.failed_tasks += 1
            profile.streak = 0
            # Penalty for failure: -0.5
            profile.success_score = max(0.0, profile.success_score - 0.5)

        profile.last_task_time = time.time()

        # Record in history (keep last 20)
        profile.history.append({
            "task_type": task_type,
            "success": success,
            "duration": duration,
            "timestamp": time.time(),
        })
        profile.history = profile.history[-20:]

        # Determine new level
        new_level = self._calculate_level(profile)
        level_changed = new_level != profile.level
        profile.level = new_level

        # Persist
        self._save_profile(profile, user_id)

        # Record outcome
        self.db.execute(
            """INSERT INTO task_outcomes
               (domain, level, task_type, success, duration, errors, lessons, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                domain, profile.level.value, task_type, success, duration,
                json.dumps(errors or []), json.dumps(lessons or []), time.time(),
            ),
        )

        if level_changed:
            logger.info(
                "Level changed for %s: %s → %s (score: %.1f)",
                domain, "beginner" if new_level == Level.BEGINNER else profile.level.value,
                new_level.value, profile.success_score,
            )

        return profile

    def _calculate_level(self, profile: SkillProfile) -> Level:
        """Calculate level based on success score and consistency."""
        score = profile.success_score
        total = profile.total_tasks
        if total < 3:
            return Level.BEGINNER

        success_rate = profile.successful_tasks / total

        # Need minimum success rate to advance
        if success_rate < 0.4 and score > 5:
            # Too many failures — stay or regress
            for level in reversed(LEVEL_ORDER):
                if score >= LEVEL_THRESHOLDS[level]:
                    return level
            return Level.BEGINNER

        # Check streak requirements
        if profile.streak >= 5 and profile.level == Level.INTERMEDIATE:
            # Bonus for sustained performance
            score += 2

        for level in reversed(LEVEL_ORDER):
            if score >= LEVEL_THRESHOLDS[level]:
                return level

        return Level.BEGINNER

    def _save_profile(self, profile: SkillProfile, user_id: str = "default"):
        """Persist skill profile to database."""
        self.db.execute(
            """INSERT OR REPLACE INTO skill_profiles
               (domain, user_id, level, success_score, total_tasks,
                successful_tasks, failed_tasks, streak, best_streak,
                last_task_time, history, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile.domain, user_id, profile.level.value,
                profile.success_score, profile.total_tasks,
                profile.successful_tasks, profile.failed_tasks,
                profile.streak, profile.best_streak,
                profile.last_task_time, json.dumps(profile.history),
                time.time(),
            ),
        )

    def recommend(self, domain: str, user_id: str = "default") -> CurriculumRecommendation:
        """Recommend what to learn next based on current skill level.

        Returns appropriate difficulty tasks for the domain.
        """
        profile = self.get_profile(domain, user_id)

        # Determine recommended difficulty based on level
        difficulty_map = {
            Level.BEGINNER: ("easy", "Foundational concepts"),
            Level.INTERMEDIATE: ("moderate", "Building on basics"),
            Level.ADVANCED: ("hard", "Advanced techniques"),
            Level.EXPERT: ("expert", "Mastery and innovation"),
        }
        difficulty, reason = difficulty_map[profile.level]

        # Suggest tasks based on performance
        tasks = []

        if profile.failed_tasks > profile.successful_tasks and profile.total_tasks > 3:
            # Struggling — recommend easier practice
            tasks.append({
                "type": "practice",
                "description": f"Practice basic {domain} concepts",
                "difficulty": "easy",
                "estimated_minutes": 10,
            })
            reason = "Struggling — reinforce basics before advancing"
        elif profile.streak >= 3:
            # On a streak — push harder
            tasks.append({
                "type": "challenge",
                "description": f"Tackle advanced {domain} challenge",
                "difficulty": "hard",
                "estimated_minutes": 20,
            })
            reason = f"On a {profile.streak}-task streak — ready for challenge"
        elif profile.total_tasks == 0:
            # New domain — start with overview
            tasks.append({
                "type": "introduction",
                "description": f"Introduction to {domain}",
                "difficulty": "easy",
                "estimated_minutes": 15,
            })
            reason = "New domain — start with fundamentals"
        else:
            # Normal progression
            tasks.append({
                "type": "learning",
                "description": f"Learn next {domain} concept",
                "difficulty": difficulty,
                "estimated_minutes": 15,
            })

        # Add review if there are failures
        if profile.failed_tasks > 0:
            tasks.append({
                "type": "review",
                "description": f"Review failed {domain} tasks",
                "difficulty": "easy",
                "estimated_minutes": 10,
            })

        return CurriculumRecommendation(
            domain=domain,
            current_level=profile.level,
            recommended_tasks=tasks,
            reason=reason,
            difficulty=difficulty,
            estimated_time_minutes=sum(t["estimated_minutes"] for t in tasks),
        )

    def get_all_profiles(self, user_id: str = "default") -> list[SkillProfile]:
        """Get all skill profiles for a user."""
        rows = self.db.fetch_all(
            """SELECT domain, level, success_score, total_tasks,
                      successful_tasks, failed_tasks, streak, best_streak,
                      last_task_time, history
               FROM skill_profiles WHERE user_id = ?
               ORDER BY success_score DESC""",
            (user_id,),
        )
        return [
            SkillProfile(
                domain=r[0], level=Level(r[1]), success_score=r[2],
                total_tasks=r[3], successful_tasks=r[4], failed_tasks=r[5],
                streak=r[6], best_streak=r[7], last_task_time=r[8],
                history=json.loads(r[9]) if r[9] else [],
            )
            for r in rows
        ]

    def get_domain_stats(self, domain: str, user_id: str = "default") -> dict:
        """Get detailed stats for a domain."""
        profile = self.get_profile(domain, user_id)
        outcomes = self.db.fetch_all(
            """SELECT success, COUNT(*), AVG(duration) FROM task_outcomes
               WHERE domain = ? GROUP BY success""",
            (domain,),
        )
        stats = {"success": 0, "failure": 0, "avg_duration": 0.0}
        for row in outcomes:
            if row[0]:
                stats["success"] = row[1]
                stats["avg_duration"] = row[2] or 0.0
            else:
                stats["failure"] = row[1]

        return {
            "profile": {
                "level": profile.level.value,
                "score": profile.success_score,
                "total": profile.total_tasks,
                "success_rate": (profile.successful_tasks / profile.total_tasks * 100)
                if profile.total_tasks > 0 else 0,
                "streak": profile.streak,
                "best_streak": profile.best_streak,
            },
            "outcomes": stats,
            "recommendation": self.recommend(domain, user_id).__dict__,
        }

    def reset_domain(self, domain: str, user_id: str = "default"):
        """Reset progress for a domain (use with caution)."""
        self.db.execute(
            "DELETE FROM skill_profiles WHERE domain = ? AND user_id = ?",
            (domain, user_id),
        )
        self.db.execute(
            "DELETE FROM task_outcomes WHERE domain = ?",
            (domain,),
        )
