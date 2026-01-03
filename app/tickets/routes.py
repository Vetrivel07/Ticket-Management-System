from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session
from ..common.db import get_cursor

bp = Blueprint("tickets", __name__)

# ---------------- Create Ticket ----------------
@bp.route("/create_ticket", methods=["GET", "POST"])
def create_ticket():
    if "username" not in session or session.get("role") != "employee":
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        user_id = session["user_id"]
        now = datetime.now()

        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO tickets (user_id, title, description, status, created_at)
                VALUES (%s, %s, %s, 'pending', %s)
                """,
                (user_id, title, description, now),
            )
            cur.connection.commit()

        return redirect(url_for("main.home"))

    return render_template("create_ticket.html")


# ---------------- Update Ticket ----------------
@bp.route("/update_ticket/<int:ticket_id>", methods=["GET", "POST"])
def update_ticket(ticket_id: int):
    if "username" not in session or session.get("role") != "responder":
        return redirect(url_for("auth.login"))

    with get_cursor() as cur:
        if request.method == "POST":
            new_status = request.form["status"]

            if new_status == "declined":
                # 1) Log declined response per responder (idempotent)
                cur.execute(
                    """
                    INSERT INTO ticket_responder_log (ticket_id, responder_id, status)
                    VALUES (%s, %s, 'declined')
                    ON DUPLICATE KEY UPDATE status = 'declined'
                    """,
                    (ticket_id, session["user_id"]),
                )

                # 2) If this responder currently owns the ticket in-process, release it back to pending
                cur.execute(
                    """
                    UPDATE tickets
                    SET status = 'pending',
                        responder_id = NULL,
                        completed_at = NULL
                    WHERE id = %s
                      AND responder_id = %s
                      AND status = 'in process'
                    """,
                    (ticket_id, session["user_id"]),
                )
            else:
                # Update ticket with responder and possibly set completion time
                completed_at = datetime.now() if new_status == "done" else None
                cur.execute(
                    """
                    UPDATE tickets
                    SET status = %s,
                        responder_id = %s,
                        completed_at = %s
                    WHERE id = %s
                    """,
                    (new_status, session["user_id"], completed_at, ticket_id),
                )

            cur.connection.commit()
            return redirect(url_for("main.home"))

        # GET request – fetch ticket data
        cur.execute(
            """
            SELECT t.id, t.title, t.description, u.username, t.status
            FROM tickets t
            JOIN users u ON t.user_id = u.id
            WHERE t.id = %s
            """,
            (ticket_id,),
        )
        row = cur.fetchone()

    ticket = dict(id=row[0], title=row[1], description=row[2], username=row[3], status=row[4])
    return render_template("update_ticket.html", ticket=ticket)


# ---------------- Manage Tickets ----------------
@bp.get("/manage_tickets")
def manage_tickets():
    if "username" not in session or session.get("role") != "employee":
        return redirect(url_for("auth.login"))

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, title, description, status, created_at
            FROM tickets
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (session["user_id"],),
        )
        tickets = [
            dict(
                id=row[0],
                title=row[1],
                description=row[2],
                status=("Completed" if row[3] == "done" else row[3].capitalize()),
                created_at=row[4],
            )
            for row in cur.fetchall()
        ]

    return render_template("manage_tickets.html", tickets=tickets)


# ---------------- Edit Ticket ----------------
@bp.route("/edit_ticket/<int:ticket_id>", methods=["GET", "POST"])
def edit_ticket(ticket_id: int):
    if "username" not in session or session.get("role") != "employee":
        return redirect(url_for("auth.login"))

    with get_cursor() as cur:
        if request.method == "POST":
            title = request.form["title"]
            description = request.form["description"]
            cur.execute(
                "UPDATE tickets SET title = %s, description = %s WHERE id = %s AND user_id = %s",
                (title, description, ticket_id, session["user_id"]),
            )
            cur.connection.commit()
            return redirect(url_for("tickets.manage_tickets"))

        cur.execute(
            "SELECT title, description FROM tickets WHERE id = %s AND user_id = %s",
            (ticket_id, session["user_id"]),
        )
        ticket = cur.fetchone()

    if not ticket:
        return "Unauthorized access or ticket not found", 403

    return render_template("edit_ticket.html", ticket_id=ticket_id, ticket=ticket)


# ---------------- Delete Ticket ----------------
@bp.post("/delete_ticket/<int:ticket_id>")
def delete_ticket(ticket_id: int):
    if "username" not in session or session.get("role") != "employee":
        return redirect(url_for("auth.login"))

    with get_cursor() as cur:
        # fetch responder/status/title before delete
        cur.execute(
            """
            SELECT responder_id, status, title
            FROM tickets
            WHERE id = %s AND user_id = %s
            """,
            (ticket_id, session["user_id"]),
        )
        row = cur.fetchone()

        if not row:
            return "Ticket not found", 404

        responder_id, status, title = row

        # alert responder only if it was already being worked on / completed
        if responder_id and status in ("in process", "done"):
            employee_name = session.get("username", "Employee")
            subject = "Ticket deleted alert"
            body = f"{employee_name} deleted this ticket #{ticket_id} ({title}) while it was {status} by you."

            cur.execute(
                """
                INSERT INTO messages (message_type, sender_id, receiver_id, ticket_id, subject, body, is_read)
                VALUES ('alert', %s, %s, %s, %s, %s, 0)
                """,
                (session["user_id"], responder_id, ticket_id, subject, body),
            )

        cur.execute(
            "DELETE FROM tickets WHERE id = %s AND user_id = %s",
            (ticket_id, session["user_id"]),
        )
        cur.connection.commit()

    return redirect(url_for("tickets.manage_tickets"))
