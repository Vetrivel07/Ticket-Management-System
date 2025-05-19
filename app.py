from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secret_key'

# MySQL Configuration

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Irtev'
app.config['MYSQL_DB'] = 'ticket_system'

mysql = MySQL(app)

# ---------------- Home Page ----------------

@app.route('/')
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
            WHERE t.status != 'completed'
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
            status='pending' if row[4] == 'declined' else row[4],
            created_at=row[5],
            responder=row[6] if row[6] else "NILL"
        ) for row in cur.fetchall()]

    cur.close()
    return render_template("home.html", tickets=tickets)


# ---------------- Login ----------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT id, username, password, role FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[3]
            return redirect(url_for('home'))
        else:
            return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")

# ---------------- Register ----------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        dob = request.form['dob']
        address = request.form['address']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        hashed_pwd = generate_password_hash(password)

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO users (firstname, lastname, dob, address, username, email, password, role)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (firstname, lastname, dob, address, username, email, hashed_pwd, role))
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('login'))

    return render_template("register.html")



# ---------------- Logout ----------------

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------------- Dashboard ----------------

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # Fetch user info
    cur.execute("""
    SELECT id, username, email, role, firstname, lastname, dob, address 
    FROM users WHERE id = %s
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
        tickets = cur.fetchall()
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
    return render_template("dashboard.html", user=user, tickets=tickets)

# ---------------- Edit Account ----------------

@app.route('/edit_account', methods=['GET', 'POST'])
def edit_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        dob = request.form['dob']
        address = request.form['address']
        email = request.form['email']

        cur.execute("""
            UPDATE users 
            SET firstname = %s, lastname = %s, dob = %s, address = %s, email = %s 
            WHERE id = %s
        """, (firstname, lastname, dob, address, email, session['user_id']))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('dashboard'))

    cur.execute("""
        SELECT firstname, lastname, dob, address, email 
        FROM users 
        WHERE id = %s
    """, (session['user_id'],))
    user = cur.fetchone()
    cur.close()

    return render_template('edit_account.html', user=user)


# ---------------- Delete Account ----------------

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM tickets WHERE user_id = %s", (session['user_id'],))  # optional: remove tickets
    cur.execute("DELETE FROM users WHERE id = %s", (session['user_id'],))
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

from datetime import datetime

@app.route('/update_ticket/<int:ticket_id>', methods=['GET', 'POST'])
def update_ticket(ticket_id):
    if 'username' not in session or session['role'] != 'responder':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        new_status = request.form['status']

        if new_status == 'declined':
            # Log declined response per responder
            cur.execute("""
                INSERT INTO ticket_responder_log (ticket_id, responder_id, status)
                VALUES (%s, %s, 'declined')
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
        status='NILL' if row[3] == 'declined' else ('Completed' if row[3] == 'done' else row[3].capitalize()),
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

@app.route('/delete_ticket/<int:ticket_id>', methods=['POST'])
def delete_ticket(ticket_id):
    if 'username' not in session or session['role'] != 'employee':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM tickets WHERE id = %s AND user_id = %s", (ticket_id, session['user_id']))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('manage_tickets'))


# ---------------- List Users ----------------

@app.route('/users')
def users():
    if 'username' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, username, email, role FROM users")
    users = [dict(id=row[0], username=row[1], email=row[2], role=row[3]) for row in cur.fetchall()]
    cur.close()

    return render_template("users.html", users=users)

# ---------------- Run Server ----------------

if __name__ == '__main__':
    app.run(debug=True)
