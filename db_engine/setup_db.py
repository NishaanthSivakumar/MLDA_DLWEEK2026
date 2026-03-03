from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from db_engine.db import get_connection


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_schema() -> None:
    conn = get_connection()
    cur = conn.cursor()

    # Core tables (your existing schema + quiz_attempts)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        canvas_user_id TEXT UNIQUE,
        name TEXT,
        email TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        canvas_course_id TEXT UNIQUE,
        course_name TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS lectures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        week_number INTEGER NOT NULL,
        lecture_title TEXT,
        canvas_slide_url TEXT,
        total_slides INTEGER,
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS lecture_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        lecture_id INTEGER NOT NULL,
        status TEXT DEFAULT 'NOT_STARTED',
        slides_viewed INTEGER DEFAULT 0,
        opened_at TEXT,
        last_accessed TEXT,
        completed_at TEXT,
        UNIQUE(user_id, lecture_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(lecture_id) REFERENCES lectures(id)
    );
    """)

    # Practice quiz attempts (your AI quiz grading writes here)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS quiz_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        lecture_id INTEGER NOT NULL,
        score INTEGER NOT NULL,
        total_questions INTEGER NOT NULL,
        attempted_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(lecture_id) REFERENCES lectures(id)
    );
    """)

    # --- NEW: Topic mastery (dynamic learning state) ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS topic_mastery (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        topic TEXT NOT NULL,
        mastery REAL NOT NULL DEFAULT 0.5,
        confidence REAL NOT NULL DEFAULT 0.0,
        attempts INTEGER NOT NULL DEFAULT 0,
        correct INTEGER NOT NULL DEFAULT 0,
        avg_time_sec REAL,
        last_practiced_at TEXT,
        updated_at TEXT,
        UNIQUE(user_id, course_id, topic),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    # --- NEW: Event log (explainability + long-term behavior) ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS learning_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER,
        week_number INTEGER,
        event_type TEXT NOT NULL,
        ts TEXT NOT NULL,
        payload_json TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    # --- OPTIONAL: assessments/tasks (assignment/quiz tracker) ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS course_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        week_number INTEGER,
        task_type TEXT NOT NULL, -- 'ASSIGNMENT' | 'CANVAS_QUIZ'
        title TEXT NOT NULL,
        due_date TEXT,
        weight_percent REAL,
        link TEXT,
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS task_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        task_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'NOT_STARTED', -- NOT_STARTED | SUBMITTED | GRADED
        score REAL,
        max_score REAL,
        submitted_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(task_id) REFERENCES course_tasks(id)
    );
    """)

    conn.commit()
    conn.close()


def seed_mock_data() -> None:
    """Seed with your 2-course mock pattern (lectures + progress)."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # User
    cur.execute(
        """
        INSERT OR IGNORE INTO users (canvas_user_id, name, email)
        VALUES (?, ?, ?)
        """,
        ("student_001", "John Doe", "johndoe@u.nus.edu"),
    )
    cur.execute("SELECT id FROM users WHERE canvas_user_id = ?", ("student_001",))
    user_id = cur.fetchone()["id"]

    def insert_course(canvas_id: str, course_name: str, base_url: str) -> int:
        cur.execute(
            """
            INSERT OR IGNORE INTO courses (canvas_course_id, course_name)
            VALUES (?, ?)
            """,
            (canvas_id, course_name),
        )
        cur.execute("SELECT id FROM courses WHERE canvas_course_id = ?", (canvas_id,))
        course_id = cur.fetchone()["id"]

        lecture_ids = []
        for week in range(1, 14):
            if week == 7:
                continue

            cur.execute(
                """
                INSERT OR IGNORE INTO lectures (
                    course_id, week_number, lecture_title, canvas_slide_url, total_slides
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (course_id, week, f"Week {week}", f"{base_url}{week}/", 30),
            )
            cur.execute(
                """
                SELECT id FROM lectures
                WHERE course_id = ? AND week_number = ?
                """,
                (course_id, week),
            )
            lecture_ids.append(cur.fetchone()["id"])

        # Progress pattern: first 2 completed, next 2 in progress, rest not started
        now = _utc_now_iso()
        for i, lecture_id in enumerate(lecture_ids):
            if i < 2:
                status = "COMPLETED"
                slides = 30
                completed_at = now
            elif i < 4:
                status = "IN_PROGRESS"
                slides = 10
                completed_at = None
            else:
                status = "NOT_STARTED"
                slides = 0
                completed_at = None

            cur.execute(
                """
                INSERT OR IGNORE INTO lecture_progress (
                    user_id, lecture_id, status, slides_viewed, opened_at, last_accessed, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    lecture_id,
                    status,
                    slides,
                    now if status != "NOT_STARTED" else None,
                    now if status != "NOT_STARTED" else None,
                    completed_at,
                ),
            )

        return course_id

    ml_course_id = insert_course(
        "machine_learning_2006",
        "MIT 6.867 Machine Learning (Fall 2006)",
        "https://ocw.mit.edu/courses/6-867-machine-learning-fall-2006/resources/lec",
    )
    fin_course_id = insert_course(
        "financial_modelling_2025",
        "Financial Modelling (MIT 18.642)",
        "https://ocw.mit.edu/courses/18-642-topics-in-mathematics-with-applications-in-finance-fall-2024/pages/week-",
    )

    # Seed a few quiz attempts to demonstrate mastery + readiness gating
    # Link quiz attempts to the *lecture row ids* (not week numbers).
    def lecture_id_for(course_id: int, week_number: int) -> int:
        cur.execute(
            "SELECT id FROM lectures WHERE course_id = ? AND week_number = ?",
            (course_id, week_number),
        )
        return cur.fetchone()["id"]

    # Completed + high scores for ML weeks 1-2, and low score for week 3
    for wk, sc in [(1, 5), (2, 4), (3, 2)]:
        lid = lecture_id_for(ml_course_id, wk)
        cur.execute(
            """
            INSERT INTO quiz_attempts (user_id, lecture_id, score, total_questions, attempted_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, lid, sc, 5, _utc_now_iso()),
        )

    # Financial modelling: high scores for weeks 1-2
    for wk, sc in [(1, 5), (2, 5)]:
        lid = lecture_id_for(fin_course_id, wk)
        cur.execute(
            """
            INSERT INTO quiz_attempts (user_id, lecture_id, score, total_questions, attempted_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, lid, sc, 5, _utc_now_iso()),
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    create_schema()
    seed_mock_data()
    print("✅ DB schema created and mock data seeded.")
