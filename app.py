import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request

from audit_log import get_log, log_submission
from main import get_heuristic_signal, get_llm_signal
from scoring import attribution_from_score, combine_scores

app = Flask(__name__)


@app.route("/")
def home():
    return "Provenance Guard is running."

@app.route("/submit", methods=["POST"])
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

    log_submission({
        "content_id": content_id,
        "creator_id": creator_id,
        "text_preview"  : text[:100],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attribution": attribution,
        "confidence": confidence_score,
        "llm_score": llm_signal["llm_score"],
        "heuristic_score": heuristic_signal["heuristic_score"],
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
        "label": "placeholder label",
    })

@app.route("/log", methods=["GET"])
def log():
    return jsonify({"entries": get_log()})

if __name__ == "__main__":
    app.run(port=5001, debug=True)