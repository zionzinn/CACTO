"""Registro de eventos de água e heartbeat do agente."""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from database import get_db
from routers.auth import get_current_user, extrair_token
from gamification import calcular_xp, calcular_level, verificar_badges_evento

router = APIRouter(tags=["events"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DrinkBody(BaseModel):
    alarm_time: str
    response_time: str


class TimeoutBody(BaseModel):
    alarm_time: str


class AwayBody(BaseModel):
    alarm_time: str


class CatchupBody(BaseModel):
    alarm_time: str
    response: str  # 'catchup_yes' | 'catchup_no'


class HeartbeatBody(BaseModel):
    agent_version: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

def _calcular_response_secs(alarm_time: str, response_time: str) -> Optional[float]:
    try:
        t1 = datetime.fromisoformat(alarm_time)
        t2 = datetime.fromisoformat(response_time)
        return max(0.0, (t2 - t1).total_seconds())
    except Exception:
        return None


def _registrar_evento(
    user_id: int,
    response: str,
    alarm_time: str,
    response_time: Optional[str],
    is_catchup: int,
    was_away: int,
    conn,
) -> dict:
    """Salva evento, calcula XP, atualiza usuário e retorna resultado."""
    agora = datetime.utcnow().isoformat()

    response_secs = None
    if response_time:
        response_secs = _calcular_response_secs(alarm_time, response_time)

    usuario = conn.execute(
        "SELECT xp_total, level, streak_current FROM users WHERE id=?", (user_id,)
    ).fetchone()

    xp = calcular_xp(response, response_secs, usuario["streak_current"])

    conn.execute(
        """INSERT INTO water_events
           (user_id, alarm_time, response_time, response, response_secs,
            xp_earned, was_away, is_catchup, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, alarm_time, response_time, response, response_secs,
         xp, was_away, is_catchup, agora),
    )

    novo_xp = usuario["xp_total"] + xp
    novo_level, level_name, xp_proximo = calcular_level(novo_xp)

    conn.execute(
        "UPDATE users SET xp_total=?, level=?, last_seen=? WHERE id=?",
        (novo_xp, novo_level, agora, user_id),
    )

    badges = verificar_badges_evento(user_id, response, conn)

    return {
        "xp_earned": xp,
        "xp_total": novo_xp,
        "level": novo_level,
        "level_name": level_name,
        "badge_unlocked": badges if badges else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/events/drink")
def event_drink(body: DrinkBody, authorization: Optional[str] = Header(default=None)):
    token = extrair_token(authorization)
    with get_db() as conn:
        usuario = get_current_user(token, conn)
        return _registrar_evento(
            usuario["id"], "drank", body.alarm_time, body.response_time, 0, 0, conn
        )


@router.post("/events/empty")
def event_empty(body: DrinkBody, authorization: Optional[str] = Header(default=None)):
    token = extrair_token(authorization)
    with get_db() as conn:
        usuario = get_current_user(token, conn)
        return _registrar_evento(
            usuario["id"], "empty_bottle", body.alarm_time, body.response_time, 0, 0, conn
        )


@router.post("/events/timeout")
def event_timeout(body: TimeoutBody, authorization: Optional[str] = Header(default=None)):
    token = extrair_token(authorization)
    agora = datetime.utcnow().isoformat()
    with get_db() as conn:
        usuario = get_current_user(token, conn)
        conn.execute(
            """INSERT INTO water_events
               (user_id, alarm_time, response, xp_earned, created_at)
               VALUES (?, ?, 'timeout', 0, ?)""",
            (usuario["id"], body.alarm_time, agora),
        )
        conn.execute("UPDATE users SET last_seen=? WHERE id=?", (agora, usuario["id"]))
    return {"xp_earned": 0}


@router.post("/events/away")
def event_away(body: AwayBody, authorization: Optional[str] = Header(default=None)):
    token = extrair_token(authorization)
    agora = datetime.utcnow().isoformat()
    with get_db() as conn:
        usuario = get_current_user(token, conn)
        conn.execute(
            """INSERT INTO water_events
               (user_id, alarm_time, response, xp_earned, was_away, created_at)
               VALUES (?, ?, 'away', 0, 1, ?)""",
            (usuario["id"], body.alarm_time, agora),
        )
        conn.execute("UPDATE users SET last_seen=? WHERE id=?", (agora, usuario["id"]))
    return {"xp_earned": 0}


@router.post("/events/catchup")
def event_catchup(body: CatchupBody, authorization: Optional[str] = Header(default=None)):
    if body.response not in ("catchup_yes", "catchup_no"):
        raise HTTPException(
            status_code=422,
            detail="response deve ser 'catchup_yes' ou 'catchup_no'",
        )
    token = extrair_token(authorization)
    with get_db() as conn:
        usuario = get_current_user(token, conn)
        return _registrar_evento(
            usuario["id"], body.response, body.alarm_time, None, 1, 0, conn
        )


@router.post("/heartbeat")
def heartbeat(body: HeartbeatBody, authorization: Optional[str] = Header(default=None)):
    """
    Endpoint mais chamado do sistema (a cada 30s por 22 PCs).
    Deve ser leve: apenas UPDATE + SELECT.
    """
    token = extrair_token(authorization)
    agora = datetime.utcnow().isoformat()

    with get_db() as conn:
        usuario = conn.execute("SELECT id FROM users WHERE token=?", (token,)).fetchone()
        if not usuario:
            raise HTTPException(status_code=401, detail="Token inválido")

        if body.agent_version:
            conn.execute(
                "UPDATE users SET last_seen=?, agent_version=? WHERE id=?",
                (agora, body.agent_version, usuario["id"]),
            )
        else:
            conn.execute(
                "UPDATE users SET last_seen=? WHERE id=?",
                (agora, usuario["id"]),
            )

        sessao = conn.execute("SELECT * FROM session_state WHERE id=1").fetchone()

    return dict(sessao)
