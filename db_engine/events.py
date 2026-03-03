from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from db_engine.db import get_connection
from db_engine.lookup import get_user_id, get_course_id


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_event(
    *,
    canvas_user_id: str,
    canvas_course_id: str | None,
    week_number: int | None,
    event_type: str,
    payload: dict | None = None,
) -> None:
    user_id = get_user_id(canvas_user_id)
    if user_id is None:
        return

    course_id = get_course_id(canvas_course_id) if canvas_course_id else None

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO learning_events (user_id, course_id, week_number, event_type, ts, payload_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            course_id,
            week_number,
            event_type,
            _utc_now_iso(),
            json.dumps(payload or {}),
        ),
    )
    conn.commit()
    conn.close()


def days_since_last_activity(canvas_user_id: str) -> int:
    user_id = get_user_id(canvas_user_id)
    if user_id is None:
        return 9999

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ts
        FROM learning_events
        WHERE user_id = ?
        ORDER BY ts DESC
        LIMIT 1
        """,
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return 9999

    last = datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    return max(0, (now - last).days)
