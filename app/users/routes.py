from flask import Blueprint, render_template, session, jsonify, redirect, url_for
from ..common.db import get_cursor

bp = Blueprint("users", __name__)

@bp.get("/users")
def users_page():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    my_role = session.get("role")
    target_role = "responder" if my_role == "employee" else "employee"

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, username, is_active
            FROM users
            WHERE role = %s
            ORDER BY username
            """,
            (target_role,),
        )
        users = cur.fetchall()

    return render_template("users.html", users=users, target_role=target_role)


@bp.get("/api/user/<int:uid>")
def api_user(uid: int):
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401

    my_role = session.get("role")
    target_role = "responder" if my_role == "employee" else "employee"

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
              id, username, firstname, lastname, email,
              address_line1, address_line2, city, state, zip_code,
              phone_e164, profession, organization, role, is_active
            FROM users
            WHERE id=%s AND role=%s
            """,
            (uid, target_role),
        )
        r = cur.fetchone()

    if not r:
        return jsonify({"error": "not_found"}), 404

    # index 14 is is_active
    if r[14] == 0:
        return jsonify({"inactive": True}), 200

    fullname = f"{(r[2] or '').strip()} {(r[3] or '').strip()}".strip()

    return jsonify(
        {
            "id": r[0],
            "username": r[1],
            "fullname": fullname,
            "email": r[4],
            "address_line1": r[5],
            "address_line2": r[6],
            "city": r[7],
            "state": r[8],
            "zip_code": r[9],
            "phone": r[10],
            "profession": r[11],
            "organization": r[12],
            "role": r[13],
            "is_active": r[14],
        }
    )
