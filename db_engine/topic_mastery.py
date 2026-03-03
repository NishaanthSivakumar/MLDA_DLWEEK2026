from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from db_engine.db import get_connection
from db_engine.lookup import get_user_id, get_course_id


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _days_since(iso_ts: str | None) -> int:
    if not iso_ts:
        return 0
    dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    return max(0, (now - dt).days)


def update_topics_from_question(
    *,
    canvas_user_id: str,
    canvas_course_id: str,
    topic_tags: list[str],
    is_correct: bool,
    time_spent_sec: int | None = None,
    decay_base: float = 0.98,
) -> None:
    """Update mastery per topic for a single graded question."""
    user_id = get_user_id(canvas_user_id)
    course_id = get_course_id(canvas_course_id)
    if user_id is None or course_id is None:
        return

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    target = 1.0 if is_correct else 0.0
    now = _utc_now_iso()

    for topic in topic_tags:
        cur.execute(
            """
            SELECT mastery, confidence, attempts, correct, avg_time_sec, last_practiced_at
            FROM topic_mastery
            WHERE user_id = ? AND course_id = ? AND topic = ?
            """,
            (user_id, course_id, topic),
        )
        row = cur.fetchone()

        if row is None:
            mastery = 0.5
            confidence = 0.0
            attempts = 0
            correct = 0
            avg_time_sec = None
            last_practiced_at = None
        else:
            mastery = float(row["mastery"])
            confidence = float(row["confidence"])
            attempts = int(row["attempts"])
            correct = int(row["correct"])
            avg_time_sec = row["avg_time_sec"]
            last_practiced_at = row["last_practiced_at"]

        # Inactivity decay
        days = _days_since(last_practiced_at)
        if days > 0:
            mastery = mastery * (decay_base ** days)

        # Confidence-aware learning rate (shrinks over time)
        lr = 0.25 * (1.0 - confidence)

        mastery = _clip01(mastery + lr * (target - mastery))

        attempts += 1
        correct += int(is_correct)
        confidence = _clip01(confidence + 0.08)

        # Update avg time
        if time_spent_sec is not None:
            if avg_time_sec is None:
                avg_time_sec = float(time_spent_sec)
            else:
                avg_time_sec = float(avg_time_sec) * 0.8 + float(time_spent_sec) * 0.2

        cur.execute(
            """
            INSERT INTO topic_mastery (
                user_id, course_id, topic, mastery, confidence, attempts, correct,
                avg_time_sec, last_practiced_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, course_id, topic)
            DO UPDATE SET
                mastery = excluded.mastery,
                confidence = excluded.confidence,
                attempts = excluded.attempts,
                correct = excluded.correct,
                avg_time_sec = excluded.avg_time_sec,
                last_practiced_at = excluded.last_practiced_at,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                course_id,
                topic,
                mastery,
                confidence,
                attempts,
                correct,
                avg_time_sec,
                now,
                now,
            ),
        )

    conn.commit()
    conn.close()


def get_topic_summary(canvas_user_id: str, canvas_course_id: str, limit: int = 5):
    """Return weakest and strongest topics."""
    user_id = get_user_id(canvas_user_id)
    course_id = get_course_id(canvas_course_id)
    if user_id is None or course_id is None:
        return {"weak": [], "strong": []}

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT topic, mastery, confidence, attempts, correct, avg_time_sec, last_practiced_at
        FROM topic_mastery
        WHERE user_id = ? AND course_id = ?
        ORDER BY mastery ASC
        LIMIT ?
        """,
        (user_id, course_id, limit),
    )
    weak = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT topic, mastery, confidence, attempts, correct, avg_time_sec, last_practiced_at
        FROM topic_mastery
        WHERE user_id = ? AND course_id = ?
        ORDER BY mastery DESC
        LIMIT ?
        """,
        (user_id, course_id, limit),
    )
    strong = [dict(r) for r in cur.fetchall()]

    conn.close()
    return {"weak": weak, "strong": strong}
