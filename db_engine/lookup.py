from __future__ import annotations

import sqlite3
from db_engine.db import get_connection


def get_user_id(canvas_user_id: str) -> int | None:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE canvas_user_id = ?", (canvas_user_id,))
    row = cur.fetchone()
    conn.close()
    return row["id"] if row else None


def get_course_id(canvas_course_id: str) -> int | None:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id FROM courses WHERE canvas_course_id = ?", (canvas_course_id,))
    row = cur.fetchone()
    conn.close()
    return row["id"] if row else None


def get_lecture_db_id(canvas_course_id: str, week_number: int) -> int | None:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT l.id
        FROM lectures l
        JOIN courses c ON c.id = l.course_id
        WHERE c.canvas_course_id = ?
          AND l.week_number = ?
        """,
        (canvas_course_id, week_number),
    )
    row = cur.fetchone()
    conn.close()
    return row["id"] if row else None
