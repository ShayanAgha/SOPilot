"""
SOPilot database models.

Design notes:
- User: role is a plain string ("admin" / "user") rather than a separate
  roles table — two roles is simple enough that a lookup table would be
  over-engineering for this project.
- Document: represents one uploaded SOP PDF and its ingestion lifecycle.
  `category` lets both the admin library view and the chat UI filter by
  department (HR / Finance / IT-Security / Operations / Compliance).
- QueryLog: one row per question asked in /chat, written BEFORE the
  response is returned to the browser (see app/chat/routes.py) so the
  dashboard is accurate even if the client disconnects mid-response.
- Escalation: created automatically whenever SOPilot has to refuse a
  question for lack of grounding. This turns "I don't know" into a
  trackable signal for the admin: which procedures are missing or
  poorly documented. This table is SOPilot's main differentiator vs. a
  generic "chat with your PDF" project.
"""
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # "admin" | "user"
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    documents = db.relationship("Document", backref="uploader", lazy="dynamic")
    query_logs = db.relationship("QueryLog", backref="user", lazy="dynamic")

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Document(db.Model):
    __tablename__ = "documents"

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(512), nullable=False)
    category = db.Column(db.String(50), nullable=False, default="Other")
    owner_department = db.Column(db.String(120), nullable=True)

    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)
    error_message = db.Column(db.Text, nullable=True)

    page_count = db.Column(db.Integer, nullable=True)
    chunk_count = db.Column(db.Integer, nullable=True)
    version = db.Column(db.Integer, nullable=False, default=1)

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ingestion_started_at = db.Column(db.DateTime, nullable=True)
    ingested_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Document {self.filename} [{self.status}]>"

    @property
    def ingestion_duration_seconds(self):
        if self.ingestion_started_at and self.ingested_at:
            return (self.ingested_at - self.ingestion_started_at).total_seconds()
        return None


class QueryLog(db.Model):
    __tablename__ = "query_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # nullable = anonymous

    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)

    top_score = db.Column(db.Float, nullable=True)
    was_grounded = db.Column(db.Boolean, nullable=False, default=False)
    category_matched = db.Column(db.String(50), nullable=True)

    latency_ms = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    escalation = db.relationship(
        "Escalation", backref="query_log", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<QueryLog #{self.id} grounded={self.was_grounded}>"


class Escalation(db.Model):
    """
    Auto-created whenever a QueryLog comes back ungrounded (refused).
    Lets an admin see, at a glance, which procedures employees are
    asking about that aren't documented well enough to answer.
    """
    __tablename__ = "escalations"

    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"

    id = db.Column(db.Integer, primary_key=True)
    query_log_id = db.Column(db.Integer, db.ForeignKey("query_logs.id"), nullable=False)

    status = db.Column(db.String(20), nullable=False, default=STATUS_OPEN)
    resolved_note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Escalation #{self.id} [{self.status}]>"
