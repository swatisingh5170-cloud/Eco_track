from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
from functools import wraps
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

def get_db():
    return mysql.connector.connect(**config.DB_CONFIG)

# helper: require login decorator
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper

# helper: require admin decorator
def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        # Check if user is admin (you may want to add an 'is_admin' field to users table)
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT is_admin FROM users WHERE id=%s", (session['user_id'],))
        user = cursor.fetchone()
        cursor.close()
        db.close()
        if not user or not user.get('is_admin'):
            flash('Access denied', 'danger')
            return redirect(url_for('dashboard'))
        return fn(*args, **kwargs)
    return wrapper

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not name or not email or not password:
            flash('Fill all fields', 'danger')
            return redirect(url_for('signup'))

        if len(password) < 6:
            flash('Password must be at least 6 characters', 'danger')
            return redirect(url_for('signup'))

        hashed = generate_password_hash(password)
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute("INSERT INTO users (name, email, password) VALUES (%s,%s,%s)", (name, email, hashed))
            db.commit()
            flash('Signup successful. Please login.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('Email already registered', 'danger')
            return redirect(url_for('signup'))
        finally:
            cursor.close()
            db.close()
    return render_template('signup.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()
        db.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            flash('Logged in successfully', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out', 'info')
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    try:
        # total emissions
        cursor.execute("SELECT SUM(emission) AS total_emission FROM entries WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        total = result['total_emission'] or 0.0 if result else 0.0

        # recent entries
        cursor.execute("""
            SELECT e.id, e.amount, e.emission, e.entry_date, a.name AS activity_name, a.unit
            FROM entries e JOIN activities a ON e.activity_id = a.id
            WHERE e.user_id=%s ORDER BY e.entry_date DESC, e.created_at DESC LIMIT 20
        """, (user_id,))
        entries = cursor.fetchall()
    finally:
        cursor.close()
        db.close()
    
    return render_template('dashboard.html', total=round(total, 3), entries=entries)

@app.route('/add', methods=['GET','POST'])
@login_required
def add_entry():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    try:
        # fetch activities list
        cursor.execute("SELECT id, name, unit, factor FROM activities ORDER BY name")
        activities = cursor.fetchall()

        if request.method == 'POST':
            try:
                activity_id = int(request.form.get('activity', 0))
                amount_raw = request.form.get('amount', '')
                entry_date = request.form.get('entry_date') or str(date.today())

                if not activity_id or not amount_raw:
                    flash('Please select an activity and enter an amount', 'danger')
                    return redirect(url_for('add_entry'))

                try:
                    amount = float(amount_raw)
                    if amount <= 0:
                        raise ValueError('Amount must be positive')
                except ValueError:
                    flash('Enter a valid positive number for amount', 'danger')
                    return redirect(url_for('add_entry'))

                # get factor
                cursor.execute("SELECT factor FROM activities WHERE id=%s", (activity_id,))
                row = cursor.fetchone()
                if not row:
                    flash('Selected activity not found', 'danger')
                    return redirect(url_for('add_entry'))

                factor = row['factor']
                emission = amount * factor

                # insert
                cursor.execute(
                    "INSERT INTO entries (user_id, activity_id, amount, emission, entry_date) VALUES (%s,%s,%s,%s,%s)",
                    (session['user_id'], activity_id, amount, emission, entry_date)
                )
                db.commit()
                flash(f'Entry added — {round(emission, 3)} kg CO₂', 'success')
                return redirect(url_for('dashboard'))
            except Exception as e:
                flash(f'Error adding entry: {str(e)}', 'danger')
                return redirect(url_for('add_entry'))
    finally:
        cursor.close()
        db.close()
    
    return render_template('add_entry.html', activities=activities)

@app.route('/admin')
@admin_required
def admin():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT id, name, email, created_at FROM users ORDER BY created_at DESC")
        users = cursor.fetchall()
        
        # total footprints per user
        cursor.execute("""
            SELECT u.id AS user_id, u.name, u.email, COALESCE(SUM(e.emission), 0) AS total_emission
            FROM users u LEFT JOIN entries e ON u.id = e.user_id
            GROUP BY u.id ORDER BY total_emission DESC
        """)
        totals = cursor.fetchall()
    finally:
        cursor.close()
        db.close()
    
    return render_template('admin.html', users=users, totals=totals)

if __name__ == '__main__':
    app.run(debug=True)
