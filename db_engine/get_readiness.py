from __future__ import annotations

import sqlite3
from db_engine.db import get_connection
from db_engine.lookup import get_user_id, get_course_id


PASS_THRESHOLD = 0.80  # >=80%


def get_module_readiness(canvas_user_id: str, canvas_course_id: str, current_week: int) -> float:
    """
    Readiness counts a lecture as READY only if:
      - lecture_progress.status == 'COMPLETED'
      - best quiz_attempts score / total_questions >= 0.80
      - lecture.week_number <= current_week
      - excludes week 7
    """
    user_id = get_user_id(canvas_user_id)
    course_id = get_course_id(canvas_course_id)
    if user_id is None or course_id is None:
        return 0.0

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*) AS total_needed
        FROM lectures
        WHERE course_id = ?
          AND week_number <= ?
          AND week_number != 7
        """,
        (course_id, current_week),
    )
    total_needed = cur.fetchone()["total_needed"]
    if total_needed == 0:
        conn.close()
        return 0.0

    cur.execute(
        """
        SELECT COUNT(*) AS ready_count
        FROM (
            SELECT l.id,
                   MAX(CAST(qa.score AS FLOAT) / qa.total_questions) AS best_ratio
            FROM lectures l
            JOIN lecture_progress lp ON lp.lecture_id = l.id
            JOIN quiz_attempts qa ON qa.lecture_id = l.id
            WHERE l.course_id = ?
              AND l.week_number <= ?
              AND l.week_number != 7
              AND lp.user_id = ?
              AND lp.status = 'COMPLETED'
              AND qa.user_id = ?
            GROUP BY l.id
            HAVING best_ratio >= ?
        ) sub
        """,
        (course_id, current_week, user_id, user_id, PASS_THRESHOLD),
    )
    ready_count = cur.fetchone()["ready_count"]
    conn.close()
    return round((ready_count / total_needed) * 100, 1)


def get_overall_readiness(canvas_user_id: str, current_week: int) -> float:
    user_id = get_user_id(canvas_user_id)
    if user_id is None:
        return 0.0

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*) AS total_needed
        FROM lectures
        WHERE week_number <= ?
          AND week_number != 7
        """,
        (current_week,),
    )
    total_needed = cur.fetchone()["total_needed"]
    if total_needed == 0:
        conn.close()
        return 0.0

    cur.execute(
        """
        SELECT COUNT(*) AS ready_count
        FROM (
            SELECT l.id,
                   MAX(CAST(qa.score AS FLOAT) / qa.total_questions) AS best_ratio
            FROM lectures l
            JOIN lecture_progress lp ON lp.lecture_id = l.id
            JOIN quiz_attempts qa ON qa.lecture_id = l.id
            WHERE l.week_number <= ?
              AND l.week_number != 7
              AND lp.user_id = ?
              AND lp.status = 'COMPLETED'
              AND qa.user_id = ?
            GROUP BY l.id
            HAVING best_ratio >= ?
        ) sub
        """,
        (current_week, user_id, user_id, PASS_THRESHOLD),
    )
    ready_count = cur.fetchone()["ready_count"]
    conn.close()
    return round((ready_count / total_needed) * 100, 1)


def get_cumulative_lectures_completed(
    canvas_user_id: str, current_week: int
) -> tuple[int, int]:
    """Return (completed, total) lectures up to and including current_week.

    A lecture counts as completed when lecture_progress.status == 'COMPLETED'.
    Week 7 (recess) is excluded, matching the readiness logic.
    """
    user_id = get_user_id(canvas_user_id)
    if user_id is None:
        return 0, 0

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*) AS total
        FROM lectures
        WHERE week_number <= ?
          AND week_number != 7
        """,
        (current_week,),
    )
    total = cur.fetchone()["total"]

    cur.execute(
        """
        SELECT COUNT(*) AS completed
        FROM lecture_progress lp
        JOIN lectures l ON l.id = lp.lecture_id
        WHERE lp.user_id = ?
          AND lp.status = 'COMPLETED'
          AND l.week_number <= ?
          AND l.week_number != 7
        """,
        (user_id, current_week),
    )
    completed = cur.fetchone()["completed"]
    conn.close()
    return completed, total


def get_course_lectures_completed(
    canvas_user_id: str, canvas_course_id: str, current_week: int
) -> tuple[int, int]:
    """Return (completed, total) lectures for a single course up to current_week."""
    user_id = get_user_id(canvas_user_id)
    course_id = get_course_id(canvas_course_id)
    if user_id is None or course_id is None:
        return 0, 0

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*) AS total
        FROM lectures
        WHERE course_id = ?
          AND week_number <= ?
          AND week_number != 7
        """,
        (course_id, current_week),
    )
    total = cur.fetchone()["total"]

    cur.execute(
        """
        SELECT COUNT(*) AS completed
        FROM lecture_progress lp
        JOIN lectures l ON l.id = lp.lecture_id
        WHERE lp.user_id = ?
          AND lp.status = 'COMPLETED'
          AND l.course_id = ?
          AND l.week_number <= ?
          AND l.week_number != 7
        """,
        (user_id, course_id, current_week),
    )
    completed = cur.fetchone()["completed"]
    conn.close()
    return completed, total
