import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from audit_log import get_latest_entry_by_content_id, get_log, log_submission
from main import get_heuristic_signal, get_llm_signal
from scoring import attribution_from_score, combine_scores, label_for_attribution

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


@app.route("/")
def home():
    return "Provenance Guard is running."

@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json(silent=True) or {}
    text = data.get("text")
    creator_id = data.get("creator_id")

    if not text or not creator_id:
        return jsonify({"error": "text and creator_id are required"}), 400

    content_id = str(uuid.uuid4())

    llm_signal = get_llm_signal(text)
    heuristic_signal = get_heuristic_signal(text)
    confidence_score = combine_scores(llm_signal["llm_score"], heuristic_signal["heuristic_score"])
    attribution = attribution_from_score(confidence_score)
    label = label_for_attribution(attribution)

    log_submission({
        "content_id": content_id,
        "creator_id": creator_id,
        "text_preview"  : text[:100],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attribution": attribution,
        "confidence": confidence_score,
        "llm_score": llm_signal["llm_score"],
        "heuristic_score": heuristic_signal["heuristic_score"],
        "label": label,
        "status": "classified",
    })

    return jsonify({
        "content_id": content_id,
        "text_preview"  : text[:100],
        "attribution": attribution,
        "confidence_score": confidence_score,
        "signal_scores": {
            "llm_score": llm_signal["llm_score"],
            "heuristic_score": heuristic_signal["heuristic_score"],
        },
        "label": label,
    })

@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True) or {}
    content_id = data.get("content_id")
    creator_reasoning = data.get("creator_reasoning")

    if not content_id or not creator_reasoning:
        return jsonify({"error": "content_id and creator_reasoning are required"}), 400

    original_entry = get_latest_entry_by_content_id(content_id)
    if original_entry is None:
        return jsonify({"error": "no submission found for that content_id"}), 404

    log_submission({
        "content_id": content_id,
        "creator_id": original_entry.get("creator_id"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attribution": original_entry.get("attribution"),
        "confidence": original_entry.get("confidence"),
        "llm_score": original_entry.get("llm_score"),
        "heuristic_score": original_entry.get("heuristic_score"),
        "label": original_entry.get("label"),
        "status": "under_review",
        "appeal_reasoning": creator_reasoning,
    })

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "message": "Your appeal has been received and marked for review.",
    })

@app.route("/log", methods=["GET"])
def log():
    return jsonify({"entries": get_log()})

if __name__ == "__main__":
    app.run(port=5001, debug=True)