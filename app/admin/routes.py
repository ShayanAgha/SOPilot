from flask import Blueprint, current_app, render_template, request

from app.decorators import admin_required
from app.models import Document, Escalation, QueryLog

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    """
    Traffic dashboard (§3.2). Real aggregation queries (total/today
    counts, avg latency, top questions, grounded %, per-day series,
    and the gap-analytics escalation chart) are wired up in Phase 5
    once QueryLog is actually being written to by /chat/ask.
    """
    stats = {
        "total_queries": QueryLog.query.count(),
        "total_documents": Document.query.count(),
        "open_escalations": Escalation.query.filter_by(
            status=Escalation.STATUS_OPEN
        ).count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


@admin_bp.route("/documents")
@admin_required
def documents():
    """
    SOP library view (§3.2). Upload + background ingestion trigger are
    built in Phase 3 — this route already supports the ?category=
    filter called out in the SOPilot plan.
    """
    category = request.args.get("category")
    query = Document.query.order_by(Document.uploaded_at.desc())
    if category:
        query = query.filter_by(category=category)
    docs = query.all()
    return render_template(
        "admin/documents.html",
        documents=docs,
        categories=current_app.config["SOP_CATEGORIES"],
        active_category=category,
    )


@admin_bp.route("/escalations")
@admin_required
def escalations():
    """
    SOPilot's differentiator: every ungrounded refusal in /chat becomes
    an open escalation here, so the admin can see which procedures
    aren't documented well enough. Populated once /chat/ask is live
    (Phase 4) and auto-creation logic is wired in (Phase 6).
    """
    open_escalations = (
        Escalation.query.filter_by(status=Escalation.STATUS_OPEN)
        .order_by(Escalation.created_at.desc())
        .all()
    )
    return render_template("admin/escalations.html", escalations=open_escalations)
