from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash
import re

from ..common.db import get_cursor
from ..common.decorators import login_required
from ..auth.routes import US_STATES, US_STATE_SET  # reuse your existing constants

bp = Blueprint("account", __name__)

@bp.get("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]

    with get_cursor() as cur:
        # Fetch user info (same columns as original)
        cur.execute(
            """
            SELECT
              id, username, email, role,
              firstname, lastname, dob,
              address_line1, address_line2, city, state, zip_code,
              phone_e164, profession, organization
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )
        user = cur.fetchone()

        # Tickets section differs by role (same as original)
        if session.get("role") == "responder":
            cur.execute(
                """
                SELECT t.id, t.title, t.description, u.username, t.status, t.created_at
                FROM tickets t
                JOIN users u ON t.user_id = u.id
                WHERE t.responder_id = %s AND t.status = 'done'
                ORDER BY t.created_at DESC
                """,
                (user_id,),
            )
            done_tickets = cur.fetchall()

            cur.execute(
                """
                SELECT t.id, t.title, t.description, u.username, 'declined' AS status, log.created_at
                FROM ticket_responder_log log
                JOIN tickets t ON log.ticket_id = t.id
                JOIN users u ON t.user_id = u.id
                WHERE log.responder_id = %s AND log.status = 'declined'
                ORDER BY log.created_at DESC
                """,
                (user_id,),
            )
            declined_tickets = cur.fetchall()

            tickets = done_tickets + declined_tickets
        else:
            cur.execute(
                """
                SELECT id, title, description, status, created_at
                FROM tickets
                WHERE user_id = %s
                  AND status IN ('in process', 'done')
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            tickets = cur.fetchall()

    # error handling for deactivate modal (same mapping as original)
    err = request.args.get("err")
    deactivate_error = None
    if err == "bad_deactivate":
        deactivate_error = "Invalid username or password."
    elif err == "missing_deactivate":
        deactivate_error = "Username and password are required."

    return render_template(
        "dashboard.html",
        user=user,
        tickets=tickets,
        deactivate_error=deactivate_error,
    )

@bp.route("/edit_account", methods=["GET", "POST"])
@login_required
def edit_account():
    user_id = session["user_id"]

    def fetch_user_for_form(cur):
        cur.execute(
            """
            SELECT
              firstname, lastname, dob,
              address_line1, address_line2, city, state, zip_code,
              email, phone_e164, profession, organization
            FROM users
            WHERE id=%s
            """,
            (user_id,),
        )
        return cur.fetchone()

    with get_cursor() as cur:
        if request.method == "POST":
            firstname = request.form.get("firstname", "").strip()
            lastname  = request.form.get("lastname", "").strip()
            dob       = request.form.get("dob", None)

            address_line1 = request.form.get("address_line1", "").strip()
            address_line2 = request.form.get("address_line2", "").strip()
            city          = request.form.get("city", "").strip()
            state         = request.form.get("state", "").strip()
            zip_code      = request.form.get("zip_code", "").strip()

            email      = request.form.get("email", "").strip()
            phone_e164 = request.form.get("phone_e164", "").strip()
            profession = request.form.get("profession", "").strip()
            organization = request.form.get("organization", "").strip()
            organization_other = request.form.get("organization_other", "").strip()

            if organization == "Others":
                organization = organization_other.strip()

            # Validation (exactly like original)
            if state not in US_STATE_SET:
                user = fetch_user_for_form(cur)
                return render_template(
                    "edit_account.html",
                    user=user,
                    states=US_STATES,
                    error="Invalid state selected.",
                )

            if not re.match(r"^\d{5}(-\d{4})?$", zip_code):
                user = fetch_user_for_form(cur)
                return render_template(
                    "edit_account.html",
                    user=user,
                    states=US_STATES,
                    error="Invalid ZIP code.",
                )

            if not phone_e164:
                user = fetch_user_for_form(cur)
                return render_template(
                    "edit_account.html",
                    user=user,
                    states=US_STATES,
                    error="Phone number is required.",
                )

            # UPDATE only if validation passes
            cur.execute(
                """
                UPDATE users
                SET
                  firstname=%s, lastname=%s, dob=%s,
                  address_line1=%s, address_line2=%s, city=%s, state=%s, zip_code=%s,
                  email=%s, phone_e164=%s, profession=%s, organization=%s
                WHERE id=%s
                """,
                (
                    firstname, lastname, dob,
                    address_line1, address_line2, city, state, zip_code,
                    email, phone_e164, profession, organization,
                    user_id,
                ),
            )
            cur.connection.commit()
            return redirect(url_for("account.dashboard"))

        # GET request
        user = fetch_user_for_form(cur)

    return render_template("edit_account.html", user=user, states=US_STATES)

@bp.post("/delete_account")
@login_required
def delete_account():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    # Basic guard (same behavior, but original redirect has err mismatch; fix it cleanly)
    if not username or not password:
        return redirect(url_for("account.dashboard", err="missing_deactivate"))

    user_id = session["user_id"]

    with get_cursor() as cur:
        cur.execute(
            "SELECT id, username, password, is_active FROM users WHERE id=%s",
            (user_id,),
        )
        row = cur.fetchone()

        if not row:
            session.clear()
            return redirect(url_for("auth.login"))

        db_id, db_username, db_hash, _is_active = row

        if username != db_username or not check_password_hash(db_hash, password):
            return redirect(url_for("account.dashboard", err="bad_deactivate"))

        cur.execute("UPDATE users SET is_active=0 WHERE id=%s", (db_id,))
        cur.connection.commit()

    session.clear()
    return redirect(url_for("auth.login"))
