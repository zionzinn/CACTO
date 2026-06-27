"""Rotas administrativas — requerem SECRET_KEY."""

import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from database import get_db
from routers.session import _require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


def _agora() -> str:
    return datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
# GET /admin/users
# ---------------------------------------------------------------------------

@router.get("/users")
def admin_users(authorization: Optional[str] = Header(default=None)):
    """Lista todos os usuários com stats resumidos."""
    _require_admin(authorization)
    with get_db() as conn:
        rows = conn.execute(
            """SELECT
                u.id, u.name, u.email, u.is_admin, u.xp_total, u.level,
                u.streak_current, u.streak_best, u.last_seen, u.agent_version,
                u.created_at,
                (SELECT COUNT(*) FROM water_events WHERE user_id=u.id) AS total_eventos
               FROM users u
               ORDER BY u.name"""
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /admin/online
# ---------------------------------------------------------------------------

@router.get("/online")
def admin_online(authorization: Optional[str] = Header(default=None)):
    """Lista usuários com last_seen nos últimos 2 minutos."""
    _require_admin(authorization)
    dois_min_atras = (datetime.utcnow() - timedelta(minutes=2)).isoformat()
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, name, last_seen, agent_version, level, xp_total
               FROM users
               WHERE last_seen >= ? AND is_admin=0
               ORDER BY last_seen DESC""",
            (dois_min_atras,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /admin/events
# ---------------------------------------------------------------------------

@router.get("/events")
def admin_events(
    user_id: Optional[int] = None,
    date: Optional[str] = None,
    response: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    """Lista water_events com filtros opcionais."""
    _require_admin(authorization)

    query = "SELECT we.*, u.name FROM water_events we JOIN users u ON u.id=we.user_id WHERE 1=1"
    params: list = []

    if user_id is not None:
        query += " AND we.user_id=?"
        params.append(user_id)
    if date:
        query += " AND DATE(we.alarm_time)=?"
        params.append(date)
    if response:
        query += " AND we.response=?"
        params.append(response)

    query += " ORDER BY we.alarm_time DESC LIMIT 500"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# DELETE /admin/users/{user_id}
# ---------------------------------------------------------------------------

@router.delete("/users/{user_id}")
def admin_delete_user(user_id: int, authorization: Optional[str] = Header(default=None)):
    """Deleta usuário e todos os seus dados relacionados."""
    _require_admin(authorization)
    with get_db() as conn:
        usuario = conn.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        conn.execute("DELETE FROM water_events WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM daily_summary WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM badges WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM chat_messages WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))

    return {"ok": True, "deleted_user_id": user_id}


# ---------------------------------------------------------------------------
# POST /admin/reset-session
# ---------------------------------------------------------------------------

@router.post("/reset-session")
def admin_reset_session(authorization: Optional[str] = Header(default=None)):
    """Reseta session_state para o estado inicial — use em emergências."""
    _require_admin(authorization)
    agora = _agora()
    with get_db() as conn:
        conn.execute(
            """UPDATE session_state
               SET is_active=0, is_paused=0, session_start=NULL, paused_at=NULL,
                   paused_elapsed=0, alarms_fired=0, updated_at=?
               WHERE id=1""",
            (agora,),
        )
    return {"ok": True, "message": "Sessão resetada com sucesso"}
