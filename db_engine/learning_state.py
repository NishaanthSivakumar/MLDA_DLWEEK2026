from __future__ import annotations

import sqlite3
from statistics import mean
from db_engine.db import get_connection
from db_engine.lookup import get_user_id, get_course_id
from db_engine.events import days_since_last_activity


def _get_recent_quiz_ratios(user_id: int, course_id: int | None, n: int = 4) -> list[float]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if course_id is None:
        cur.execute(
            """
            SELECT qa.score, qa.total_questions
            FROM quiz_attempts qa
            WHERE qa.user_id = ?
            ORDER BY qa.attempted_at DESC
            LIMIT ?
            """,
            (user_id, n),
        )
    else:
        cur.execute(
            """
            SELECT qa.score, qa.total_questions
            FROM quiz_attempts qa
            JOIN lectures l ON l.id = qa.lecture_id
            WHERE qa.user_id = ?
              AND l.course_id = ?
            ORDER BY qa.attempted_at DESC
            LIMIT ?
            """,
            (user_id, course_id, n),
        )

    rows = cur.fetchall()
    conn.close()
    ratios = []
    for r in rows:
        if r["total_questions"]:
            ratios.append(float(r["score"]) / float(r["total_questions"]))
    return ratios


def classify_learning_state(canvas_user_id: str, canvas_course_id: str | None = None) -> dict:
    """
    Returns a simple, explainable state:
      - INACTIVE: no events recently
      - IMPROVING / NEEDS ATTENTION / STABLE based on last 4 quiz ratios
      - If too little data: NEW
    """
    user_id = get_user_id(canvas_user_id)
    if user_id is None:
        return {"state": "NEW", "reason": "No user record."}

    course_id = get_course_id(canvas_course_id) if canvas_course_id else None

    inactive_days = days_since_last_activity(canvas_user_id)
    if inactive_days >= 10:
        return {"state": "INACTIVE", "reason": f"No learning activity for {inactive_days} days."}

    ratios = _get_recent_quiz_ratios(user_id, course_id, n=4)
    if len(ratios) < 2:
        return {"state": "NEW", "reason": "Not enough quiz history yet."}

    # Compare recent half vs older half
    mid = len(ratios) // 2
    recent = mean(ratios[:mid])
    older = mean(ratios[mid:])

    delta = recent - older  # positive means improving

    if delta >= 0.08:
        return {"state": "IMPROVING", "reason": f"Recent quiz accuracy is up by {delta*100:.0f}% vs earlier attempts."}
    if delta <= -0.08:
        return {"state": "NEEDS ATTENTION", "reason": f"Recent quiz accuracy is down by {-delta*100:.0f}% vs earlier attempts."}
    return {"state": "STABLE", "reason": "Quiz accuracy is roughly stable recently."}
