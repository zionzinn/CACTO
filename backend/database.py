import sqlite3
import os
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "cacto.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Cria todas as tabelas se não existirem."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                computer_id TEXT UNIQUE NOT NULL,
                is_admin INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1,
                xp_total INTEGER DEFAULT 0,
                badge TEXT DEFAULT 'SEMENTE',
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT REFERENCES users(id),
                started_at TEXT,
                ended_at TEXT,
                paused_by_admin INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS alarms (
                id TEXT PRIMARY KEY,
                session_id TEXT REFERENCES sessions(id),
                user_id TEXT REFERENCES users(id),
                fired_at TEXT,
                acked_at TEXT,
                ack_type TEXT
            );

            CREATE TABLE IF NOT EXISTS daily_summary (
                id TEXT PRIMARY KEY,
                user_id TEXT REFERENCES users(id),
                date TEXT,
                alarms_total INTEGER DEFAULT 0,
                alarms_acked INTEGER DEFAULT 0,
                goal_pct REAL,
                goal_met INTEGER DEFAULT 0,
                xp_earned INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS admin_state (
                id INTEGER PRIMARY KEY DEFAULT 1,
                paused INTEGER DEFAULT 0,
                paused_at TEXT,
                resumed_at TEXT,
                version TEXT DEFAULT '1.0.0'
            );

            INSERT OR IGNORE INTO admin_state (id, paused, version)
            VALUES (1, 0, '1.0.0');
        """)
