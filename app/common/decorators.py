from functools import wraps
from flask import session, redirect, url_for

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return fn(*args, **kwargs)
    return wrapper

def role_required(*allowed_roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("auth.login"))
            role = session.get("role")
            if role not in allowed_roles:
                return redirect(url_for("main.home"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator
