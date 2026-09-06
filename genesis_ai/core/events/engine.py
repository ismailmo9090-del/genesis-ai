"""Event log engine that records pipeline stage transitions with timing data."""

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from genesis_ai.database.db import DatabaseManager


@dataclass
class Event:
    """A single recorded event representing a pipeline stage transition."""

    event_id: str
    event_type: str
    timestamp: float
    data: Dict = field(default_factory=dict)
    session_id: str = ""
    duration: float = 0.0


class EventLog:
    """Records and queries pipeline events with timing and performance analysis.

    Supported event types:
        USER_INPUT, UNDERSTANDING_START, UNDERSTANDING_COMPLETE,
        ANALYSIS_START, ANALYSIS_COMPLETE, PLAN_CREATED, MEMORY_SEARCH,
        KNOWLEDGE_GAP_FOUND, SEARCH_STARTED, SOURCE_FOUND, EVIDENCE_EXTRACTED,
        COMPARISON_COMPLETE, CONTRADICTION_FOUND, REASONING_COMPLETE,
        SELF_CRITIQUE, SOLUTION_CREATED, TESTING_START, TESTING_COMPLETE,
        LEARNING_START, LEARNING_COMPLETE, MEMORY_UPDATED, ANSWER_READY
    """

    VALID_EVENT_TYPES = frozenset({
        "USER_INPUT",
        "UNDERSTANDING_START", "UNDERSTANDING_COMPLETE",
        "ANALYSIS_START", "ANALYSIS_COMPLETE",
        "PLAN_CREATED",
        "MEMORY_SEARCH",
        "KNOWLEDGE_GAP_FOUND",
        "SEARCH_STARTED", "SOURCE_FOUND", "EVIDENCE_EXTRACTED",
        "COMPARISON_COMPLETE",
        "CONTRADICTION_FOUND",
        "REASONING_COMPLETE",
        "SELF_CRITIQUE",
        "VERIFICATION_COMPLETE",
        "SOLUTION_CREATED",
        "TESTING_START", "TESTING_COMPLETE",
        "LEARNING_START", "LEARNING_COMPLETE",
        "EXPERIENCE_STORED",
        "MEMORY_UPDATED",
        "ANSWER_READY",
    })

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.session_events: List[Event] = []
        self._ensure_tables()

    def _ensure_tables(self):
        """Create the event_log table if it does not exist."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS event_log (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                timestamp REAL NOT NULL,
                data TEXT DEFAULT '{}',
                session_id TEXT DEFAULT '',
                duration REAL DEFAULT 0.0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_log_session ON event_log(session_id)
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_log_type ON event_log(event_type)
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_log_timestamp ON event_log(timestamp DESC)
        """)

    def _row_to_event(self, row) -> Event:
        """Convert a database row into an Event dataclass."""
        try:
            row_dict = dict(zip([d[0] for d in row.cursor.description], row)) if hasattr(row, 'cursor') else {}
        except Exception:
            row_dict = {}
        if not row_dict:
            row_dict = {col: row[i] for i, col in enumerate(["id", "event_id", "event_type", "session_id", "data", "duration", "timestamp"])}
        return Event(
            event_id=row_dict.get("event_id", ""),
            event_type=row_dict.get("event_type", ""),
            timestamp=row_dict.get("timestamp", 0.0),
            data=json.loads(row_dict.get("data", "{}")) if row_dict.get("data") else {},
            session_id=row_dict.get("session_id", ""),
            duration=row_dict.get("duration", 0.0),
        )

    def log_event(
        self,
        event_type: str,
        data: dict,
        session_id: str,
        duration: float = 0.0,
    ) -> str:
        """Record a new event in the log.

        Args:
            event_type: One of the supported event type strings.
            data: Arbitrary JSON-serialisable payload for this event.
            session_id: The session this event belongs to.
            duration: How long the stage took in seconds (0 if instantaneous).

        Returns:
            The generated event_id.

        Raises:
            ValueError: If event_type is not a recognised type.
        """
        if event_type not in self.VALID_EVENT_TYPES:
            raise ValueError(
                f"Invalid event_type: {event_type}. Must be one of {sorted(self.VALID_EVENT_TYPES)}"
            )
        event_id = str(uuid.uuid4())[:12]
        now = time.time()
        self.db.execute(
            """INSERT INTO event_log (event_id, event_type, timestamp, data, session_id, duration)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event_id, event_type, now, json.dumps(data), session_id, duration),
        )
        event = Event(
            event_id=event_id,
            event_type=event_type,
            timestamp=now,
            data=data,
            session_id=session_id,
            duration=duration,
        )
        self.session_events.append(event)
        return event_id

    def get_session_events(self, session_id: str) -> List[Event]:
        """Return all events for a given session, ordered by timestamp ascending.

        Args:
            session_id: The session to query.

        Returns:
            List of Event objects.
        """
        rows = self.db.fetch_all(
            "SELECT * FROM event_log WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,),
        )
        return [self._row_to_event(row) for row in rows]

    def get_events_by_type(self, event_type: str, limit: int = 100) -> List[Event]:
        """Return events of a specific type, most recent first.

        Args:
            event_type: The event type to filter on.
            limit: Maximum number of results.

        Returns:
            List of Event objects.
        """
        rows = self.db.fetch_all(
            "SELECT * FROM event_log WHERE event_type = ? ORDER BY timestamp DESC LIMIT ?",
            (event_type, limit),
        )
        return [self._row_to_event(row) for row in rows]

    def get_performance_stats(self, session_id: str = None) -> Dict:
        """Calculate aggregate performance statistics.

        If session_id is provided, stats are scoped to that session only.
        Otherwise they cover all recorded events.

        Returns a dict with keys:
            total_events, total_duration, average_duration,
            events_by_type, slowest_events
        """
        if session_id:
            rows = self.db.fetch_all(
                "SELECT event_type, duration FROM event_log WHERE session_id = ?",
                (session_id,),
            )
        else:
            rows = self.db.fetch_all(
                "SELECT event_type, duration FROM event_log"
            )

        if not rows:
            return {
                "total_events": 0,
                "total_duration": 0.0,
                "average_duration": 0.0,
                "events_by_type": {},
                "slowest_events": [],
            }

        total_duration = sum(r[1] for r in rows)
        events_by_type: Dict[str, Dict] = {}
        for event_type, duration in rows:
            if event_type not in events_by_type:
                events_by_type[event_type] = {"count": 0, "total_duration": 0.0}
            events_by_type[event_type]["count"] += 1
            events_by_type[event_type]["total_duration"] += duration

        # Compute average per type
        for stats in events_by_type.values():
            stats["average_duration"] = round(
                stats["total_duration"] / stats["count"], 4
            ) if stats["count"] > 0 else 0.0

        # Slowest individual events
        slowest_rows = self.db.fetch_all(
            """SELECT event_id, event_type, duration, session_id
               FROM event_log WHERE duration > 0
               ORDER BY duration DESC LIMIT 5"""
        )
        slowest_events = [
            {
                "event_id": r[0],
                "event_type": r[1],
                "duration": r[2],
                "session_id": r[3],
            }
            for r in slowest_rows
        ]

        return {
            "total_events": len(rows),
            "total_duration": round(total_duration, 4),
            "average_duration": round(total_duration / len(rows), 4),
            "events_by_type": events_by_type,
            "slowest_events": slowest_events,
        }

    def get_stage_timings(self, session_id: str) -> Dict:
        """Return per-stage timing breakdown for a single session.

        Pairs start/complete event types to compute elapsed time for each pipeline stage.
        Also includes the duration stored on each individual event.

        Returns:
            Dict mapping stage name to a dict with ``event_count``,
            ``total_duration``, and ``average_duration``.
        """
        rows = self.db.fetch_all(
            "SELECT event_type, duration FROM event_log WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,),
        )
        if not rows:
            return {}

        stage_map: Dict[str, Dict] = {}
        for event_type, duration in rows:
            if event_type not in stage_map:
                stage_map[event_type] = {"event_count": 0, "total_duration": 0.0}
            stage_map[event_type]["event_count"] += 1
            stage_map[event_type]["total_duration"] += duration

        # Derive stage names from start/complete pairs
        stages: Dict[str, Dict] = {}
        start_events = {
            "UNDERSTANDING_START", "ANALYSIS_START",
            "SEARCH_STARTED", "TESTING_START", "LEARNING_START",
        }
        complete_events = {
            "UNDERSTANDING_COMPLETE", "ANALYSIS_COMPLETE",
            "SOURCE_FOUND", "TESTING_COMPLETE", "LEARNING_COMPLETE",
        }
        for event_type in stage_map:
            if event_type in start_events:
                stage_name = event_type.replace("_START", "").lower()
                stages[stage_name] = {
                    "event_count": stage_map[event_type]["event_count"],
                    "total_duration": stage_map[event_type]["total_duration"],
                    "average_duration": round(
                        stage_map[event_type]["total_duration"]
                        / stage_map[event_type]["event_count"],
                        4,
                    ),
                }
            elif event_type in complete_events:
                stage_name = event_type.replace("_COMPLETE", "").lower()
                if stage_name not in stages:
                    stages[stage_name] = {
                        "event_count": stage_map[event_type]["event_count"],
                        "total_duration": stage_map[event_type]["total_duration"],
                        "average_duration": round(
                            stage_map[event_type]["total_duration"]
                            / stage_map[event_type]["event_count"],
                            4,
                        ),
                    }

        # Add remaining non-paired event types
        for event_type, stats in stage_map.items():
            if event_type not in start_events and event_type not in complete_events:
                stages[event_type.lower()] = {
                    "event_count": stats["event_count"],
                    "total_duration": stats["total_duration"],
                    "average_duration": round(
                        stats["total_duration"] / stats["event_count"], 4
                    ),
                }

        return stages

    def clear_old_events(self, days: int = 30) -> int:
        """Delete events older than the given number of days.

        Args:
            days: Age threshold in days (default 30).

        Returns:
            Number of rows deleted.
        """
        cutoff = time.time() - (days * 86400)
        self.db.execute(
            "DELETE FROM event_log WHERE timestamp < ?", (cutoff,)
        )
        return True

    def get_event_count_by_type(self) -> Dict[str, int]:
        """Return a count of events grouped by event type.

        Returns:
            Dict mapping event_type string to integer count.
        """
        rows = self.db.fetch_all(
            "SELECT event_type, COUNT(*) FROM event_log GROUP BY event_type ORDER BY COUNT(*) DESC"
        )
        return {r[0]: r[1] for r in rows} if rows else {}

    def get_session_summary(self, session_id: str) -> Dict:
        """Return a compact summary of a session's events.

        Includes event count, total duration, start/end timestamps, and the list
        of event types that occurred.
        """
        rows = self.db.fetch_all(
            "SELECT event_type, timestamp, duration FROM event_log WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,),
        )
        if not rows:
            return {"session_id": session_id, "event_count": 0}

        total_duration = sum(r[2] for r in rows)
        event_types = list(dict.fromkeys(r[0] for r in rows))  # ordered unique

        return {
            "session_id": session_id,
            "event_count": len(rows),
            "total_duration": round(total_duration, 4),
            "start_time": rows[0][1],
            "end_time": rows[-1][1],
            "event_types": event_types,
        }

    def delete_session(self, session_id: str) -> bool:
        """Remove all events for a given session.

        Returns:
            True on completion.
        """
        self.db.execute(
            "DELETE FROM event_log WHERE session_id = ?", (session_id,)
        )
        return True
