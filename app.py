from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from pathlib import Path
from datetime import datetime
import sqlite3

app = Flask(__name__)
app.secret_key = "replace-this-secret-before-deployment"
DB = Path(__file__).with_name("campuscare.db")
CATEGORIES = ["Classroom", "Library", "Wi-Fi / IT", "Sanitation", "Hostel", "Canteen", "Transport", "Other"]
STATUSES = ["Submitted", "In Progress", "Resolved"]

def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
          email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'student', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS complaints (
          id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE,
          user_id INTEGER NOT NULL, title TEXT NOT NULL, category TEXT NOT NULL,
          location TEXT, description TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Submitted',
          response TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)
        exists = db.execute("SELECT id FROM users WHERE email=?", ("admin@campuscare.local",)).fetchone()
        if not exists:
            db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                ("CampusCare Admin", "admin@campuscare.local", generate_password_hash("Admin@12345"), "admin", now()))

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("uid"):
            flash("Please log in first.", "info")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("uid"):
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

@app.context_processor
def globals_for_templates():
    return {"year": datetime.now().year, "categories": CATEGORIES, "statuses": STATUSES}

@app.route("/")
def home():
    if session.get("uid"):
        return redirect(url_for("admin") if session.get("role") == "admin" else url_for("dashboard"))
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name and email. Password must be at least 8 characters.", "error")
        else:
            try:
                with connect() as db:
                    db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'student',?)",
                               (name, email, generate_password_hash(password), now()))
                flash("Account created. Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.", "error")
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with connect() as db:
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.update(uid=user["id"], name=user["name"], role=user["role"])
            return redirect(url_for("admin") if user["role"] == "admin" else url_for("dashboard"))
        flash("Incorrect email or password.", "error")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have logged out.", "info")
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    if session.get("role") == "admin":
        return redirect(url_for("admin"))
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    sql = "SELECT * FROM complaints WHERE user_id=?"
    params = [session["uid"]]
    if q:
        sql += " AND (code LIKE ? OR title LIKE ? OR category LIKE ?)"
        params.extend([f"%{q}%"] * 3)
    if status in STATUSES:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY id DESC"
    with connect() as db:
        rows = db.execute(sql, params).fetchall()
        total = db.execute("SELECT COUNT(*) FROM complaints WHERE user_id=?", (session["uid"],)).fetchone()[0]
        pending = db.execute("SELECT COUNT(*) FROM complaints WHERE user_id=? AND status='Submitted'", (session["uid"],)).fetchone()[0]
        resolved = db.execute("SELECT COUNT(*) FROM complaints WHERE user_id=? AND status='Resolved'", (session["uid"],)).fetchone()[0]
    return render_template("dashboard.html", rows=rows, total=total, pending=pending, resolved=resolved, q=q, selected=status)

@app.route("/new", methods=["GET", "POST"])
@login_required
def new_complaint():
    if session.get("role") == "admin":
        return redirect(url_for("admin"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "")
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        if not title or category not in CATEGORIES or len(description) < 10:
            flash("Enter a title, valid category, and description of at least 10 characters.", "error")
        else:
            with connect() as db:
                cur = db.execute("""INSERT INTO complaints(user_id,title,category,location,description,status,created_at,updated_at)
                    VALUES(?,?,?,?,?,'Submitted',?,?)""",
                    (session["uid"], title, category, location, description, now(), now()))
                cid = cur.lastrowid
                code = f"CC-{datetime.now().strftime('%y')}-{cid:05d}"
                db.execute("UPDATE complaints SET code=? WHERE id=?", (code, cid))
            flash(f"Complaint submitted. Your reference ID is {code}.", "success")
            return redirect(url_for("detail", cid=cid))
    return render_template("new.html")

@app.route("/complaint/<int:cid>")
@login_required
def detail(cid):
    with connect() as db:
        item = db.execute("""SELECT c.*,u.name AS student_name,u.email AS student_email
            FROM complaints c JOIN users u ON u.id=c.user_id WHERE c.id=?""", (cid,)).fetchone()
    if not item:
        abort(404)
    if session.get("role") != "admin" and item["user_id"] != session["uid"]:
        abort(403)
    return render_template("detail.html", item=item)

@app.route("/admin")
@admin_required
def admin():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    category = request.args.get("category", "")
    sql = """SELECT c.*,u.name AS student_name FROM complaints c
             JOIN users u ON u.id=c.user_id WHERE 1=1"""
    params = []
    if q:
        sql += " AND (c.code LIKE ? OR c.title LIKE ? OR u.name LIKE ?)"
        params.extend([f"%{q}%"] * 3)
    if status in STATUSES:
        sql += " AND c.status=?"
        params.append(status)
    if category in CATEGORIES:
        sql += " AND c.category=?"
        params.append(category)
    sql += " ORDER BY c.id DESC"
    with connect() as db:
        rows = db.execute(sql, params).fetchall()
        total = db.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
        submitted = db.execute("SELECT COUNT(*) FROM complaints WHERE status='Submitted'").fetchone()[0]
        progress = db.execute("SELECT COUNT(*) FROM complaints WHERE status='In Progress'").fetchone()[0]
        resolved = db.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'").fetchone()[0]
    return render_template("admin.html", rows=rows, total=total, submitted=submitted, progress=progress,
                           resolved=resolved, q=q, selected=status, selected_category=category)

@app.route("/admin/update/<int:cid>", methods=["POST"])
@admin_required
def update(cid):
    status = request.form.get("status", "")
    response = request.form.get("response", "").strip()
    if status not in STATUSES:
        flash("Choose a valid status.", "error")
        return redirect(url_for("detail", cid=cid))
    with connect() as db:
        if not db.execute("SELECT id FROM complaints WHERE id=?", (cid,)).fetchone():
            abort(404)
        db.execute("UPDATE complaints SET status=?,response=?,updated_at=? WHERE id=?",
                   (status, response, now(), cid))
    flash("Complaint updated.", "success")
    return redirect(url_for("detail", cid=cid))

@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403, message="You do not have permission to view this page."), 403

@app.errorhandler(404)
def missing(_):
    return render_template("error.html", code=404, message="The requested page or complaint was not found."), 404

init_db()
if __name__ == "__main__":
    app.run(debug=True)
