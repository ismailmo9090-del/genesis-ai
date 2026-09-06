"""Learning API — Flask endpoints for the Genesis Learning System.

Provides a local-first API for:
- Experience ingestion
- Learning session management
- Knowledge/skill retrieval
- Learning status and progress
- Generalization and reflection

All endpoints are local-only. No external access by default.
"""

from __future__ import annotations

import json
import logging
import time
from functools import wraps

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Blueprint for learning API
learning_bp = Blueprint("learning", __name__, url_prefix="/learning")

# Global references (set by init_learning_api)
_learning_pipeline = None
_experience_memory = None
_learning_session_manager = None
_curriculum_engine = None
_firewall = None
_evolution = None
_db = None


def init_learning_api(app, db, learning_pipeline, experience_memory, session_manager=None):
    """Initialize the learning API with dependencies."""
    global _learning_pipeline, _experience_memory, _learning_session_manager, _db
    global _curriculum_engine, _firewall, _evolution
    _learning_pipeline = learning_pipeline
    _experience_memory = experience_memory
    _learning_session_manager = session_manager
    _db = db

    # Initialize curriculum engine, firewall, and evolution
    from genesis_ai.learning.curriculum import CurriculumEngine
    from genesis_ai.learning.firewall import LearningFirewall
    from genesis_ai.learning.evolution import KnowledgeEvolution
    _curriculum_engine = CurriculumEngine(db)
    _firewall = LearningFirewall(db)
    _evolution = KnowledgeEvolution(db)

    if "learning" not in app.blueprints:
        app.register_blueprint(learning_bp)
    logger.info("Learning API initialized (with curriculum + firewall)")


def require_pipeline(f):
    """Decorator to ensure learning pipeline is available."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if _learning_pipeline is None:
            return jsonify({"error": "Learning pipeline not initialized"}), 503
        return f(*args, **kwargs)
    return decorated


# ── Experience Ingestion ──────────────────────────────────────────────

@learning_bp.route("/experience", methods=["POST"])
@require_pipeline
def ingest_experience():
    """Ingest a learning experience.

    This is the primary API for teaching Genesis through experience.
    The experience is processed through the full learning pipeline.

    Expected JSON:
    {
        "task": "...",
        "goal": "...",
        "context": {},
        "observations": [],
        "actions": [],
        "tools_used": [],
        "errors": [],
        "attempts": [],
        "result": {},
        "success": true/false,
        "evidence": [],
        "reflection": "...",
        "metadata": {}
    }
    """
    data = request.get_json()
    if not data or "task" not in data:
        return jsonify({"error": "Missing required field: task"}), 400

    from .experience_memory import Experience
    experience = Experience(
        task=data.get("task", ""),
        goal=data.get("goal", ""),
        context=data.get("context", {}),
        observations=data.get("observations", []),
        actions=data.get("actions", []),
        tools_used=data.get("tools_used", []),
        errors=data.get("errors", []),
        attempts=data.get("attempts", []),
        result=data.get("result", {}),
        success=data.get("success", False),
        evidence=data.get("evidence", []),
        reflection=data.get("reflection", ""),
        metadata=data.get("metadata", {}),
    )

    # Ingest into memory
    exp_id = _experience_memory.ingest(experience)

    # Process through learning pipeline
    learning_result = _learning_pipeline.process_experience(experience)

    return jsonify({
        "experience_id": exp_id,
        "learning_result": {
            "success": learning_result.success,
            "lessons_learned": learning_result.lessons_learned,
            "generalizations": learning_result.generalizations,
            "knowledge_created": len(learning_result.knowledge_created),
            "skills_created": len(learning_result.skills_created),
            "skills_updated": len(learning_result.skills_updated),
            "contradictions_found": len(learning_result.contradictions_found),
            "confidence_delta": learning_result.confidence_delta,
            "steps_completed": learning_result.steps_completed,
            "error": learning_result.error,
            "duration": round(learning_result.duration, 3),
        },
    }), 201


@learning_bp.route("/observation", methods=["POST"])
@require_pipeline
def submit_observation():
    """Submit an observation (lighter than a full experience)."""
    data = request.get_json()
    if not data or "observation" not in data:
        return jsonify({"error": "Missing required field: observation"}), 400

    from .experience_memory import Experience
    experience = Experience(
        task=data.get("context", {}).get("task", "observation"),
        goal="observe",
        observations=[data["observation"]],
        success=True,
        metadata={"type": "observation", **data.get("metadata", {})},
    )
    exp_id = _experience_memory.ingest(experience)
    return jsonify({"experience_id": exp_id, "status": "observed"}), 201


@learning_bp.route("/result", methods=["POST"])
@require_pipeline
def submit_result():
    """Submit a task result (outcome of an action)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    from .experience_memory import Experience
    experience = Experience(
        task=data.get("task", ""),
        goal=data.get("goal", ""),
        result=data.get("result", {}),
        success=data.get("success", False),
        errors=data.get("errors", []),
        metadata={"type": "result", **data.get("metadata", {})},
    )
    exp_id = _experience_memory.ingest(experience)
    learning_result = _learning_pipeline.process_experience(experience)
    return jsonify({
        "experience_id": exp_id,
        "processed": learning_result.success,
        "lessons": learning_result.lessons_learned,
    }), 201


@learning_bp.route("/error", methods=["POST"])
@require_pipeline
def submit_error():
    """Submit an error report for failure learning."""
    data = request.get_json()
    if not data or "error" not in data:
        return jsonify({"error": "Missing required field: error"}), 400

    from .experience_memory import Experience
    experience = Experience(
        task=data.get("task", ""),
        goal=data.get("goal", ""),
        errors=[data["error"]],
        success=False,
        actions=data.get("actions", []),
        tools_used=data.get("tools_used", []),
        reflection=data.get("reflection", ""),
        metadata={"type": "error_report", **data.get("metadata", {})},
    )
    exp_id = _experience_memory.ingest(experience)
    learning_result = _learning_pipeline.process_experience(experience)
    return jsonify({
        "experience_id": exp_id,
        "failure_learned": learning_result.success,
        "lessons": learning_result.lessons_learned,
        "generalizations": learning_result.generalizations,
    }), 201


@learning_bp.route("/feedback", methods=["POST"])
@require_pipeline
def submit_feedback():
    """Submit feedback on a previous response."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    from .experience_memory import Experience
    experience = Experience(
        task=data.get("task", "feedback"),
        goal="improve",
        result={"feedback": data.get("feedback", ""), "rating": data.get("rating", 0)},
        success=data.get("rating", 0) >= 3,
        reflection=data.get("comment", ""),
        metadata={"type": "feedback", **data.get("metadata", {})},
    )
    exp_id = _experience_memory.ingest(experience)
    return jsonify({"experience_id": exp_id, "status": "feedback_received"}), 201


@learning_bp.route("/knowledge", methods=["POST"])
@require_pipeline
def submit_knowledge():
    """Submit a knowledge claim for verification."""
    data = request.get_json()
    if not data or "claim" not in data:
        return jsonify({"error": "Missing required field: claim"}), 400

    _db.execute(
        """INSERT INTO learned_knowledge
           (concept, claim, source, evidence, confidence, created_at, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            data.get("concept", "general"),
            data["claim"],
            data.get("source", "external"),
            json.dumps(data.get("evidence", [])),
            data.get("confidence", 0.5),
            time.time(),
            data.get("status", "UNCERTAIN"),
        ),
    )
    return jsonify({"status": "knowledge_submitted"}), 201


@learning_bp.route("/skill", methods=["POST"])
@require_pipeline
def submit_skill():
    """Submit a skill definition."""
    data = request.get_json()
    if not data or "name" not in data:
        return jsonify({"error": "Missing required field: name"}), 400

    import uuid
    skill_id = str(uuid.uuid4())[:12]
    _db.execute(
        """INSERT INTO learned_skills
           (skill_id, name, description, purpose, procedure, confidence,
            experience_count, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
        (
            skill_id,
            data["name"],
            data.get("description", ""),
            data.get("purpose", ""),
            json.dumps(data.get("procedure", [])),
            data.get("confidence", 0.5),
            time.time(),
            time.time(),
        ),
    )
    return jsonify({"skill_id": skill_id, "status": "skill_created"}), 201


@learning_bp.route("/reflection", methods=["POST"])
@require_pipeline
def submit_reflection():
    """Submit a reflection on a learning session."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    from .experience_memory import Experience
    experience = Experience(
        task=data.get("task", "reflection"),
        goal="reflect",
        reflection=data.get("reflection", ""),
        lessons=data.get("lessons", []),
        generalizations=data.get("generalizations", []),
        success=True,
        metadata={"type": "reflection", **data.get("metadata", {})},
    )
    exp_id = _experience_memory.ingest(experience)
    return jsonify({"experience_id": exp_id, "status": "reflection_recorded"}), 201


# ── Learning Status & Progress ────────────────────────────────────────

@learning_bp.route("/status", methods=["GET"])
@require_pipeline
def get_status():
    """Get current learning system status."""
    stats = _learning_pipeline.get_stats()
    exp_stats = _experience_memory.get_stats()
    return jsonify({
        "status": "active",
        "learning_pipeline": stats,
        "experience_memory": exp_stats,
        "timestamp": time.time(),
    })


@learning_bp.route("/progress", methods=["GET"])
@require_pipeline
def get_progress():
    """Get learning progress over time."""
    recent = _experience_memory.get_recent(limit=20)
    stats = _learning_pipeline.get_stats()

    # Calculate recent success rate
    if recent:
        recent_success = sum(1 for e in recent if e.success)
        recent_rate = recent_success / len(recent)
    else:
        recent_rate = 0.0

    return jsonify({
        "total_experiences": exp_stats.get("total", 0),
        "recent_success_rate": round(recent_rate, 3),
        "knowledge_items": stats.get("knowledge_items", 0),
        "skills": stats.get("skills", 0),
        "generalizations": stats.get("generalizations", 0),
        "verified_knowledge": stats.get("verified_knowledge", 0),
        "recent_experiences": [
            {
                "task": e.task[:100],
                "success": e.success,
                "duration": round(e.duration, 2),
                "timestamp": e.timestamp,
            }
            for e in recent[:10]
        ],
    })


@learning_bp.route("/gaps", methods=["GET"])
@require_pipeline
def get_gaps():
    """Get identified knowledge gaps."""
    # Query knowledge with low confidence or uncertain status
    uncertain = _db.fetch_all(
        "SELECT concept, claim, confidence FROM learned_knowledge WHERE status = 'UNCERTAIN' ORDER BY confidence ASC LIMIT 20"
    )
    outdated = _db.fetch_all(
        "SELECT concept, claim, confidence FROM learned_knowledge WHERE status = 'OUTDATED' LIMIT 20"
    )
    return jsonify({
        "uncertain_knowledge": [{"concept": r[0], "claim": r[1], "confidence": r[2]} for r in uncertain],
        "outdated_knowledge": [{"concept": r[0], "claim": r[1], "confidence": r[2]} for r in outdated],
    })


@learning_bp.route("/skills", methods=["GET"])
@require_pipeline
def get_skills():
    """Get all learned skills."""
    rows = _db.fetch_all(
        "SELECT skill_id, name, description, confidence, success_rate, experience_count, last_used FROM learned_skills ORDER BY confidence DESC"
    )
    skills = [
        {
            "skill_id": r[0], "name": r[1], "description": r[2],
            "confidence": r[3], "success_rate": r[4],
            "experience_count": r[5], "last_used": r[6],
        }
        for r in rows
    ]
    return jsonify({"skills": skills, "total": len(skills)})


@learning_bp.route("/knowledge", methods=["GET"])
@require_pipeline
def get_knowledge():
    """Get all learned knowledge."""
    status_filter = request.args.get("status", "")
    if status_filter:
        rows = _db.fetch_all(
            "SELECT id, concept, claim, confidence, status, usage_count, created_at FROM learned_knowledge WHERE status = ? ORDER BY confidence DESC LIMIT 50",
            (status_filter,),
        )
    else:
        rows = _db.fetch_all(
            "SELECT id, concept, claim, confidence, status, usage_count, created_at FROM learned_knowledge ORDER BY confidence DESC LIMIT 50"
        )
    knowledge = [
        {
            "id": r[0], "concept": r[1], "claim": r[2],
            "confidence": r[3], "status": r[4],
            "usage_count": r[5], "created_at": r[6],
        }
        for r in rows
    ]
    return jsonify({"knowledge": knowledge, "total": len(knowledge)})


@learning_bp.route("/experiences", methods=["GET"])
@require_pipeline
def get_experiences():
    """Get recent experiences."""
    limit = request.args.get("limit", 20, type=int)
    experiences = _experience_memory.get_recent(limit=limit)
    return jsonify({
        "experiences": [
            {
                "experience_id": e.experience_id,
                "task": e.task[:200],
                "success": e.success,
                "confidence": e.confidence,
                "duration": round(e.duration, 2),
                "lessons": e.lessons[:3],
                "timestamp": e.timestamp,
            }
            for e in experiences
        ],
        "total": len(experiences),
    })


@learning_bp.route("/generalizations", methods=["GET"])
@require_pipeline
def get_generalizations():
    """Get all learned generalizations."""
    rows = _db.fetch_all(
        "SELECT id, pattern, description, confidence, scope, usage_count, success_rate, created_at FROM learned_generalizations ORDER BY confidence DESC LIMIT 50"
    )
    gens = [
        {
            "id": r[0], "pattern": r[1], "description": r[2],
            "confidence": r[3], "scope": r[4],
            "usage_count": r[5], "success_rate": r[6], "created_at": r[7],
        }
        for r in rows
    ]
    return jsonify({"generalizations": gens, "total": len(gens)})


@learning_bp.route("/evaluate", methods=["POST"])
@require_pipeline
def evaluate():
    """Evaluate whether a generalization applies to a new task."""
    data = request.get_json()
    if not data or "task" not in data:
        return jsonify({"error": "Missing required field: task"}), 400

    task = data["task"]
    similar = _experience_memory.find_similar(task, limit=5)

    # Check which generalizations might apply
    applicable = []
    rows = _db.fetch_all(
        "SELECT pattern, description, confidence FROM learned_generalizations WHERE confidence > 0.3"
    )
    for pattern, desc, conf in rows:
        task_words = set(task.lower().split())
        pattern_words = set(pattern.lower().split())
        overlap = task_words & pattern_words
        if overlap and len(overlap) >= 1:
            applicable.append({
                "pattern": pattern,
                "description": desc,
                "confidence": conf,
                "overlap": list(overlap),
            })

    return jsonify({
        "task": task,
        "similar_experiences": len(similar),
        "applicable_generalizations": applicable,
    })


@learning_bp.route("/generalize", methods=["POST"])
@require_pipeline
def generalize():
    """Trigger generalization on recent experiences."""
    recent = _experience_memory.get_successful(limit=10)
    generalizations = []
    for exp in recent:
        if exp.lessons:
            for lesson in exp.lessons:
                generalizations.append({
                    "source": exp.experience_id,
                    "lesson": lesson,
                })

    return jsonify({
        "recent_successful": len(recent),
        "potential_generalizations": generalizations[:20],
    })


# ── Learning Sessions ─────────────────────────────────────────────────

@learning_bp.route("/session/start", methods=["POST"])
@require_pipeline
def start_session():
    """Start a learning session."""
    data = request.get_json() or {}
    session_id = f"learn_{int(time.time())}_{id(data)}"
    _db.execute(
        """INSERT INTO learning_sessions
           (user_id, topic, session_type, goals, status)
           VALUES (?, ?, ?, ?, 'active')""",
        (
            data.get("user_id", 1),
            data.get("topic", "general"),
            data.get("session_type", "guided"),
            json.dumps(data.get("goals", [])),
        ),
    )
    return jsonify({"session_id": session_id, "status": "started"}), 201


@learning_bp.route("/session/stop", methods=["POST"])
@require_pipeline
def stop_session():
    """Stop the current learning session."""
    data = request.get_json() or {}
    session_id = data.get("session_id", "")
    if session_id:
        _db.execute(
            "UPDATE learning_sessions SET status = 'stopped' WHERE id = ?",
            (session_id,),
        )
    return jsonify({"status": "stopped"})


@learning_bp.route("/session/pause", methods=["POST"])
@require_pipeline
def pause_session():
    """Pause the current learning session."""
    data = request.get_json() or {}
    session_id = data.get("session_id", "")
    if session_id:
        _db.execute(
            "UPDATE learning_sessions SET status = 'paused' WHERE id = ?",
            (session_id,),
        )
    return jsonify({"status": "paused"})


@learning_bp.route("/session/resume", methods=["POST"])
@require_pipeline
def resume_session():
    """Resume a paused learning session."""
    data = request.get_json() or {}
    session_id = data.get("session_id", "")
    if session_id:
        _db.execute(
            "UPDATE learning_sessions SET status = 'active' WHERE id = ?",
            (session_id,),
        )
    return jsonify({"status": "resumed"})


# ── Curriculum Endpoints ─────────────────────────────────────────────

@learning_bp.route("/curriculum/profile", methods=["GET"])
@require_pipeline
def get_curriculum_profile():
    """Get skill profile for a domain."""
    domain = request.args.get("domain", "general")
    profile = _curriculum_engine.get_profile(domain)
    return jsonify({
        "domain": profile.domain,
        "level": profile.level.value,
        "success_score": profile.success_score,
        "total_tasks": profile.total_tasks,
        "successful_tasks": profile.successful_tasks,
        "failed_tasks": profile.failed_tasks,
        "streak": profile.streak,
        "best_streak": profile.best_streak,
    })


@learning_bp.route("/curriculum/recommend", methods=["GET"])
@require_pipeline
def get_curriculum_recommendation():
    """Get recommended next tasks for a domain."""
    domain = request.args.get("domain", "general")
    rec = _curriculum_engine.recommend(domain)
    return jsonify({
        "domain": rec.domain,
        "current_level": rec.current_level.value,
        "recommended_tasks": rec.recommended_tasks,
        "reason": rec.reason,
        "difficulty": rec.difficulty,
        "estimated_time_minutes": rec.estimated_time_minutes,
    })


@learning_bp.route("/curriculum/profiles", methods=["GET"])
@require_pipeline
def get_all_profiles():
    """Get all skill profiles."""
    profiles = _curriculum_engine.get_all_profiles()
    return jsonify({
        "profiles": [
            {
                "domain": p.domain, "level": p.level.value,
                "score": p.success_score, "total": p.total_tasks,
                "success_rate": (p.successful_tasks / p.total_tasks * 100) if p.total_tasks > 0 else 0,
                "streak": p.streak,
            }
            for p in profiles
        ]
    })


@learning_bp.route("/curriculum/stats", methods=["GET"])
@require_pipeline
def get_curriculum_stats():
    """Get detailed stats for a domain."""
    domain = request.args.get("domain", "general")
    return jsonify(_curriculum_engine.get_domain_stats(domain))


@learning_bp.route("/curriculum/reset", methods=["POST"])
@require_pipeline
def reset_curriculum():
    """Reset progress for a domain (dangerous — requires confirmation)."""
    data = request.get_json() or {}
    domain = data.get("domain", "")
    if not domain:
        return jsonify({"error": "Domain required"}), 400

    # Firewall check
    verdict = _firewall.check("delete_knowledge", {"domain": domain})
    if not verdict.allowed:
        return jsonify({"error": verdict.blocked_reason, "requires_approval": True}), 403

    _curriculum_engine.reset_domain(domain)
    return jsonify({"status": "reset", "domain": domain})


# ── Firewall Endpoints ───────────────────────────────────────────────

@learning_bp.route("/firewall/log", methods=["GET"])
@require_pipeline
def get_firewall_log():
    """Get recent firewall log entries."""
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"log": _firewall.get_log(limit)})


@learning_bp.route("/firewall/approvals", methods=["GET"])
@require_pipeline
def get_pending_approvals():
    """Get actions waiting for approval."""
    return jsonify({"approvals": _firewall.get_pending_approvals()})


@learning_bp.route("/firewall/approve", methods=["POST"])
@require_pipeline
def approve_action():
    """Approve a pending action."""
    data = request.get_json() or {}
    action = data.get("action", "")
    if not action:
        return jsonify({"error": "Action required"}), 400
    _firewall.approve(action)
    return jsonify({"status": "approved", "action": action})


@learning_bp.route("/firewall/deny", methods=["POST"])
@require_pipeline
def deny_action():
    """Deny a pending action."""
    data = request.get_json() or {}
    action = data.get("action", "")
    if not action:
        return jsonify({"error": "Action required"}), 400
    _firewall.deny(action)
    return jsonify({"status": "denied", "action": action})


@learning_bp.route("/firewall/stats", methods=["GET"])
@require_pipeline
def get_firewall_stats():
    """Get firewall statistics."""
    return jsonify(_firewall.get_stats())


# ── Knowledge Evolution Endpoints ────────────────────────────────────

@learning_bp.route("/evolution/contradictions", methods=["GET"])
@require_pipeline
def get_contradictions():
    """Get detected contradictions."""
    resolved = request.args.get("resolved", "false").lower() == "true"
    contradictions = _evolution.get_contradictions(resolved=resolved)
    return jsonify({
        "contradictions": [
            {
                "knowledge_a_id": c.knowledge_a_id,
                "knowledge_b_id": c.knowledge_b_id,
                "claim_a": c.claim_a,
                "claim_b": c.claim_b,
                "type": c.contradiction_type,
                "severity": c.severity,
                "resolved": c.resolved,
                "resolution": c.resolution,
            }
            for c in contradictions
        ]
    })


@learning_bp.route("/evolution/versions/<int:knowledge_id>", methods=["GET"])
@require_pipeline
def get_knowledge_versions(knowledge_id):
    """Get version history of a knowledge item."""
    versions = _evolution.get_knowledge_versions(knowledge_id)
    return jsonify({
        "versions": [
            {
                "version": v.version_number,
                "claim": v.claim,
                "confidence": v.confidence,
                "status": v.status,
                "source": v.source,
                "created_at": v.created_at,
                "superseded_by": v.superseded_by,
            }
            for v in versions
        ]
    })


@learning_bp.route("/evolution/freshness/<int:knowledge_id>", methods=["GET"])
@require_pipeline
def get_knowledge_freshness(knowledge_id):
    """Get freshness info for a knowledge item."""
    return jsonify(_evolution.get_freshness(knowledge_id))


@learning_bp.route("/evolution/verify/<int:knowledge_id>", methods=["POST"])
@require_pipeline
def verify_knowledge(knowledge_id):
    """Manually verify a knowledge item."""
    _evolution.verify_knowledge(knowledge_id)
    return jsonify({"status": "verified", "knowledge_id": knowledge_id})


@learning_bp.route("/evolution/decay", methods=["POST"])
@require_pipeline
def trigger_decay():
    """Trigger decay of stale knowledge."""
    data = request.get_json() or {}
    max_age_days = data.get("max_age_days", 30)
    _evolution.decay_stale_knowledge(max_age_days)
    return jsonify({"status": "decay_applied", "max_age_days": max_age_days})


@learning_bp.route("/evolution/stats", methods=["GET"])
@require_pipeline
def get_evolution_stats():
    """Get knowledge evolution statistics."""
    return jsonify(_evolution.get_evolution_stats())
