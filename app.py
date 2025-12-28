from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import re
import os
import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException
from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'secret_key')

# MySQL Configuration

app.config['MYSQL_HOST'] = os.environ['DB_HOST']
app.config['MYSQL_USER'] = os.environ['DB_USER']
app.config['MYSQL_PASSWORD'] = os.environ['DB_PASSWORD']
app.config['MYSQL_DB'] = os.environ['DB_NAME']
app.config['MYSQL_PORT'] = int(os.environ.get('DB_PORT', 3306))
app.config['MYSQL_SSL'] = {'ssl': True}

mysql = MySQL(app)

# ---------------- Index Page ----------------

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return render_template('index.html')

@app.context_processor
def inject_year():
    from datetime import datetime
    return {"current_year": datetime.now().year}


# ---------------- Home Page ----------------

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # ---------------- Responder View ----------------
    if session['role'] == 'responder':
        cur.execute("""
            SELECT t.id, t.title, t.description, u.username AS creator_name, 
                   t.status, t.created_at, r.username AS responder_name
            FROM tickets t
            JOIN users u ON t.user_id = u.id
            LEFT JOIN users r ON t.responder_id = r.id
            WHERE t.status != 'done'
              AND (t.responder_id IS NULL OR t.responder_id = %s)
              AND NOT EXISTS (
                  SELECT 1 FROM ticket_responder_log log
                  WHERE log.ticket_id = t.id AND log.responder_id = %s AND log.status = 'declined'
              )
            ORDER BY t.created_at DESC
        """, (session['user_id'], session['user_id']))

        tickets = [dict(
            id=row[0],
            title=row[1],
            description=row[2],
            username=row[3],
            status=row[4],
            created_at=row[5],
            responder=row[6] if row[6] else "NILL"
        ) for row in cur.fetchall()]

    # ---------------- Employee View ----------------
    else:
        cur.execute("""
            SELECT t.id, t.title, t.description, creator.username AS creator_name,
                   t.status, t.created_at,
                   responder.username AS responder_name
            FROM tickets t
            JOIN users creator ON t.user_id = creator.id
            LEFT JOIN users responder ON t.responder_id = responder.id
            WHERE t.user_id = %s
            ORDER BY t.created_at DESC
        """, (session['user_id'],))

        tickets = [dict(
            id=row[0],
            title=row[1],
            description=row[2],
            username=row[3],
            status=row[4],
            created_at=row[5],
            responder=row[6] if row[6] else "NILL"
        ) for row in cur.fetchall()]

    cur.close()
    return render_template("home.html", tickets=tickets)


# ---------------- Login ----------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''

        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, username, password, role, is_active
            FROM users
            WHERE username = %s
            LIMIT 1
        """, (username,))
        user = cur.fetchone()
        cur.close()

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
            session['pending_reactivate'] = user_id
            return render_template(
                "login.html",
                show_reactivate=True
            )

        # 4) correct password and active
        session.clear()
        session['user_id'] = user_id
        session['username'] = db_username
        session['role'] = role
        return redirect(url_for('home'))

    return render_template("login.html")


# ---------------- Register ----------------
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


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        firstname = request.form.get('firstname', '').strip()
        lastname = request.form.get('lastname', '').strip()
        dob = request.form.get('dob', None)
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()

        address_line1 = request.form.get('address_line1', '').strip()
        address_line2 = request.form.get('address_line2', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        zip_code = request.form.get('zip_code', '').strip()
        
        phone_e164 = request.form.get('phone_e164', '').strip()
        profession = request.form.get('profession', '').strip()
        organization = request.form.get('organization', '').strip()
        organization_other = request.form.get('organization_other', '').strip()

        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', '').strip()        

        # --- Server-side validation ---
        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match.", states=US_STATES)
    
        if state not in US_STATE_SET:
            return render_template("register.html", error="Invalid state selected.", states=US_STATES)

        if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
            return render_template("register.html", error="Invalid ZIP code.", states=US_STATES)

        if organization == "Others" and not organization_other:
            return render_template("register.html", error="Please specify your organization (Others).", states=US_STATES)

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

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO users (
              firstname, lastname, dob, 
              address_line1, address_line2, city, state, zip_code,
              username, email, phone_e164,
              password, role,
              profession, organization, organization_other
            )
             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            firstname, lastname, dob,
            address_line1, address_line2, city, state, zip_code,
            username, email, phone_e164,
            hashed_pwd, role,
            profession, organization, organization_other
        ))
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('login'))

    return render_template("register.html",states=US_STATES)


# ---------------- Logout ----------------

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# ---------------- Dashboard ----------------

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # Fetch user info
    cur.execute("""
    SELECT
      id, username, email, role,
      firstname, lastname, dob,
      address_line1, address_line2, city, state, zip_code,
      phone_e164, profession, organization
    FROM users
    WHERE id = %s
    """, (session['user_id'],))
    user = cur.fetchone()


    if session['role'] == 'responder':
        # Fetch DONE tickets handled by responder
        cur.execute("""
            SELECT t.id, t.title, t.description, u.username, t.status, t.created_at
            FROM tickets t
            JOIN users u ON t.user_id = u.id
            WHERE t.responder_id = %s AND t.status = 'done'
            ORDER BY t.created_at DESC
        """, (session['user_id'],))
        done_tickets  = cur.fetchall()

         # DECLINED tickets (per-responder)
        cur.execute("""
            SELECT t.id, t.title, t.description, u.username, 'declined' AS status, log.created_at
            FROM ticket_responder_log log
            JOIN tickets t ON log.ticket_id = t.id
            JOIN users u ON t.user_id = u.id
            WHERE log.responder_id = %s AND log.status = 'declined'
            ORDER BY log.created_at DESC
        """, (session['user_id'],))

        declined_tickets = cur.fetchall()

        tickets = done_tickets + declined_tickets

    else:
        # Fetch ALL tickets posted by the employee
        cur.execute("""
        SELECT id, title, description, status, created_at
        FROM tickets
        WHERE user_id = %s
        AND status IN ('in process', 'done')
        ORDER BY created_at DESC
        """, (session['user_id'],))
        tickets = cur.fetchall()

    cur.close()

    # error handling for deactivate modal
    err = request.args.get('err')
    deactivate_error = None
    if err == "bad_deactivate":
        deactivate_error = "Invalid username or password."
    elif err == "missing_deactivate":
        deactivate_error = "Username and password are required."

    return render_template("dashboard.html", user=user, tickets=tickets, deactivate_error=deactivate_error)


# ---------------- Edit Account ----------------

@app.route('/edit_account', methods=['GET', 'POST'])
def edit_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        # 1) Read form data
        firstname = request.form.get('firstname', '').strip()
        lastname  = request.form.get('lastname', '').strip()
        dob       = request.form.get('dob', None)

        address_line1 = request.form.get('address_line1', '').strip()
        address_line2 = request.form.get('address_line2', '').strip()
        city          = request.form.get('city', '').strip()
        state         = request.form.get('state', '').strip()
        zip_code      = request.form.get('zip_code', '').strip()

        email      = request.form.get('email', '').strip()
        phone_e164 = request.form.get('phone_e164', '').strip()
        profession = request.form.get('profession', '').strip()
        organization = request.form.get('organization', '').strip()
        organization_other = request.form.get('organization_other', '').strip()

        if organization == "Others":
            organization = organization_other.strip()

        # 2) Validation (before UPDATE)
        if state not in US_STATE_SET:
            cur.execute("""SELECT
              firstname, lastname, dob,
              address_line1, address_line2, city, state, zip_code,
              email, phone_e164, profession, organization
              FROM users WHERE id=%s""", (session['user_id'],))
            user = cur.fetchone()
            cur.close()
            return render_template(
                'edit_account.html',
                user=user,
                states=US_STATES,
                error="Invalid state selected."
            )

        if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
            cur.execute("""SELECT
              firstname, lastname, dob,
              address_line1, address_line2, city, state, zip_code,
              email, phone_e164, profession, organization
              FROM users WHERE id=%s""", (session['user_id'],))
            user = cur.fetchone()
            cur.close()
            return render_template(
                'edit_account.html',
                user=user,
                states=US_STATES,
                error="Invalid ZIP code."
            )

        if not phone_e164:
            cur.execute("""SELECT
              firstname, lastname, dob,
              address_line1, address_line2, city, state, zip_code,
              email, phone_e164, profession, organization
              FROM users WHERE id=%s""", (session['user_id'],))
            user = cur.fetchone()
            cur.close()
            return render_template(
                'edit_account.html',
                user=user,
                states=US_STATES,
                error="Phone number is required."
            )

        # 3) UPDATE only if validation passes
        cur.execute("""
            UPDATE users
            SET
              firstname=%s, lastname=%s, dob=%s,
              address_line1=%s, address_line2=%s, city=%s, state=%s, zip_code=%s,
              email=%s, phone_e164=%s, profession=%s, organization=%s
            WHERE id=%s
        """, (
            firstname, lastname, dob,
            address_line1, address_line2, city, state, zip_code,
            email, phone_e164, profession, organization,
            session['user_id']
        ))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('dashboard'))

    # GET request
    cur.execute("""
        SELECT
          firstname, lastname, dob,
          address_line1, address_line2, city, state, zip_code,
          email, phone_e164, profession, organization
        FROM users WHERE id=%s
    """, (session['user_id'],))
    user = cur.fetchone()
    cur.close()

    return render_template('edit_account.html', user=user, states=US_STATES)

# ---------------- Delete Account ----------------


@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''

    # Basic guard
    if not username or not password:
        return redirect(url_for('dashboard', err='bad_deactivate'))


    cur = mysql.connection.cursor()
    cur.execute("SELECT id, username, password, is_active FROM users WHERE id=%s", (session['user_id'],))
    row = cur.fetchone()

    if not row:
        cur.close()
        session.clear()
        return redirect(url_for('login'))

    user_id, db_username, db_hash, is_active = row

    # Must match the logged-in account + correct password
    if username != db_username or not check_password_hash(db_hash, password):
        cur.close()
        return redirect(url_for('dashboard', err='bad_deactivate'))

    # Deactivate
    cur.execute("UPDATE users SET is_active=0 WHERE id=%s", (user_id,))
    mysql.connection.commit()
    cur.close()

    session.clear()
    return redirect(url_for('login'))


# ---------------- Create Ticket ----------------

@app.route('/create_ticket', methods=['GET', 'POST'])
def create_ticket():
    if 'username' not in session or session['role'] != 'employee':
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        user_id = session['user_id']
        now = datetime.now()

        cur = mysql.connection.cursor()
        cur.execute("""
    INSERT INTO tickets (user_id, title, description, status, created_at)
    VALUES (%s, %s, %s, 'pending', %s)
""", (user_id, title, description, now))

        mysql.connection.commit()
        cur.close()

        return redirect(url_for('home'))

    return render_template("create_ticket.html")


# ---------------- Update Ticket ----------------

@app.route('/update_ticket/<int:ticket_id>', methods=['GET', 'POST'])
def update_ticket(ticket_id):
    if 'username' not in session or session['role'] != 'responder':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        new_status = request.form['status']

        if new_status == 'declined':
             # 1) Log declined response per responder (idempotent)
            cur.execute("""
                INSERT INTO ticket_responder_log (ticket_id, responder_id, status)
                VALUES (%s, %s, 'declined')
                ON DUPLICATE KEY UPDATE status = 'declined'
            """, (ticket_id, session['user_id']))
            # 2) If this responder currently owns the ticket in-process, release it back to pending
            cur.execute("""
                UPDATE tickets
                SET status = 'pending',
                    responder_id = NULL,
                    completed_at = NULL
                WHERE id = %s
                AND responder_id = %s
                AND status = 'in process'
            """, (ticket_id, session['user_id']))

        else:
            # Update ticket with responder and possibly set completion time
            completed_at = datetime.now() if new_status == 'done' else None
            cur.execute("""
                UPDATE tickets
                SET status = %s,
                    responder_id = %s,
                    completed_at = %s
                WHERE id = %s
            """, (new_status, session['user_id'], completed_at, ticket_id))

        mysql.connection.commit()
        cur.close()
        return redirect(url_for('home'))

    # GET request – fetch ticket data
    cur.execute("""
        SELECT t.id, t.title, t.description, u.username, t.status
        FROM tickets t
        JOIN users u ON t.user_id = u.id
        WHERE t.id = %s
    """, (ticket_id,))
    row = cur.fetchone()
    ticket = dict(id=row[0], title=row[1], description=row[2], username=row[3], status=row[4])
    cur.close()

    return render_template("update_ticket.html", ticket=ticket)


# ---------------- Manage Ticket ----------------

@app.route('/manage_tickets')
def manage_tickets():
    if 'username' not in session or session['role'] != 'employee':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, title, description, status, created_at
        FROM tickets
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (session['user_id'],))
    tickets = [dict(
        id=row[0],
        title=row[1],
        description=row[2],
        status= ('Completed' if row[3] == 'done' else row[3].capitalize()),
        created_at=row[4]
    ) for row in cur.fetchall()]
    cur.close()

    return render_template("manage_tickets.html", tickets=tickets)


# ---------------- Edit Ticket ----------------

@app.route('/edit_ticket/<int:ticket_id>', methods=['GET', 'POST'])
def edit_ticket(ticket_id):
    if 'username' not in session or session['role'] != 'employee':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        cur.execute("UPDATE tickets SET title = %s, description = %s WHERE id = %s AND user_id = %s",
                    (title, description, ticket_id, session['user_id']))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('manage_tickets'))

    cur.execute("SELECT title, description FROM tickets WHERE id = %s AND user_id = %s",
                (ticket_id, session['user_id']))
    ticket = cur.fetchone()
    cur.close()
    if not ticket:
        return "Unauthorized access or ticket not found", 403

    return render_template("edit_ticket.html", ticket_id=ticket_id, ticket=ticket)

# ---------------- Delete Ticket ----------------

@app.route('/delete_ticket/<int:ticket_id>', methods=['POST'])
def delete_ticket(ticket_id):
    if 'username' not in session or session['role'] != 'employee':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # fetch responder/status/title before delete
    cur.execute("""
        SELECT responder_id, status, title
        FROM tickets
        WHERE id = %s AND user_id = %s
    """, (ticket_id, session['user_id']))
    row = cur.fetchone()

    if not row:
        cur.close()
        return "Ticket not found", 404

    responder_id, status, title = row

    # alert responder only if it was already being worked on / completed
    if responder_id and status in ('in process', 'done'):
        employee_name = session.get('username', 'Employee')
        subject = "Ticket deleted alert"
        body = f"{employee_name} deleted this ticket #{ticket_id} ({title}) while it was {status} by you."

        cur.execute("""
            INSERT INTO messages (message_type, sender_id, receiver_id, ticket_id, subject, body, is_read)
            VALUES ('alert', %s, %s, %s, %s, %s, 0)
        """, (session['user_id'], responder_id, ticket_id, subject, body))

    cur.execute("DELETE FROM tickets WHERE id = %s AND user_id = %s", (ticket_id, session['user_id']))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('manage_tickets'))


# ---------------- List Users ----------------

@app.route('/users')
def users():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    my_role = session.get('role')
    target_role = 'responder' if my_role == 'employee' else 'employee'

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, username, is_active
        FROM users
        WHERE role = %s
        ORDER BY username
    """, (target_role,))
    users = cur.fetchall()
    cur.close()

    return render_template("users.html", users=users, target_role=target_role)


@app.route('/api/user/<int:uid>')
def api_user(uid):
    if 'user_id' not in session:
        return jsonify({"error":"unauthorized"}), 401

    my_role = session.get('role')
    target_role = 'responder' if my_role == 'employee' else 'employee'

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT
          id, username, firstname, lastname, email,
          address_line1, address_line2, city, state, zip_code,
          phone_e164, profession, organization, role, is_active
        FROM users
        WHERE id=%s AND role=%s
    """, (uid, target_role))
    r = cur.fetchone()
    cur.close()

    if not r:
        return jsonify({"error":"not_found"}), 404
    
    if r[14] == 0:
        return jsonify({"inactive": True}), 200

    return jsonify({
        "id": r[0],
        "username": r[1],
        "fullname": f"{(r[2] or '').strip()} {(r[3] or '').strip()}".strip(),
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
    })

@app.route('/messages/send', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    receiver_id = request.form.get('receiver_id', type=int)
    subject = (request.form.get('subject') or '').strip()
    body = (request.form.get('body') or '').strip()

    if not receiver_id or not subject or not body:
        return "Missing fields", 400

    my_role = session.get('role')
    target_role = 'responder' if my_role == 'employee' else 'employee'

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM users WHERE id=%s AND role=%s AND is_active=1", (receiver_id, target_role))
    ok = cur.fetchone()
    if not ok:
        cur.close()
        return "Not allowed", 403

    cur.execute("""
        INSERT INTO messages (message_type, sender_id, receiver_id, ticket_id, subject, body, is_read)
        VALUES ('direct', %s, %s, NULL, %s, %s, 0)
    """, (session['user_id'], receiver_id, subject, body))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('users'))


@app.route('/reactivate', methods=['GET','POST'])
def reactivate():
    if 'pending_reactivate' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''

        if not username or not password:
            return render_template(
                'reactivate.html',
                hide_nav_links=True,
                error="Username and password are required."
            )

        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, username, password, is_active
            FROM users
            WHERE id=%s
        """, (session['pending_reactivate'],))
        row = cur.fetchone()

        if not row:
            cur.close()
            session.pop('pending_reactivate', None)
            return redirect(url_for('login'))

        user_id, db_username, db_hash, is_active = row

        # Must match the same account + correct password
        if username != db_username or not check_password_hash(db_hash, password):
            cur.close()
            return render_template(
                'reactivate.html',
                hide_nav_links=True,
                error="Invalid username or password."
            )

        # Reactivate
        cur.execute("UPDATE users SET is_active=1 WHERE id=%s", (user_id,))
        mysql.connection.commit()
        cur.close()

        session.pop('pending_reactivate', None)
        return redirect(url_for('login'))

    return render_template('reactivate.html', hide_nav_links=True)



# ---------------- Message Section ----------------

@app.context_processor
def inject_unread_count():
    if 'user_id' not in session:
        return dict(unread_count=0)

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM messages WHERE receiver_id=%s AND is_read=0",
        (session['user_id'],)
    )
    count = cur.fetchone()[0]
    cur.close()
    return dict(unread_count=count)

@app.route('/messages')
def messages():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
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
    """, (session['user_id'],))
    rows = cur.fetchall()
    cur.close()

    inbox = [dict(
        id=r[0],
        message_type=r[1],
        sender=r[2],
        subject=r[3],
        body=r[4],
        is_read=r[5],
        created_at=r[6],
        ticket_id=r[7]
    ) for r in rows]

    return render_template('messages.html', messages=inbox)

@app.route('/messages/<int:msg_id>/read', methods=['POST'])
def mark_message_read(msg_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE messages
        SET is_read = 1
        WHERE id = %s AND receiver_id = %s
    """, (msg_id, session['user_id']))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('messages'))


@app.route('/messages/read_all', methods=['POST'])
def mark_all_messages_read():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE messages
        SET is_read = 1
        WHERE receiver_id = %s AND is_read = 0
    """, (session['user_id'],))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('messages'))


# ---------------- Run Server ----------------

if __name__ == '__main__':
    app.run(debug=True)
