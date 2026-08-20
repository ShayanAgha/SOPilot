from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import login_required

chat_bp = Blueprint("chat", __name__, template_folder="../templates/chat")


@chat_bp.route("")
@chat_bp.route("/")
@login_required
def chat_ui():
    """
    User-facing chat interface (§3.3). Any authenticated account (admin
    or user) can ask questions — admins just also happen to have the
    /admin/* panel available to them.
    """
    return render_template(
        "chat/chat.html", categories=current_app.config["SOP_CATEGORIES"]
    )


@chat_bp.route("/ask", methods=["POST"])
@login_required
def ask():
    """
    Grounded Q&A endpoint. Real retrieval (embed -> FAISS search ->
    threshold check -> Gemini) is wired up in Phase 4, once the RAG
    pipeline from Phase 2 is in place. For now this returns a
    placeholder so the chat UI is testable end-to-end.
    """
    question = (request.get_json(silent=True) or {}).get("question", "").strip()
    if not question:
        return jsonify({"error": "Question is required."}), 400

    return jsonify(
        {
            "answer": (
                "SOPilot's retrieval pipeline isn't wired up yet "
                "(coming in Phase 4) — this is a placeholder response."
            ),
            "sources": [],
            "grounded": False,
        }
    )
