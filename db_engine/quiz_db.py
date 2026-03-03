from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from db_engine.db import get_connection
from db_engine.lookup import get_user_id


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_quiz_attempt(user_canvas_id: str, lecture_db_id: int, score: int, total: int) -> None:
    user_id = get_user_id(user_canvas_id)
    if user_id is None:
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO quiz_attempts (user_id, lecture_id, score, total_questions, attempted_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, lecture_db_id, int(score), int(total), _utc_now_iso()),
    )
    conn.commit()
    conn.close()


def get_last_quiz_attempt(user_canvas_id: str, lecture_db_id: int):
    user_id = get_user_id(user_canvas_id)
    if user_id is None:
        return None

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT score, total_questions, attempted_at
        FROM quiz_attempts
        WHERE user_id = ? AND lecture_id = ?
        ORDER BY attempted_at DESC
        LIMIT 1
        """,
        (user_id, lecture_db_id),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_quiz_history(user_canvas_id: str, canvas_course_id: str | None = None) -> list[dict]:
    """Return all quiz attempts for a user, optionally filtered by course.

    Each row includes: course_name, canvas_course_id, lecture_title,
    week_number, score, total_questions, attempted_at.
    """
    user_id = get_user_id(user_canvas_id)
    if user_id is None:
        return []

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if canvas_course_id:
        cur.execute(
            """
            SELECT c.course_name,
                   c.canvas_course_id,
                   l.lecture_title,
                   l.week_number,
                   qa.score,
                   qa.total_questions,
                   qa.attempted_at
            FROM quiz_attempts qa
            JOIN lectures l  ON l.id = qa.lecture_id
            JOIN courses  c  ON c.id = l.course_id
            WHERE qa.user_id = ?
              AND c.canvas_course_id = ?
            ORDER BY qa.attempted_at DESC
            """,
            (user_id, canvas_course_id),
        )
    else:
        cur.execute(
            """
            SELECT c.course_name,
                   c.canvas_course_id,
                   l.lecture_title,
                   l.week_number,
                   qa.score,
                   qa.total_questions,
                   qa.attempted_at
            FROM quiz_attempts qa
            JOIN lectures l  ON l.id = qa.lecture_id
            JOIN courses  c  ON c.id = l.course_id
            WHERE qa.user_id = ?
            ORDER BY qa.attempted_at DESC
            """,
            (user_id,),
        )

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_user_courses_with_attempts(user_canvas_id: str) -> list[dict]:
    """Return distinct courses for which the user has at least one quiz attempt."""
    user_id = get_user_id(user_canvas_id)
    if user_id is None:
        return []

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT c.canvas_course_id, c.course_name
        FROM quiz_attempts qa
        JOIN lectures l ON l.id = qa.lecture_id
        JOIN courses  c ON c.id = l.course_id
        WHERE qa.user_id = ?
        ORDER BY c.course_name
        """,
        (user_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
