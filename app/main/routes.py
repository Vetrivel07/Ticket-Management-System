from flask import Blueprint, render_template, redirect, url_for, session
from ..common.db import get_cursor

bp = Blueprint("main", __name__)

@bp.get("/")
def index():
    # original: checks 'user_id' and redirects to 'home'
    if "user_id" in session:
        return redirect(url_for("main.home"))
    return render_template("index.html")

@bp.get("/home")
def home():
    # original: checks 'username' and redirects to 'login'
    if "username" not in session:
        return redirect(url_for("auth.login"))

    with get_cursor() as cur:
        # ---------------- Responder View ----------------
        if session.get("role") == "responder":
            cur.execute(
                """
                SELECT t.id, t.title, t.description, u.username AS creator_name,
                       t.status, t.created_at, r.username AS responder_name
                FROM tickets t
                JOIN users u ON t.user_id = u.id
                LEFT JOIN users r ON t.responder_id = r.id
                WHERE t.status != 'done'
                  AND (t.responder_id IS NULL OR t.responder_id = %s)
                  AND NOT EXISTS (
                      SELECT 1 FROM ticket_responder_log log
                      WHERE log.ticket_id = t.id
                        AND log.responder_id = %s
                        AND log.status = 'declined'
                  )
                ORDER BY t.created_at DESC
                """,
                (session["user_id"], session["user_id"]),
            )

            tickets = [
                dict(
                    id=row[0],
                    title=row[1],
                    description=row[2],
                    username=row[3],
                    status=row[4],
                    created_at=row[5],
                    responder=row[6] if row[6] else "NILL",
                )
                for row in cur.fetchall()
            ]

        # ---------------- Employee View ----------------
        else:
            cur.execute(
                """
                SELECT t.id, t.title, t.description, creator.username AS creator_name,
                       t.status, t.created_at,
                       responder.username AS responder_name
                FROM tickets t
                JOIN users creator ON t.user_id = creator.id
                LEFT JOIN users responder ON t.responder_id = responder.id
                WHERE t.user_id = %s
                ORDER BY t.created_at DESC
                """,
                (session["user_id"],),
            )

            tickets = [
                dict(
                    id=row[0],
                    title=row[1],
                    description=row[2],
                    username=row[3],
                    status=row[4],
                    created_at=row[5],
                    responder=row[6] if row[6] else "NILL",
                )
                for row in cur.fetchall()
            ]

    return render_template("home.html", tickets=tickets)
