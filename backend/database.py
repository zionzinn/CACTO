import os
import sqlite3
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
    """Cria todas as tabelas caso não existam e garante o estado inicial."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                email           TEXT UNIQUE NOT NULL,
                password_hash   TEXT NOT NULL,
                token           TEXT UNIQUE NOT NULL,
                is_admin        INTEGER DEFAULT 0,
                xp_total        INTEGER DEFAULT 0,
                level           INTEGER DEFAULT 1,
                streak_current  INTEGER DEFAULT 0,
                streak_best     INTEGER DEFAULT 0,
                streak_last_day TEXT,
                agent_version   TEXT,
                last_seen       TEXT,
                popup_mode      TEXT DEFAULT 'central',
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS water_events (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER REFERENCES users(id),
                alarm_time      TEXT NOT NULL,
                response_time   TEXT,
                response        TEXT NOT NULL,
                response_secs   REAL,
                xp_earned       INTEGER DEFAULT 0,
                was_away        INTEGER DEFAULT 0,
                was_paused      INTEGER DEFAULT 0,
                is_catchup      INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS session_state (
                id              INTEGER PRIMARY KEY DEFAULT 1,
                is_active       INTEGER DEFAULT 0,
                is_paused       INTEGER DEFAULT 0,
                session_start   TEXT,
                paused_at       TEXT,
                paused_elapsed  INTEGER DEFAULT 0,
                interval_min    INTEGER DEFAULT 25,
                alarms_fired    INTEGER DEFAULT 0,
                updated_at      TEXT
            );

            CREATE TABLE IF NOT EXISTS daily_summary (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER REFERENCES users(id),
                date            TEXT NOT NULL,
                alarms_total    INTEGER DEFAULT 0,
                alarms_positive INTEGER DEFAULT 0,
                alarms_away     INTEGER DEFAULT 0,
                alarms_paused   INTEGER DEFAULT 0,
                hit_goal        INTEGER DEFAULT 0,
                streak_counted  INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS badges (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER REFERENCES users(id),
                badge_key       TEXT NOT NULL,
                earned_at       TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER REFERENCES users(id),
                content         TEXT NOT NULL,
                is_system       INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP
            );

            INSERT OR IGNORE INTO session_state (id) VALUES (1);
        """)
