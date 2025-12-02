# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

# Config
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev_secret")
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# DB helper
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", "waste_management")
    )

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Routes
@app.route('/')
def index():
    return render_template('index.html')

# ===== Register =====
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name').strip()
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        if not (name and email and password):
            flash("Please fill all fields", "warning")
            return redirect(url_for('register'))

        password_hash = generate_password_hash(password)
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)", (name, email, password_hash))
            conn.commit()
            cursor.close()
            conn.close()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for('login'))
        except Error as e:
            # simple error handling
            flash(f"Error: {e}", "danger")
            return redirect(url_for('register'))

    return render_template('register.html')

# ===== Login =====
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['role'] = user['role']
            flash("Logged in successfully.", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid email or password.", "danger")
            return redirect(url_for('login'))
    return render_template('login.html')

# ===== Logout =====
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))

# ===== Submit report =====
@app.route('/report', methods=['GET', 'POST'])
def report():
    if request.method == 'POST':
        if 'user_id' not in session:
            flash("Please login to submit a report.", "warning")
            return redirect(url_for('login'))

        waste_type = request.form.get('waste_type')
        description = request.form.get('description')
        lat = request.form.get('lat') or None
        lng = request.form.get('lng') or None

        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(save_path)
                image_filename = filename

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO reports (user_id, image, latitude, longitude, waste_type, description) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (session['user_id'], image_filename, lat, lng, waste_type, description)
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash("Report submitted. Thank you!", "success")
            return redirect(url_for('index'))
        except Error as e:
            flash(f"Database error: {e}", "danger")
            return redirect(url_for('report'))

    return render_template('report.html')

# ===== View reports (simple dashboard) =====
@app.route('/reports')
def reports():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT r.*, u.name as reporter FROM reports r LEFT JOIN users u ON r.user_id = u.id ORDER BY r.created_at DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('reports.html', reports=rows)

# ===== Serve uploaded images (optional) =====
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Run app
if __name__ == '__main__':
    app.run(debug=True)

# --- Paste or update inside app.py ---

import uuid
from datetime import datetime

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB

def secure_unique_filename(filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    return f"{uuid.uuid4().hex}.{ext}"

def file_too_large(file_obj):
    # file_obj is a Werkzeug FileStorage
    file_obj.seek(0, 2)  # seek to end
    size = file_obj.tell()
    file_obj.seek(0)
    return size > MAX_UPLOAD_SIZE

@app.route('/report', methods=['GET', 'POST'])
def report():
    if request.method == 'POST':
        if 'user_id' not in session:
            flash("Please login to submit a report.", "warning")
            return redirect(url_for('login'))

        waste_type = request.form.get('waste_type', '').strip()
        description = request.form.get('description', '').strip()
        lat = request.form.get('lat') or None
        lng = request.form.get('lng') or None

        image_filename = None
        file = request.files.get('image')
        if file and file.filename:
            if not allowed_file(file.filename):
                flash("Only image files (png,jpg,jpeg,gif) are allowed.", "danger")
                return redirect(url_for('report'))

            if file_too_large(file):
                flash("Image too large. Max size is 5 MB.", "danger")
                return redirect(url_for('report'))

            filename = secure_unique_filename(secure_filename(file.filename))
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)
            image_filename = filename

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO reports (user_id, image, latitude, longitude, waste_type, description) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (session['user_id'], image_filename, lat, lng, waste_type, description)
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash("Report submitted. Thank you!", "success")
            return redirect(url_for('dashboard'))  # go to user dashboard
        except Error as e:
            flash(f"Database error: {e}", "danger")
            return redirect(url_for('report'))

    # GET: show form
    return render_template('report.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please login.", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM reports WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('dashboard.html', reports=rows)

def is_admin():
    return session.get('role') == 'admin'

@app.route('/admin/reports', methods=['GET', 'POST'])
def admin_reports():
    if not is_admin():
        flash("Admin access required.", "danger")
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # update status
        report_id = request.form.get('report_id')
        new_status = request.form.get('new_status')
        cursor.execute("UPDATE reports SET status=%s WHERE id=%s", (new_status, report_id))
        conn.commit()
        flash("Status updated.", "success")

    cursor.execute("SELECT r.*, u.name as reporter FROM reports r LEFT JOIN users u ON r.user_id = u.id ORDER BY r.created_at DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin_reports.html', reports=rows)

import os

def delete_report_file(filename):
    if not filename:
        return
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(path):
        os.remove(path)
