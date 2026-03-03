from __future__ import annotations

import sqlite3
from pathlib import Path

from config import path_in_project
# db_engine/ is the single source of truth for DB location
DB_PATH = path_in_project("db_engine", "lumi_grad.db")


def get_connection() -> sqlite3.Connection:
    """Return a sqlite connection to the app DB."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn