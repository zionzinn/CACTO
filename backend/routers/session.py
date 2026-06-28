"""Controle da sessão global de hidratação (admin only)."""

import os
from datetime import datetime, date, timedelta
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from database import get_conn, release, cursor as db_cursor
from gamification import (
    calcular_level, atualizar_streak, verificar_badges_fim_dia,
    META_GOAL_PCT, XP_BONUS_DIA,
)

router = APIRouter(prefix="/session", tags=["session"])


# ---------------------------------------------------------------------------
# Auth admin
# ---------------------------------------------------------------------------

def _require_admin(authorization: Optional[str]):
    secret = os.getenv("SECRET_KEY", "")
    if not secret:
        raise HTTPException(status_code=500, detail="SECRET_KEY não configurado no servidor")
    token = (authorization or "").removeprefix("Bearer ")
    if token == secret:
        return

    from database import get_conn as _gc, release as _rel, cursor as _cur
    conn = _gc()
    try:
        cur = _cur(conn)
        cur.execute("SELECT is_admin FROM users WHERE token=%s", (token,))
        u = cur.fetchone()
        if u and u["is_admin"]:
            return
    finally:
        _rel(conn)

    raise HTTPException(status_code=401, detail="Acesso restrito ao administrador")


# ---------------------------------------------------------------------------
# Helpers internos (reutilizados por stats.py)
# ---------------------------------------------------------------------------

def _agora() -> str:
    return datetime.utcnow().isoformat()


def _hoje() -> str:
    return date.today().isoformat()


def _ler_session(conn) -> dict:
    cur = db_cursor(conn)
    cur.execute("SELECT * FROM session_state WHERE id=1")
    row = cur.fetchone()
    return dict(row) if row else {}


def _calcular_next_alarm(state: dict) -> Optional[str]:
    """Calcula o datetime ISO do próximo alarme, ou None se sessão inativa/pausada."""
    if not state.get("is_active") or state.get("is_paused"):
        return None
    try:
        inicio = datetime.fromisoformat(state["session_start"])
        agora_dt = datetime.utcnow()
        intervalo_s = state["interval_min"] or 10
        elapsed = (agora_dt - inicio).total_seconds() - (state["paused_elapsed"] or 0)
        falta = intervalo_s - (elapsed % intervalo_s)
        return (agora_dt + timedelta(seconds=falta)).isoformat()
    except Exception:
        return None


def _session_response(conn) -> dict:
    state = _ler_session(conn)
    state["next_alarm_at"] = _calcular_next_alarm(state)
    return state


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
def get_session():
    """Retorna o estado atual da sessão — sem autenticação."""
    conn = get_conn()
    try:
        return _session_response(conn)
    finally:
        release(conn)


@router.post("/start")
def session_start(authorization: Optional[str] = Header(default=None)):
    _require_admin(authorization)
    agora = _agora()
    conn = get_conn()
    try:
        cur = db_cursor(conn)
        cur.execute(
            """UPDATE session_state
               SET is_active=TRUE, is_paused=FALSE, session_start=%s,
                   paused_elapsed=0, paused_at=NULL, alarms_fired=0, updated_at=%s
               WHERE id=1""",
            (agora, agora),
        )
        conn.commit()
        return _session_response(conn)
    finally:
        release(conn)


@router.post("/pause")
def session_pause(authorization: Optional[str] = Header(default=None)):
    _require_admin(authorization)
    agora = _agora()
    conn = get_conn()
    try:
        state = _ler_session(conn)
        if not state.get("is_active"):
            raise HTTPException(status_code=400, detail="Sessão não está ativa")
        cur = db_cursor(conn)
        cur.execute(
            "UPDATE session_state SET is_paused=TRUE, paused_at=%s, updated_at=%s WHERE id=1",
            (agora, agora),
        )
        conn.commit()
        return _session_response(conn)
    finally:
        release(conn)


@router.post("/resume")
def session_resume(authorization: Optional[str] = Header(default=None)):
    _require_admin(authorization)
    agora = _agora()
    conn = get_conn()
    try:
        state = _ler_session(conn)
        if not state.get("is_paused"):
            raise HTTPException(status_code=400, detail="Sessão não está pausada")

        tempo_pausado = 0
        if state.get("paused_at"):
            try:
                pausou_em = datetime.fromisoformat(state["paused_at"])
                tempo_pausado = int((datetime.utcnow() - pausou_em).total_seconds())
            except Exception:
                pass

        novo_elapsed = (state.get("paused_elapsed") or 0) + tempo_pausado
        cur = db_cursor(conn)
        cur.execute(
            """UPDATE session_state
               SET is_paused=FALSE, paused_at=NULL, paused_elapsed=%s, updated_at=%s
               WHERE id=1""",
            (novo_elapsed, agora),
        )
        conn.commit()
        return _session_response(conn)
    finally:
        release(conn)


@router.post("/end")
def session_end(authorization: Optional[str] = Header(default=None)):
    _require_admin(authorization)
    agora = _agora()
    hoje = _hoje()
    summaries = []

    conn = get_conn()
    try:
        cur = db_cursor(conn)
        cur.execute(
            "UPDATE session_state SET is_active=FALSE, is_paused=FALSE, updated_at=%s WHERE id=1",
            (agora,),
        )

        cur.execute(
            "SELECT DISTINCT user_id FROM water_events WHERE LEFT(alarm_time, 10)=%s",
            (hoje,),
        )
        usuarios_hoje = cur.fetchall()

        for row in usuarios_hoje:
            uid = row["user_id"]
            _fechar_dia_usuario(uid, hoje, conn, agora)

            cur2 = db_cursor(conn)
            cur2.execute(
                "SELECT name, xp_total, level, streak_current FROM users WHERE id=%s", (uid,)
            )
            usuario = cur2.fetchone()
            summaries.append({
                "user_id": uid,
                "name": usuario["name"],
                "xp_total": usuario["xp_total"],
                "level": usuario["level"],
                "streak_current": usuario["streak_current"],
            })

        conn.commit()
    finally:
        release(conn)

    return {"ok": True, "summaries": summaries}


def _fechar_dia_usuario(user_id: int, hoje: str, conn, agora: str):
    """Calcula daily_summary, streak, bônus de XP e badges de fim de dia."""
    cur = db_cursor(conn)
    cur.execute(
        "SELECT response, was_paused FROM water_events WHERE user_id=%s AND LEFT(alarm_time, 10)=%s",
        (user_id, hoje),
    )
    eventos = cur.fetchall()

    if not eventos:
        return

    total    = len(eventos)
    positivos = sum(1 for e in eventos if e["response"] in ("drank", "empty_bottle"))
    away     = sum(1 for e in eventos if e["response"] == "away")
    paused   = sum(1 for e in eventos if e["was_paused"])
    pct      = positivos / total if total else 0.0
    hit_goal = pct >= META_GOAL_PCT

    # Upsert em daily_summary
    cur2 = db_cursor(conn)
    cur2.execute(
        "SELECT id FROM daily_summary WHERE user_id=%s AND date=%s", (user_id, hoje)
    )
    existente = cur2.fetchone()

    if existente:
        cur3 = db_cursor(conn)
        cur3.execute(
            """UPDATE daily_summary
               SET alarms_total=%s, alarms_positive=%s, alarms_away=%s,
                   alarms_paused=%s, hit_goal=%s
               WHERE id=%s""",
            (total, positivos, away, paused, hit_goal, existente["id"]),
        )
    else:
        cur4 = db_cursor(conn)
        cur4.execute(
            """INSERT INTO daily_summary
               (user_id, date, alarms_total, alarms_positive, alarms_away,
                alarms_paused, hit_goal, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, hoje, total, positivos, away, paused, hit_goal, agora),
        )

    # Atualiza streak
    cur5 = db_cursor(conn)
    cur5.execute(
        "SELECT streak_current, streak_best, streak_last_day, xp_total FROM users WHERE id=%s",
        (user_id,),
    )
    usuario = cur5.fetchone()
    novo_sc, novo_sb, novo_sl = atualizar_streak(
        usuario["streak_current"],
        usuario["streak_best"],
        usuario["streak_last_day"],
        pct >= 0.70,
        hoje,
    )

    # Bônus diário de XP
    xp_bonus = XP_BONUS_DIA if hit_goal else 0
    novo_xp = usuario["xp_total"] + xp_bonus
    novo_level, _, _ = calcular_level(novo_xp)

    cur6 = db_cursor(conn)
    cur6.execute(
        """UPDATE users
           SET streak_current=%s, streak_best=%s, streak_last_day=%s,
               xp_total=%s, level=%s, last_seen=%s
           WHERE id=%s""",
        (novo_sc, novo_sb, novo_sl, novo_xp, novo_level, agora, user_id),
    )

    verificar_badges_fim_dia(user_id, hoje, conn)


class ConfigBody(BaseModel):
    interval_min: int


@router.post("/config")
def session_config(body: ConfigBody, authorization: Optional[str] = Header(default=None)):
    _require_admin(authorization)
    if body.interval_min < 1 or body.interval_min > 7200:
        raise HTTPException(status_code=422, detail="interval_min deve ser entre 1 e 7200")
    agora = _agora()
    conn = get_conn()
    try:
        cur = db_cursor(conn)
        cur.execute(
            "UPDATE session_state SET interval_min=%s, updated_at=%s WHERE id=1",
            (body.interval_min, agora),
        )
        conn.commit()
        return _session_response(conn)
    finally:
        release(conn)
