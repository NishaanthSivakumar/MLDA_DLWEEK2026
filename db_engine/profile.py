"""
Compute an overall strength/weakness profile for a student.

Technical skills  — derived from topic_mastery (avg mastery per subject area)
Soft skills       — derived from learning_events, lecture_progress, quiz_attempts
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from statistics import mean, stdev
from db_engine.db import get_connection
from db_engine.lookup import get_user_id
from db_engine.events import days_since_last_activity


# ─── helpers ──────────────────────────────────────────────────────────────────

def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _label(score: float) -> tuple[str, str]:
    """Return (label, colour) for a 0-1 score."""
    if score >= 0.70:
        return "Strength", "#66bb6a"
    if score >= 0.40:
        return "Developing", "#ffa726"
    return "Weakness", "#ef5350"


# ─── technical skills ─────────────────────────────────────────────────────────

def _avg_mastery_all_courses(user_id: int) -> float:
    """Mean topic mastery across every course the student has attempted."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT mastery FROM topic_mastery WHERE user_id = ?",
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return 0.0
    return mean(float(r["mastery"]) for r in rows)


def _quiz_accuracy(user_id: int) -> float:
    """Overall quiz accuracy across all attempts."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT score, total_questions
        FROM quiz_attempts
        WHERE user_id = ?
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return 0.0
    total_score = sum(float(r["score"]) for r in rows)
    total_q = sum(float(r["total_questions"]) for r in rows if r["total_questions"])
    return _clip(total_score / total_q) if total_q else 0.0


# ─── soft skills ──────────────────────────────────────────────────────────────

def _lecture_discipline(user_id: int, current_week: int) -> float:
    """Fraction of available lectures (up to current week) marked COMPLETED."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) AS total
        FROM lectures
        WHERE week_number <= ? AND week_number != 7
        """,
        (current_week,),
    )
    total = cur.fetchone()["total"]
    if total == 0:
        conn.close()
        return 0.0
    cur.execute(
        """
        SELECT COUNT(*) AS done
        FROM lecture_progress lp
        JOIN lectures l ON l.id = lp.lecture_id
        WHERE lp.user_id = ? AND lp.status = 'COMPLETED'
          AND l.week_number <= ? AND l.week_number != 7
        """,
        (user_id, current_week),
    )
    done = cur.fetchone()["done"]
    conn.close()
    return _clip(done / total)


def _study_consistency(canvas_user_id: str, user_id: int) -> float:
    """
    Score based on regularity of quiz+lecture activity.
    Looks at the last 14 days of learning_events and computes
    the proportion of days with at least one event.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ts FROM learning_events
        WHERE user_id = ?
        ORDER BY ts DESC
        LIMIT 60
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return 0.0

    now = datetime.now(timezone.utc)
    active_days: set[int] = set()
    for r in rows:
        try:
            dt = datetime.fromisoformat(r["ts"].replace("Z", "+00:00"))
            age_days = (now - dt).days
            if age_days <= 14:
                active_days.add(age_days)
        except Exception:
            pass
    return _clip(len(active_days) / 14.0)


def _time_management(user_id: int) -> float:
    """
    Measures how evenly spread quiz attempts are over time.
    A student who quizzes a little each day scores higher than
    one who crams everything on one day.
    Score = 1 - normalised stdev of inter-attempt gaps (capped at 1).
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT attempted_at FROM quiz_attempts
        WHERE user_id = ?
        ORDER BY attempted_at ASC
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    if len(rows) < 3:
        return 0.5  # not enough data — neutral
    timestamps = []
    for r in rows:
        try:
            timestamps.append(
                datetime.fromisoformat(r["attempted_at"].replace("Z", "+00:00"))
            )
        except Exception:
            pass
    if len(timestamps) < 3:
        return 0.5
    gaps_hrs = [
        (timestamps[i] - timestamps[i - 1]).total_seconds() / 3600
        for i in range(1, len(timestamps))
    ]
    avg_gap = mean(gaps_hrs)
    if avg_gap == 0:
        return 0.2
    sd = stdev(gaps_hrs) if len(gaps_hrs) > 1 else 0.0
    cv = sd / avg_gap  # coefficient of variation — lower = more consistent
    return _clip(1.0 - min(cv / 3.0, 1.0))


def _quiz_effort(user_id: int) -> float:
    """
    Avg number of quiz attempts per lecture (retrying shows effort).
    Capped: 1 attempt = 0.4, 2 = 0.7, 3+ = 1.0
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT lecture_id, COUNT(*) AS cnt
        FROM quiz_attempts
        WHERE user_id = ?
        GROUP BY lecture_id
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return 0.0
    avg_attempts = mean(float(r["cnt"]) for r in rows)
    return _clip((avg_attempts - 1.0) / 2.0 + 0.4)   # 1→0.4, 2→0.9, 3→1.0


# ─── public API ───────────────────────────────────────────────────────────────

def get_student_profile(canvas_user_id: str, current_week: int) -> dict:
    """
    Return a profile dict with two lists:
      technical_skills: [{name, score, label, colour, description}]
      soft_skills:      [{name, score, label, colour, description}]
    """
    user_id = get_user_id(canvas_user_id)
    if user_id is None:
        return {"technical_skills": [], "soft_skills": []}

    mastery  = _avg_mastery_all_courses(user_id)
    accuracy = _quiz_accuracy(user_id)

    discipline   = _lecture_discipline(user_id, current_week)
    consistency  = _study_consistency(canvas_user_id, user_id)
    time_mgmt    = _time_management(user_id)
    effort       = _quiz_effort(user_id)

    def _skill(name: str, score: float, description: str) -> dict:
        lbl, col = _label(score)
        return {
            "name": name,
            "score": round(score, 2),
            "label": lbl,
            "colour": col,
            "description": description,
        }

    technical = [
        _skill(
            "Knowledge Mastery",
            mastery,
            "Average topic mastery across all your quizzed subjects.",
        ),
        _skill(
            "Quiz Accuracy",
            accuracy,
            "Overall percentage of quiz questions answered correctly.",
        ),
    ]

    soft = [
        _skill(
            "Lecture Discipline",
            discipline,
            "Proportion of available lectures you have completed on schedule.",
        ),
        _skill(
            "Study Consistency",
            consistency,
            "How regularly you have been active across the last 14 days.",
        ),
        _skill(
            "Time Management",
            time_mgmt,
            "How evenly your study sessions are spread over time (vs cramming).",
        ),
        _skill(
            "Revision Effort",
            effort,
            "Average quiz re-attempt rate — shows willingness to revise until mastery.",
        ),
    ]

    return {"technical_skills": technical, "soft_skills": soft}
