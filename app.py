import os
import io
import csv
import base64
import secrets
import sqlite3

from datetime import datetime, timedelta

import qrcode
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response


# =========================================================
# SMARTATTEND - QR ATTENDANCE SYSTEM
# =========================================================
# This project intentionally stays simple:
# Flask + SQLite + QR codes + HTML/CSS/JavaScript.
# It is suitable for a hackathon and can be deployed on Render.
# =========================================================

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-in-production")
DB = os.environ.get("DB_PATH", "attendance.db")


# =========================================================
# DATABASE HELPERS
# =========================================================

def get_db():
    """Open SQLite and return rows like dictionaries."""
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables. Existing databases are preserved."""
    conn = get_db()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_no TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                class_name TEXT DEFAULT 'CSE-A',
                token TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                marked_at TEXT NOT NULL,
                UNIQUE(student_id, session_id),
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
            """
        )

        # Existing databases from the previous version may not have class_name.
        columns = [row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()]
        if "class_name" not in columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN class_name TEXT DEFAULT 'CSE-A'")

        conn.commit()
    finally:
        conn.close()


init_db()


# =========================================================
# SMALL UTILITY FUNCTIONS
# =========================================================

def now_local():
    """Keep timestamps consistent throughout the application."""
    return datetime.now()


def session_is_active(session):
    """Return True when the QR session is still inside its time window."""
    return now_local() <= datetime.fromisoformat(session["expires_at"])


def session_qr_base64(session):
    """Generate one QR image for a session and return base64 data."""
    qr_url = url_for("mark_attendance", token=session["token"], _external=True)
    img = qrcode.make(qr_url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


app.jinja_env.globals["session_is_active"] = session_is_active


def get_session_stats(conn, session_id):
    """Calculate live present/total numbers for one session."""
    total = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    present = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE session_id = ?", (session_id,)
    ).fetchone()[0]
    percentage = round((present * 100 / total), 1) if total else 0
    return total, present, percentage


def get_dashboard_data(conn):
    """Build the numbers shown on the premium teacher dashboard."""
    total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

    today = now_local().date().isoformat()
    today_present = conn.execute(
        """
        SELECT COUNT(*) FROM attendance
        WHERE substr(marked_at, 1, 10) = ?
        """,
        (today,),
    ).fetchone()[0]

    # Calculate each student's overall attendance.
    risk_rows = conn.execute(
        """
        SELECT
            s.id, s.roll_no, s.name,
            COUNT(DISTINCT se.id) AS total_sessions,
            COUNT(DISTINCT a.session_id) AS present_sessions
        FROM students s
        LEFT JOIN sessions se ON 1 = 1
        LEFT JOIN attendance a
            ON a.student_id = s.id AND a.session_id = se.id
        GROUP BY s.id
        ORDER BY s.roll_no
        """
    ).fetchall()

    risk_students = []
    percentages = []
    for row in risk_rows:
        total = row["total_sessions"] or 0
        present = row["present_sessions"] or 0
        pct = (present * 100 / total) if total else 0
        percentages.append(pct)
        if total and pct < 75:
            risk_students.append({"name": row["name"], "roll_no": row["roll_no"], "percentage": round(pct, 1)})

    # Today's attendance percentage is based on the total students.
    today_percentage = round((today_present * 100 / total_students), 1) if total_students else 0

    # Latest sessions are displayed on the dashboard.
    sessions = conn.execute(
        "SELECT * FROM sessions ORDER BY id DESC LIMIT 6"
    ).fetchall()

    return {
        "total_students": total_students,
        "total_sessions": total_sessions,
        "today_present": today_present,
        "today_percentage": today_percentage,
        "risk_students": risk_students,
        "sessions": sessions,
    }


# =========================================================
# HOME / STUDENT MANAGEMENT
# =========================================================

@app.route("/")
def index():
    conn = get_db()
    try:
        students = conn.execute("SELECT * FROM students ORDER BY roll_no").fetchall()
    finally:
        conn.close()
    return render_template("index.html", students=students)


@app.route("/add_student", methods=["POST"])
def add_student():
    roll_no = request.form.get("roll_no", "").strip()
    name = request.form.get("name", "").strip()

    if not roll_no or not name:
        flash("Enter both roll number and name.", "error")
        return redirect(url_for("index"))

    conn = get_db()
    try:
        conn.execute("INSERT INTO students (roll_no, name) VALUES (?, ?)", (roll_no, name))
        conn.commit()
        flash("Student added successfully.", "success")
    except sqlite3.IntegrityError:
        flash("That roll number already exists.", "error")
    finally:
        conn.close()
    return redirect(url_for("index"))


# =========================================================
# TEACHER DASHBOARD
# =========================================================

@app.route("/teacher")
def teacher():
    """
    Teacher dashboard entry point.

    IMPORTANT:
    The premium teacher.html template expects one variable named
    `data`, so we pass the complete dashboard dictionary as
    `data=data` instead of expanding it with **data.
    """
    conn = get_db()
    try:
        data = get_dashboard_data(conn)
    finally:
        conn.close()

    return render_template("teacher.html", data=data)


@app.route("/dashboard")
def dashboard():
    """
    Premium dashboard page.

    base.html links the Dashboard button to /dashboard.
    This route was missing in the previous version.
    """
    conn = get_db()
    try:
        data = get_dashboard_data(conn)
    finally:
        conn.close()

    return render_template("dashboard.html", data=data)


@app.route("/attendance")
def attendance():
    """
    Attendance control center.

    attendance.html also expects the complete dashboard
    dictionary through the `data` variable.
    """
    conn = get_db()
    try:
        data = get_dashboard_data(conn)
    finally:
        conn.close()

    return render_template("attendance.html", data=data)


@app.route("/create_session", methods=["POST"])
def create_session():
    subject = request.form.get("subject", "").strip()
    class_name = request.form.get("class_name", "CSE-A").strip() or "CSE-A"

    try:
        minutes = int(request.form.get("minutes", 5))
    except (TypeError, ValueError):
        minutes = 5

    # Keep the attendance window practical for a classroom.
    minutes = max(2, min(minutes, 30))

    if not subject:
        flash("Enter a subject.", "error")
        return redirect(url_for("teacher"))

    now = now_local()
    expires = now + timedelta(minutes=minutes)
    token = secrets.token_urlsafe(24)

    conn = get_db()
    try:
        cursor = conn.execute(
            """
            INSERT INTO sessions (subject, class_name, token, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (subject, class_name, token, now.isoformat(timespec="seconds"), expires.isoformat(timespec="seconds")),
        )
        conn.commit()
        session_id = cursor.lastrowid
    finally:
        conn.close()

    flash("Attendance session started. Display the QR to the class.", "success")
    return redirect(url_for("live_session", session_id=session_id))


# =========================================================
# LIVE SESSION / QR DISPLAY
# =========================================================

@app.route("/live/<int:session_id>")
def live_session(session_id):
    conn = get_db()
    try:
        session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not session:
            return "Session not found", 404
        qr = session_qr_base64(session)
        total, present, percentage = get_session_stats(conn, session_id)
    finally:
        conn.close()

    return render_template(
        "live.html",
        session=session,
        qr=qr,
        total=total,
        present=present,
        percentage=percentage,
    )


@app.route("/api/session/<int:session_id>/stats")
def session_stats(session_id):
    """Small JSON endpoint polled by the live teacher screen."""
    conn = get_db()
    try:
        session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not session:
            return jsonify({"error": "Session not found"}), 404
        total, present, percentage = get_session_stats(conn, session_id)
        active = session_is_active(session)
        remaining = max(0, int((datetime.fromisoformat(session["expires_at"]) - now_local()).total_seconds()))
        return jsonify({
            "total": total,
            "present": present,
            "percentage": percentage,
            "active": active,
            "remaining": remaining,
        })
    finally:
        conn.close()


# =========================================================
# STUDENT ATTENDANCE
# =========================================================

@app.route("/mark/<token>", methods=["GET", "POST"])
def mark_attendance(token):
    conn = get_db()
    try:
        attendance_session = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
        if not attendance_session:
            return render_template("mark.html", error="Invalid attendance QR code."), 404

        expired = not session_is_active(attendance_session)

        if request.method == "POST":
            if expired:
                return render_template("mark.html", session=attendance_session, expired=True)

            roll_no = request.form.get("roll_no", "").strip()
            if not roll_no:
                return render_template("mark.html", session=attendance_session, error="Please enter your roll number.")

            student = conn.execute("SELECT * FROM students WHERE roll_no = ?", (roll_no,)).fetchone()
            if not student:
                return render_template("mark.html", session=attendance_session, error="Student not found. Ask the teacher to register you.")

            try:
                conn.execute(
                    "INSERT INTO attendance (student_id, session_id, marked_at) VALUES (?, ?, ?)",
                    (student["id"], attendance_session["id"], now_local().isoformat(timespec="seconds")),
                )
                conn.commit()
                already = False
            except sqlite3.IntegrityError:
                already = True

            return render_template(
                "success.html",
                session=attendance_session,
                student=student,
                already=already,
            )

        return render_template("mark.html", session=attendance_session, expired=expired)
    finally:
        conn.close()


# =========================================================
# REPORTS + ANALYTICS
# =========================================================

@app.route("/report")
def report():
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT
                s.roll_no,
                s.name,
                COUNT(DISTINCT a.session_id) AS present,
                (SELECT COUNT(*) FROM sessions) AS total
            FROM students s
            LEFT JOIN attendance a ON s.id = a.student_id
            GROUP BY s.id
            ORDER BY s.roll_no
            """
        ).fetchall()
    finally:
        conn.close()
    return render_template("report.html", rows=rows)


@app.route("/analytics")
def analytics():
    conn = get_db()
    try:
        data = get_dashboard_data(conn)
        rows = conn.execute(
            """
            SELECT
                s.roll_no, s.name,
                COUNT(DISTINCT se.id) AS total,
                COUNT(DISTINCT a.session_id) AS present
            FROM students s
            LEFT JOIN sessions se ON 1 = 1
            LEFT JOIN attendance a ON a.student_id = s.id AND a.session_id = se.id
            GROUP BY s.id
            ORDER BY s.roll_no
            """
        ).fetchall()
    finally:
        conn.close()

    analytics_rows = []
    for row in rows:
        total = row["total"] or 0
        present = row["present"] or 0
        pct = round(present * 100 / total, 1) if total else 0
        status = "good" if pct >= 85 else "warning" if pct >= 75 else "critical"
        analytics_rows.append({**dict(row), "percentage": pct, "status": status})

    return render_template("analytics.html", data=data, rows=analytics_rows)


@app.route("/export.csv")
def export_csv():
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT
                s.roll_no, s.name,
                COUNT(DISTINCT a.session_id) AS present,
                (SELECT COUNT(*) FROM sessions) AS total
            FROM students s
            LEFT JOIN attendance a ON s.id = a.student_id
            GROUP BY s.id
            ORDER BY s.roll_no
            """
        ).fetchall()
    finally:
        conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Roll No", "Name", "Present Sessions", "Total Sessions", "Attendance %"])

    for row in rows:
        total = row["total"] or 0
        present = row["present"] or 0
        pct = round(present * 100 / total, 1) if total else 0
        writer.writerow([row["roll_no"], row["name"], present, total, pct])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=smartattend-report.csv"},
    )


# =========================================================
# SESSION DETAILS
# =========================================================

@app.route("/session/<int:session_id>")
def session_details(session_id):
    conn = get_db()
    try:
        attendance_session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not attendance_session:
            return "Session not found", 404

        rows = conn.execute(
            """
            SELECT s.roll_no, s.name, a.marked_at
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            WHERE a.session_id = ?
            ORDER BY s.roll_no
            """,
            (session_id,),
        ).fetchall()
    finally:
        conn.close()

    return render_template("session.html", session=attendance_session, rows=rows)


# =========================================================
# OPTIONAL FAVICON
# =========================================================

@app.route("/favicon.ico")
def favicon():
    """
    The browser automatically requests /favicon.ico.
    Returning an empty 204 response avoids a harmless 404.
    """
    return Response(status=204)


# =========================================================
# LOCAL DEVELOPMENT
# =========================================================

if __name__ == "__main__":
    # Render uses Gunicorn and does not execute this block.
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
