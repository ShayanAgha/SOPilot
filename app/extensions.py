"""
Extension instances live here, separate from __init__.py, so that
models.py and blueprints can import `db` / `login_manager` without
triggering a circular import with the app factory.
"""
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access SOPilot."
login_manager.login_message_category = "warning"
