from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from db_engine.db import get_connection
from db_engine.lookup import get_user_id, get_course_id, get_lecture_db_id
from db_engine.events import log_event


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_lecture(user_canvas_id: str, course_canvas_id: str, week_number: int) -> None:
    user_id = get_user_id(user_canvas_id)
    course_id = get_course_id(course_canvas_id)
    lecture_db_id = get_lecture_db_id(course_canvas_id, week_number)
    if user_id is None or course_id is None or lecture_db_id is None:
        return

    conn = get_connection()
    cur = conn.cursor()
    now = _utc_now_iso()

    # Insert / update progress
    cur.execute(
        """
        INSERT INTO lecture_progress (user_id, lecture_id, status, slides_viewed, opened_at, last_accessed)
        VALUES (?, ?, 'IN_PROGRESS', 0, ?, ?)
        ON CONFLICT(user_id, lecture_id)
        DO UPDATE SET
            status = 'IN_PROGRESS',
            last_accessed = excluded.last_accessed
        """,
        (user_id, lecture_db_id, now, now),
    )
    conn.commit()
    conn.close()

    log_event(
        canvas_user_id=user_canvas_id,
        canvas_course_id=course_canvas_id,
        week_number=week_number,
        event_type="LECTURE_START",
        payload={"lecture_db_id": lecture_db_id},
    )


def mark_lecture_complete(user_canvas_id: str, course_canvas_id: str, week_number: int) -> None:
    user_id = get_user_id(user_canvas_id)
    lecture_db_id = get_lecture_db_id(course_canvas_id, week_number)
    if user_id is None or lecture_db_id is None:
        return

    conn = get_connection()
    cur = conn.cursor()
    now = _utc_now_iso()

    cur.execute(
        """
        INSERT INTO lecture_progress (user_id, lecture_id, status, slides_viewed, opened_at, last_accessed, completed_at)
        VALUES (?, ?, 'COMPLETED', 0, ?, ?, ?)
        ON CONFLICT(user_id, lecture_id)
        DO UPDATE SET
            status = 'COMPLETED',
            last_accessed = excluded.last_accessed,
            completed_at = excluded.completed_at
        """,
        (user_id, lecture_db_id, now, now, now),
    )

    conn.commit()
    conn.close()

    log_event(
        canvas_user_id=user_canvas_id,
        canvas_course_id=course_canvas_id,
        week_number=week_number,
        event_type="LECTURE_COMPLETE",
        payload={"lecture_db_id": lecture_db_id},
    )


def mark_lecture_incomplete(user_canvas_id: str, course_canvas_id: str, week_number: int) -> None:
    """Undo a completed lecture — reset it back to NOT_STARTED."""
    user_id = get_user_id(user_canvas_id)
    lecture_db_id = get_lecture_db_id(course_canvas_id, week_number)
    if user_id is None or lecture_db_id is None:
        return

    conn = get_connection()
    cur = conn.cursor()
    now = _utc_now_iso()

    cur.execute(
        """
        UPDATE lecture_progress
        SET status = 'NOT_STARTED',
            completed_at = NULL,
            last_accessed = ?
        WHERE user_id = ? AND lecture_id = ?
        """,
        (now, user_id, lecture_db_id),
    )

    conn.commit()
    conn.close()

    log_event(
        canvas_user_id=user_canvas_id,
        canvas_course_id=course_canvas_id,
        week_number=week_number,
        event_type="LECTURE_UNDO_COMPLETE",
        payload={"lecture_db_id": lecture_db_id},
    )
