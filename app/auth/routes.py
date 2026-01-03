from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import re

import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException

from ..common.db import get_cursor

bp = Blueprint("auth", __name__)

# ---------------- Register constants (same as original) ----------------
US_STATES = [
    ("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"), ("AR", "Arkansas"),
    ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"),
    ("DE", "Delaware"), ("FL", "Florida"), ("GA", "Georgia"),
    ("HI", "Hawaii"), ("ID", "Idaho"), ("IL", "Illinois"), ("IN", "Indiana"),
    ("IA", "Iowa"), ("KS", "Kansas"), ("KY", "Kentucky"), ("LA", "Louisiana"),
    ("ME", "Maine"), ("MD", "Maryland"), ("MA", "Massachusetts"),
    ("MI", "Michigan"), ("MN", "Minnesota"), ("MS", "Mississippi"),
    ("MO", "Missouri"), ("MT", "Montana"), ("NE", "Nebraska"),
    ("NV", "Nevada"), ("NH", "New Hampshire"), ("NJ", "New Jersey"),
    ("NM", "New Mexico"), ("NY", "New York"), ("NC", "North Carolina"),
    ("ND", "North Dakota"), ("OH", "Ohio"), ("OK", "Oklahoma"),
    ("OR", "Oregon"), ("PA", "Pennsylvania"), ("RI", "Rhode Island"),
    ("SC", "South Carolina"), ("SD", "South Dakota"), ("TN", "Tennessee"),
    ("TX", "Texas"), ("UT", "Utah"), ("VT", "Vermont"),
    ("VA", "Virginia"), ("WA", "Washington"),
    ("WV", "West Virginia"), ("WI", "Wisconsin"), ("WY", "Wyoming")
]
US_STATE_SET = {abbr for abbr, _ in US_STATES}


# ---------------- Login ----------------
@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        with get_cursor() as cur:
            cur.execute(
                """
                SELECT id, username, password, role, is_active
                FROM users
                WHERE username = %s
                LIMIT 1
                """,
                (username,),
            )
            user = cur.fetchone()

        # 1) username not found
        if not user:
            return render_template("login.html", error="Invalid username or password.")

        user_id, db_username, db_password_hash, role, is_active = user

        # 2) wrong password
        if not check_password_hash(db_password_hash, password):
            return render_template("login.html", error="Invalid username or password.")

        # 3) correct password but inactive
        if is_active == 0:
            session.clear()
            session["pending_reactivate"] = user_id
            return render_template("login.html", show_reactivate=True)

        # 4) correct password and active
        session.clear()
        session["user_id"] = user_id
        session["username"] = db_username
        session["role"] = role
        return redirect(url_for("main.home"))

    return render_template("login.html")


# ---------------- Register ----------------
@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        firstname = request.form.get("firstname", "").strip()
        lastname = request.form.get("lastname", "").strip()
        dob = request.form.get("dob", None)
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()

        address_line1 = request.form.get("address_line1", "").strip()
        address_line2 = request.form.get("address_line2", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        zip_code = request.form.get("zip_code", "").strip()

        phone_e164 = request.form.get("phone_e164", "").strip()
        profession = request.form.get("profession", "").strip()
        organization = request.form.get("organization", "").strip()
        organization_other = request.form.get("organization_other", "").strip()

        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "").strip()

        # --- Server-side validation (same messages as original) ---
        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match.", states=US_STATES)

        if state not in US_STATE_SET:
            return render_template("register.html", error="Invalid state selected.", states=US_STATES)

        if not re.match(r"^\d{5}(-\d{4})?$", zip_code):
            return render_template("register.html", error="Invalid ZIP code.", states=US_STATES)

        if organization == "Others" and not organization_other:
            return render_template(
                "register.html",
                error="Please specify your organization (Others).",
                states=US_STATES,
            )

        if not phone_e164:
            return render_template("register.html", error="Phone number is required.", states=US_STATES)

        try:
            parsed = phonenumbers.parse(phone_e164, None)
            if not phonenumbers.is_valid_number(parsed):
                return render_template("register.html", error="Invalid phone number.", states=US_STATES)
            phone_e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except NumberParseException:
            return render_template("register.html", error="Invalid phone number format.", states=US_STATES)

        if organization == "Others":
            organization = organization_other.strip()

        hashed_pwd = generate_password_hash(password)

        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (
                  firstname, lastname, dob,
                  address_line1, address_line2, city, state, zip_code,
                  username, email, phone_e164,
                  password, role,
                  profession, organization, organization_other
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    firstname, lastname, dob,
                    address_line1, address_line2, city, state, zip_code,
                    username, email, phone_e164,
                    hashed_pwd, role,
                    profession, organization, organization_other,
                ),
            )
            cur.connection.commit()

        return redirect(url_for("auth.login"))

    return render_template("register.html", states=US_STATES)


# ---------------- Logout ----------------
@bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.index"))


# ---------------- Reactivate ----------------
@bp.route("/reactivate", methods=["GET", "POST"])
def reactivate():
    if "pending_reactivate" not in session:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            return render_template(
                "reactivate.html",
                hide_nav_links=True,
                error="Username and password are required.",
            )

        with get_cursor() as cur:
            cur.execute(
                """
                SELECT id, username, password, is_active
                FROM users
                WHERE id=%s
                """,
                (session["pending_reactivate"],),
            )
            row = cur.fetchone()

            if not row:
                session.pop("pending_reactivate", None)
                return redirect(url_for("auth.login"))

            user_id, db_username, db_hash, is_active = row

            if username != db_username or not check_password_hash(db_hash, password):
                return render_template(
                    "reactivate.html",
                    hide_nav_links=True,
                    error="Invalid username or password.",
                )

            cur.execute("UPDATE users SET is_active=1 WHERE id=%s", (user_id,))
            cur.connection.commit()

        session.pop("pending_reactivate", None)
        return redirect(url_for("auth.login"))

    return render_template("reactivate.html", hide_nav_links=True)
