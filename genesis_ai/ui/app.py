"""Flask web application for Genesis AI."""

import logging
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

from genesis_ai.main import GenesisAI

logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates")
CORS(app)

genesis: GenesisAI = None


def create_app(genesis_instance: GenesisAI) -> Flask:
    global genesis
    genesis = genesis_instance

    # Initialize Learning API
    from genesis_ai.learning.api import init_learning_api
    init_learning_api(
        app,
        genesis.db,
        genesis.learning_pipeline,
        genesis.experience_memory,
    )

    # Initialize Inference API (Production /v1 endpoints)
    from genesis_ai.api.inference import init_inference_api
    init_inference_api(app, genesis, genesis.db)

    # Initialize Code Generation API
    from genesis_ai.api.code_api import init_code_api
    init_code_api(app, genesis)

    return app


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """UI chat endpoint — routes through the same Genesis core as /v1/chat."""
    data = request.get_json(force=True)
    message = data.get("message", "")
    user_id = data.get("user_id", "web_user")

    if not message:
        return jsonify({"error": "No message provided"}), 400

    result = genesis.chat(user_id, message)
    return jsonify(result)


@app.route("/api/status")
def api_status():
    return jsonify(genesis.get_status())


@app.route("/api/memory")
def api_memory():
    stats = genesis.get_memory_stats()
    recent = genesis.memory_engine.get_recent_memories(10)
    return jsonify({"stats": stats, "recent_memories": recent})


@app.route("/api/knowledge")
def api_knowledge():
    stats = genesis.get_knowledge_stats()
    concepts = genesis.db.list_concepts()
    graph_data = []
    for c in concepts[:20]:
        items = genesis.db.get_knowledge_for_concept(c["id"])
        graph_data.append({
            "concept": c.get("name", f"concept_{c['id']}"),
            "knowledge_count": len(items),
            "id": c["id"],
        })
    return jsonify({"stats": stats, "graph": graph_data})


@app.route("/api/skills")
def api_skills():
    stats = genesis.get_skill_stats()
    skills = genesis.db.list_skills() if hasattr(genesis.db, "list_skills") else []
    return jsonify({"stats": stats, "skills": skills})


@app.route("/api/learning")
def api_learning():
    stats = genesis.get_learning_stats()
    timeline = genesis.get_learning_timeline()
    return jsonify({"stats": stats, "timeline": timeline})


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    data = request.get_json(force=True)
    result = genesis.process_feedback(data)
    return jsonify(result)


@app.route("/api/reflection")
def api_reflection():
    return jsonify(genesis.reflect())


@app.route("/api/privacy")
def api_privacy():
    return jsonify(genesis.get_privacy_report())


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "POST":
        data = request.get_json(force=True)
        return jsonify({"success": True, "message": "Settings updated", "settings": data})
    return jsonify({
        "privacy": genesis.get_privacy_report(),
        "learning_stats": genesis.get_learning_stats(),
        "status": genesis.get_status(),
    })


@app.route("/api/research/<query>")
def api_research(query):
    result = genesis.research(query)
    return jsonify(result)


@app.route("/api/pipeline/<session_id>", methods=["GET"])
def get_pipeline(session_id):
    """Get pipeline progress for a session."""
    events = genesis.event_log.get_session_events(session_id)
    timings = genesis.event_log.get_stage_timings(session_id)
    return jsonify({
        "session_id": session_id,
        "events": [{"type": e.event_type, "timestamp": e.timestamp, "duration": e.duration, "data": e.data} for e in events],
        "timings": timings,
        "total_stages": len(events)
    })
