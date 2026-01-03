import os
from flask import Flask, session
from dotenv import load_dotenv

from .config import get_config
from .extensions import mysql
from .common.db import get_cursor

if (os.getenv("APP_ENV") or "").lower() in ("dev", "development"):
    load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config.from_object(get_config())

    mysql.init_app(app)

    from .main.routes import bp as main_bp
    from .auth.routes import bp as auth_bp
    from .account.routes import bp as account_bp
    from .tickets.routes import bp as tickets_bp
    from .users.routes import bp as users_bp
    from .messages.routes import bp as messages_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(messages_bp)

    @app.context_processor
    def inject_year():
        from datetime import datetime
        return {"current_year": datetime.now().year}

    @app.context_processor
    def inject_unread_count():
        if "user_id" not in session:
            return dict(unread_count=0)

        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM messages WHERE receiver_id=%s AND is_read=0",
                (session["user_id"],),
            )
            count = cur.fetchone()[0]
        return dict(unread_count=count)

    return app

app = create_app()
