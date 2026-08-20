import os

import click
from flask import Flask, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from config import config_map
from app.extensions import db, login_manager


def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=True)

    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app.config.from_object(config_map.get(config_name, config_map["default"]))

    # Make sure instance/, uploads/, and vector_store/ exist before anything
    # tries to write to them (SQLite file, uploaded PDFs, FAISS index).
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["VECTOR_STORE_DIR"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    _register_blueprints(app)
    _register_cli(app)
    _register_error_handlers(app)
    _register_root_routes(app)

    with app.app_context():
        # Simple/portfolio-friendly: create tables automatically if they
        # don't exist yet. For real production use you'd swap this for
        # Alembic migrations, but that's out of scope for this assignment.
        db.create_all()

    return app


def _register_blueprints(app):
    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.chat.routes import chat_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(chat_bp, url_prefix="/chat")


def _register_root_routes(app):
    @app.route("/")
    @login_required
    def index():
        # Admins land on the dashboard, regular users land in chat.
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("chat.chat_ui"))


def _register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404


def _register_cli(app):
    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
    )
    def create_admin(email, password):
        """
        Seed the first admin account, e.g.:
            flask create-admin --email owner@company.com
        Credentials are never hardcoded in the repo — they're supplied
        interactively (or piped in) at seed time.
        """
        from app.models import User

        existing = User.query.filter_by(email=email).first()
        if existing:
            existing.role = "admin"
            existing.set_password(password)
            db.session.commit()
            click.echo(f"Existing user {email} promoted to admin and password reset.")
            return

        admin = User(email=email, role="admin")
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Admin account created: {email}")


@login_manager.user_loader
def load_user(user_id):
    from app.models import User

    return User.query.get(int(user_id))
