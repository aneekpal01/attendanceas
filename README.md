# SmartAttend — QR Attendance System

A simple, premium QR-based classroom attendance system built with Flask and SQLite.

## Core flow

1. Teacher opens the dashboard.
2. Teacher creates one attendance session.
3. SmartAttend generates one secure QR code.
4. Teacher displays the QR on a projector/screen.
5. 50+ students scan the same QR and enter their registered roll number.
6. The server validates the session and prevents duplicate attendance.
7. The teacher's live display updates every 2 seconds.
8. Teacher can inspect reports, analytics and export CSV.

## Features

- Premium dark/light responsive UI
- One QR per attendance session
- Configurable 5/10/15 minute attendance window
- Live attendance counter
- Classroom display mode
- Duplicate attendance prevention
- Student directory + search
- Attendance percentage
- Simple attendance risk rules
- Smart insights
- CSV export
- Render-ready Gunicorn configuration

## Run locally

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`.

## Render

Use the included `render.yaml`, or create a Python web service manually:

- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`
- Environment variable: `SECRET_KEY`

### Important database note

This starter version uses SQLite. Render's local filesystem is not intended for durable production data, so the included Blueprint uses `/tmp/attendance.db` for demo deployments. For a serious multi-instance production deployment, replace SQLite with PostgreSQL.

## GitHub workflow

```bash
git init
git add .
git commit -m "Build SmartAttend QR attendance system"
git branch -M main
git remote add origin YOUR_GITHUB_REPO_URL
git push -u origin main
```

After connecting the repository to Render, every push can trigger a new deployment.

## Version 2 — Hackathon Premium Build

This package is the modified premium hackathon version of SmartAttend.

### Demo flow
1. Teacher opens the dashboard.
2. Teacher creates one attendance session for a subject/class.
3. The system displays one QR code for the whole classroom.
4. Students scan the same QR and submit their roll number.
5. The backend prevents duplicate attendance.
6. The teacher's live session page shows the attendance count and progress.
7. After the session, reports and analytics can be viewed and CSV exported.

### Render deployment
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- The included `render.yaml` can be used as a deployment reference.

### Important database note
SQLite is intentionally used for this easy hackathon build. For a long-running production deployment, replace SQLite with PostgreSQL because Render's local filesystem should not be treated as durable application storage.
