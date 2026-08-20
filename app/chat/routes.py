"""
Chat blueprint — user-facing Q&A interface backed by the RAG pipeline.

/chat/ask flow (§3.3 + phases plan):
  1. Parse question + optional category filter from JSON body.
  2. Write a QueryLog row BEFORE calling the RAG pipeline (so the
     dashboard is accurate even if the client disconnects mid-response).
  3. Call answer_question() — embed → FAISS → threshold → Gemini.
  4. Update the QueryLog with the real answer, latency, grounded flag,
     category_matched, and top_score.
  5. If not grounded → auto-create an Escalation row (SOPilot differentiator).
  6. Return JSON to the browser.
"""
import time
from datetime import datetime

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Escalation, QueryLog

chat_bp = Blueprint("chat", __name__, template_folder="../templates/chat")


@chat_bp.route("")
@chat_bp.route("/")
@login_required
def chat_ui():
    """User-facing chat interface."""
    return render_template(
        "chat/chat.html", categories=current_app.config["SOP_CATEGORIES"]
    )


@chat_bp.route("/ask", methods=["POST"])
@login_required
def ask():
    """Grounded Q&A endpoint — full RAG pipeline."""
    body = request.get_json(silent=True) or {}
    question = body.get("question", "").strip()
    category = body.get("category") or None  # None means "search all"

    if not question:
        return jsonify({"error": "Question is required."}), 400

    # -------------------------------------------------------------------
    # Step 1: Pre-write QueryLog row (assignment requirement: log BEFORE
    # responding so the record exists even if Gemini times out).
    # -------------------------------------------------------------------
    log = QueryLog(
        user_id=current_user.id,
        question=question,
        answer="",           # filled in after RAG returns
        was_grounded=False,
        latency_ms=0,
    )
    db.session.add(log)
    db.session.commit()

    # -------------------------------------------------------------------
    # Step 2: RAG pipeline
    # -------------------------------------------------------------------
    t0 = time.perf_counter()

    from app.rag.query import answer_question
    result = answer_question(question, category=category, cfg=current_app.config)

    latency_ms = int((time.perf_counter() - t0) * 1000)

    # -------------------------------------------------------------------
    # Step 3: Update QueryLog with real result
    # -------------------------------------------------------------------
    log.answer = result["answer"]
    log.was_grounded = result["grounded"]
    log.latency_ms = latency_ms
    log.top_score = result.get("top_score")
    log.category_matched = result.get("category_matched")

    # -------------------------------------------------------------------
    # Step 4: Auto-create Escalation on refusal (Phase 6 differentiator)
    # -------------------------------------------------------------------
    if not result["grounded"]:
        esc = Escalation(query_log_id=log.id)
        db.session.add(esc)

    db.session.commit()

    return jsonify(
        {
            "answer": result["answer"],
            "sources": result["sources"],
            "grounded": result["grounded"],
            "latency_ms": latency_ms,
        }
    )
