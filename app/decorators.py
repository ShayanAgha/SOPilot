"""
Route-protection decorators.

`admin_required` is what actually enforces the "a logged-in user must
not be able to reach /admin/*" requirement from the assignment spec.
It's applied at the top of every view in app/admin/routes.py.
"""
from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            # 403, not a redirect — a `user` hitting /admin/* should get a
            # clear "not allowed", not be silently bounced somewhere else.
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped


def user_required(view_func):
    """Any authenticated account (admin or user) may access these routes."""
    @wraps(view_func)
    @login_required
    def wrapped(*args, **kwargs):
        return view_func(*args, **kwargs)

    return wrapped
