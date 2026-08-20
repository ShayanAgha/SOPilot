"""
Admin blueprint — dashboard, SOP library (with upload + background
ingestion), escalation management, and gap-analytics JSON endpoint.
"""
import os
import threading
from datetime import datetime, date, timedelta

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
    flash,
)
from sqlalchemy import func

from app.decorators import admin_required
from app.extensions import db
from app.models import Document, Escalation, QueryLog

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    """Traffic dashboard with real aggregation stats."""
    total_queries = QueryLog.query.count()
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_queries = QueryLog.query.filter(QueryLog.created_at >= today_start).count()
    total_documents = Document.query.count()
    open_escalations = Escalation.query.filter_by(status=Escalation.STATUS_OPEN).count()

    # Avg latency
    avg_latency_row = db.session.query(func.avg(QueryLog.latency_ms)).scalar()
    avg_latency = round(avg_latency_row or 0)

    # Grounded %
    grounded_count = QueryLog.query.filter_by(was_grounded=True).count()
    grounded_pct = round((grounded_count / total_queries * 100) if total_queries else 0)

    # Top 10 most-asked questions (by exact question text frequency)
    top_questions = (
        db.session.query(QueryLog.question, func.count(QueryLog.id).label("cnt"))
        .group_by(QueryLog.question)
        .order_by(func.count(QueryLog.id).desc())
        .limit(10)
        .all()
    )

    stats = {
        "total_queries": total_queries,
        "today_queries": today_queries,
        "total_documents": total_documents,
        "open_escalations": open_escalations,
        "avg_latency_ms": avg_latency,
        "grounded_pct": grounded_pct,
    }
    return render_template("admin/dashboard.html", stats=stats, top_questions=top_questions)


# ---------------------------------------------------------------------------
# Query log viewer
# ---------------------------------------------------------------------------

@admin_bp.route("/logs")
@admin_required
def logs():
    """
    Paginated, searchable table of every QueryLog row.
    Satisfies §3.2 'Query log viewer' requirement.
    """
    page = request.args.get("page", 1, type=int)
    q = request.args.get("q", "").strip()
    per_page = current_app.config.get("LOGS_PER_PAGE", 25)

    query = QueryLog.query.order_by(QueryLog.created_at.desc())
    if q:
        query = query.filter(QueryLog.question.ilike(f"%{q}%"))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template(
        "admin/logs.html",
        logs=pagination.items,
        pagination=pagination,
        search=q,
    )


@admin_bp.route("/dashboard/gaps")
@admin_required
def dashboard_gaps():
    """
    JSON: last 7 days of daily query counts + escalations by category.
    Consumed by Chart.js in the dashboard template.
    """
    # Per-day query counts (last 14 days)
    days = []
    counts = []
    for i in range(13, -1, -1):
        day = date.today() - timedelta(days=i)
        day_start = datetime(day.year, day.month, day.day)
        day_end = day_start + timedelta(days=1)
        cnt = QueryLog.query.filter(
            QueryLog.created_at >= day_start,
            QueryLog.created_at < day_end,
        ).count()
        days.append(day.strftime("%b %d"))
        counts.append(cnt)

    # Escalations by category (from the related QueryLog.category_matched)
    category_counts: dict[str, int] = {}
    for esc in Escalation.query.filter_by(status=Escalation.STATUS_OPEN).all():
        cat = esc.query_log.category_matched or "Uncategorized"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    return jsonify(
        {
            "daily": {"labels": days, "counts": counts},
            "by_category": {
                "labels": list(category_counts.keys()),
                "counts": list(category_counts.values()),
            },
        }
    )


# ---------------------------------------------------------------------------
# SOP Library
# ---------------------------------------------------------------------------

@admin_bp.route("/documents")
@admin_required
def documents():
    """SOP library with category filter."""
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


@admin_bp.route("/documents/upload", methods=["POST"])
@admin_required
def upload_document():
    """Save uploaded PDF, create Document row, kick off background ingestion."""
    from flask_login import current_user

    file = request.files.get("file")
    category = request.form.get("category", "Other")
    owner_department = request.form.get("owner_department", "").strip()

    if not file or file.filename == "":
        flash("Please select a PDF file to upload.", "danger")
        return redirect(url_for("admin.documents"))

    if not _allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
        flash("Only PDF files are allowed.", "danger")
        return redirect(url_for("admin.documents"))

    # Save to uploads/
    filename = _secure_filename(file.filename)
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    stored_path = os.path.join(upload_folder, filename)

    # If a file with same name exists, append timestamp to avoid collision
    if os.path.exists(stored_path):
        base, ext = os.path.splitext(filename)
        filename = f"{base}_{int(datetime.utcnow().timestamp())}{ext}"
        stored_path = os.path.join(upload_folder, filename)

    file.save(stored_path)

    # Create DB record
    doc = Document(
        filename=filename,
        stored_path=stored_path,
        category=category,
        owner_department=owner_department or None,
        uploaded_by=current_user.id,
        status=Document.STATUS_PENDING,
    )
    db.session.add(doc)
    db.session.commit()

    # Kick off background ingestion — never blocks the request
    app = current_app._get_current_object()  # unwrap proxy for thread safety
    t = threading.Thread(target=_run_ingestion, args=(doc.id, app), daemon=True)
    t.start()

    flash(f'"{filename}" uploaded — ingestion started in the background.', "success")
    return redirect(url_for("admin.documents"))


@admin_bp.route("/documents/<int:doc_id>/status")
@admin_required
def document_status(doc_id):
    """JSON polling endpoint so the UI can refresh ingestion status live."""
    doc = db.session.get(Document, doc_id)
    if doc is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(
        {
            "id": doc.id,
            "status": doc.status,
            "chunk_count": doc.chunk_count,
            "page_count": doc.page_count,
            "error_message": doc.error_message,
            "ingestion_duration_seconds": doc.ingestion_duration_seconds,
        }
    )


@admin_bp.route("/documents/<int:doc_id>/delete", methods=["POST"])
@admin_required
def delete_document(doc_id):
    """Remove document record (and stored file) from the system."""
    doc = db.session.get(Document, doc_id)
    if doc is None:
        flash("Document not found.", "danger")
        return redirect(url_for("admin.documents"))

    # Delete physical file
    try:
        if os.path.exists(doc.stored_path):
            os.remove(doc.stored_path)
    except OSError:
        pass

    db.session.delete(doc)
    db.session.commit()
    flash(f'"{doc.filename}" has been deleted.', "info")
    return redirect(url_for("admin.documents"))


# ---------------------------------------------------------------------------
# Escalations
# ---------------------------------------------------------------------------

@admin_bp.route("/escalations")
@admin_required
def escalations():
    """SOPilot differentiator: every ungrounded refusal shows up here."""
    open_escalations = (
        Escalation.query.filter_by(status=Escalation.STATUS_OPEN)
        .order_by(Escalation.created_at.desc())
        .all()
    )
    resolved_escalations = (
        Escalation.query.filter_by(status=Escalation.STATUS_RESOLVED)
        .order_by(Escalation.resolved_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "admin/escalations.html",
        escalations=open_escalations,
        resolved=resolved_escalations,
    )


@admin_bp.route("/escalations/<int:esc_id>/resolve", methods=["POST"])
@admin_required
def resolve_escalation(esc_id):
    """Mark an escalation as resolved with an optional note."""
    esc = db.session.get(Escalation, esc_id)
    if esc is None:
        flash("Escalation not found.", "danger")
        return redirect(url_for("admin.escalations"))

    note = request.form.get("note", "").strip()
    esc.status = Escalation.STATUS_RESOLVED
    esc.resolved_note = note or None
    esc.resolved_at = datetime.utcnow()
    db.session.commit()
    flash("Escalation marked as resolved.", "success")
    return redirect(url_for("admin.escalations"))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _allowed_file(filename: str, allowed: set) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def _secure_filename(filename: str) -> str:
    """Basic safe-filename: keep only alphanumerics, dots, dashes, underscores."""
    import re
    name = os.path.basename(filename)
    name = re.sub(r"[^\w.\-]", "_", name)
    return name or "upload.pdf"


def _run_ingestion(document_id: int, app) -> None:
    """Wrapper called from the background thread — imports here to avoid
    circular imports at module load time."""
    from app.rag.ingest import ingest_document
    ingest_document(document_id, app)
