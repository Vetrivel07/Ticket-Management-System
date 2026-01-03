from flask import Blueprint, render_template, request, redirect, url_for, session
from ..common.db import get_cursor

bp = Blueprint("messages", __name__)

@bp.get("/messages")
def messages():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
              m.id,
              m.message_type,
              COALESCE(u.username, 'System') AS sender_username,
              m.subject,
              m.body,
              m.is_read,
              m.created_at,
              m.ticket_id
            FROM messages m
            LEFT JOIN users u ON m.sender_id = u.id
            WHERE m.receiver_id = %s
            ORDER BY m.created_at DESC
            """,
            (session["user_id"],),
        )
        rows = cur.fetchall()

    inbox = [
        dict(
            id=r[0],
            message_type=r[1],
            sender=r[2],
            subject=r[3],
            body=r[4],
            is_read=r[5],
            created_at=r[6],
            ticket_id=r[7],
        )
        for r in rows
    ]

    return render_template("messages.html", messages=inbox)

@bp.post("/messages/<int:msg_id>/read")
def mark_message_read(msg_id: int):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE messages
            SET is_read = 1
            WHERE id = %s AND receiver_id = %s
            """,
            (msg_id, session["user_id"]),
        )
        cur.connection.commit()

    return redirect(url_for("messages.messages"))

@bp.post("/messages/read_all")
def mark_all_messages_read():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE messages
            SET is_read = 1
            WHERE receiver_id = %s AND is_read = 0
            """,
            (session["user_id"],),
        )
        cur.connection.commit()

    return redirect(url_for("messages.messages"))

@bp.post("/messages/send")
def send_message():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    receiver_id = request.form.get("receiver_id", type=int)
    subject = (request.form.get("subject") or "").strip()
    body = (request.form.get("body") or "").strip()

    if not receiver_id or not subject or not body:
        return "Missing fields", 400

    my_role = session.get("role")
    target_role = "responder" if my_role == "employee" else "employee"

    with get_cursor() as cur:
        cur.execute(
            "SELECT id FROM users WHERE id=%s AND role=%s AND is_active=1",
            (receiver_id, target_role),
        )
        ok = cur.fetchone()
        if not ok:
            return "Not allowed", 403

        cur.execute(
            """
            INSERT INTO messages (message_type, sender_id, receiver_id, ticket_id, subject, body, is_read)
            VALUES ('direct', %s, %s, NULL, %s, %s, 0)
            """,
            (session["user_id"], receiver_id, subject, body),
        )
        cur.connection.commit()

    return redirect(url_for("users.users_page"))
