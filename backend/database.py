import os
import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

_pool: ThreadedConnectionPool | None = None


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL não configurada")
        _pool = ThreadedConnectionPool(1, 10, dsn=url)
    return _pool


def get_conn():
    """Retorna uma conexão do pool."""
    return _get_pool().getconn()


def release(conn):
    """Devolve a conexão ao pool."""
    _get_pool().putconn(conn)


def cursor(conn):
    """Retorna cursor com acesso por nome de coluna (RealDictCursor)."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def init_db():
    """Cria todas as tabelas se não existirem e inicializa session_state."""
    conn = get_conn()
    try:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              SERIAL PRIMARY KEY,
                name            TEXT NOT NULL,
                email           TEXT UNIQUE NOT NULL,
                password_hash   TEXT NOT NULL,
                token           TEXT UNIQUE NOT NULL,
                is_admin        BOOLEAN DEFAULT FALSE,
                xp_total        INTEGER DEFAULT 0,
                level           INTEGER DEFAULT 1,
                streak_current  INTEGER DEFAULT 0,
                streak_best     INTEGER DEFAULT 0,
                streak_last_day TEXT,
                agent_version   TEXT,
                last_seen       TEXT,
                popup_mode      TEXT DEFAULT 'central',
                created_at      TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS water_events (
                id            SERIAL PRIMARY KEY,
                user_id       INTEGER REFERENCES users(id),
                alarm_time    TEXT NOT NULL,
                response_time TEXT,
                response      TEXT NOT NULL,
                response_secs REAL,
                xp_earned     INTEGER DEFAULT 0,
                was_away      BOOLEAN DEFAULT FALSE,
                was_paused    BOOLEAN DEFAULT FALSE,
                is_catchup    BOOLEAN DEFAULT FALSE,
                created_at    TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS session_state (
                id             INTEGER PRIMARY KEY DEFAULT 1,
                is_active      BOOLEAN DEFAULT FALSE,
                is_paused      BOOLEAN DEFAULT FALSE,
                session_start  TEXT,
                paused_at      TEXT,
                paused_elapsed INTEGER DEFAULT 0,
                interval_min   INTEGER DEFAULT 25,
                alarms_fired   INTEGER DEFAULT 0,
                updated_at     TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_summary (
                id              SERIAL PRIMARY KEY,
                user_id         INTEGER REFERENCES users(id),
                date            TEXT NOT NULL,
                alarms_total    INTEGER DEFAULT 0,
                alarms_positive INTEGER DEFAULT 0,
                alarms_away     INTEGER DEFAULT 0,
                alarms_paused   INTEGER DEFAULT 0,
                hit_goal        BOOLEAN DEFAULT FALSE,
                streak_counted  BOOLEAN DEFAULT FALSE,
                created_at      TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS badges (
                id        SERIAL PRIMARY KEY,
                user_id   INTEGER REFERENCES users(id),
                badge_key TEXT NOT NULL,
                earned_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER REFERENCES users(id),
                content    TEXT NOT NULL,
                is_system  BOOLEAN DEFAULT FALSE,
                created_at TEXT
            )
        """)

        # Garante a única linha de estado da sessão
        cur.execute("INSERT INTO session_state (id) VALUES (1) ON CONFLICT DO NOTHING")

        conn.commit()
    finally:
        release(conn)
