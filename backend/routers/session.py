"""Controle da sessão global de hidratação (admin only)."""

import os
from datetime import datetime, date, timedelta
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from database import get_db
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
    token = authorization or ""
    if token.startswith("Bearer "):
        token = token[7:]
    # Aceita SECRET_KEY direto ou usuário com is_admin=1
    if token == secret:
        return
    from database import get_db as _get_db
    with _get_db() as conn:
        u = conn.execute(
            "SELECT is_admin FROM users WHERE token=?", (token,)
        ).fetchone()
        if u and u["is_admin"] == 1:
            return
    raise HTTPException(status_code=401, detail="Acesso restrito ao administrador")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agora() -> str:
    return datetime.utcnow().isoformat()


def _hoje() -> str:
    return date.today().isoformat()


def _ler_session(conn) -> dict:
    row = conn.execute("SELECT * FROM session_state WHERE id=1").fetchone()
    return dict(row) if row else {}


def _calcular_next_alarm(state: dict) -> Optional[str]:
    """Calcula o datetime ISO do próximo alarme, ou None."""
    if not state.get("is_active") or state.get("is_paused"):
        return None
    try:
        inicio = datetime.fromisoformat(state["session_start"])
        agora_dt = datetime.utcnow()
        intervalo_s = (state["interval_min"] or 25) * 60
        elapsed = (agora_dt - inicio).total_seconds() - (state["paused_elapsed"] or 0)
        falta = intervalo_s - (elapsed % intervalo_s)
        next_dt = agora_dt + timedelta(seconds=falta)
        return next_dt.isoformat()
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
    """Retorna o estado atual da sessão — aberto, sem auth."""
    with get_db() as conn:
        return _session_response(conn)


@router.post("/start")
def session_start(authorization: Optional[str] = Header(default=None)):
    _require_admin(authorization)
    agora = _agora()
    with get_db() as conn:
        conn.execute(
            """UPDATE session_state
               SET is_active=1, is_paused=0, session_start=?, paused_elapsed=0,
                   paused_at=NULL, alarms_fired=0, updated_at=?
               WHERE id=1""",
            (agora, agora),
        )
        return _session_response(conn)


@router.post("/pause")
def session_pause(authorization: Optional[str] = Header(default=None)):
    _require_admin(authorization)
    agora = _agora()
    with get_db() as conn:
        state = _ler_session(conn)
        if not state.get("is_active"):
            raise HTTPException(status_code=400, detail="Sessão não está ativa")
        conn.execute(
            "UPDATE session_state SET is_paused=1, paused_at=?, updated_at=? WHERE id=1",
            (agora, agora),
        )
        return _session_response(conn)


@router.post("/resume")
def session_resume(authorization: Optional[str] = Header(default=None)):
    _require_admin(authorization)
    agora = _agora()
    with get_db() as conn:
        state = _ler_session(conn)
        if not state.get("is_paused"):
            raise HTTPException(status_code=400, detail="Sessão não está pausada")

        # Acumula o tempo que ficou pausado
        tempo_pausado = 0
        if state.get("paused_at"):
            try:
                pausou_em = datetime.fromisoformat(state["paused_at"])
                tempo_pausado = int((datetime.utcnow() - pausou_em).total_seconds())
            except Exception:
                pass

        novo_elapsed = (state.get("paused_elapsed") or 0) + tempo_pausado
        conn.execute(
            """UPDATE session_state
               SET is_paused=0, paused_at=NULL, paused_elapsed=?, updated_at=?
               WHERE id=1""",
            (novo_elapsed, agora),
        )
        return _session_response(conn)


@router.post("/end")
def session_end(authorization: Optional[str] = Header(default=None)):
    _require_admin(authorization)
    agora = _agora()
    hoje = _hoje()

    summaries = []

    with get_db() as conn:
        conn.execute(
            "UPDATE session_state SET is_active=0, is_paused=0, updated_at=? WHERE id=1",
            (agora,),
        )

        # Usuários que tiveram eventos hoje
        usuarios_hoje = conn.execute(
            """SELECT DISTINCT user_id FROM water_events
               WHERE DATE(alarm_time)=?""",
            (hoje,),
        ).fetchall()

        for row in usuarios_hoje:
            uid = row["user_id"]
            _fechar_dia_usuario(uid, hoje, conn, agora)
            usuario = conn.execute(
                "SELECT name, xp_total, level, streak_current FROM users WHERE id=?", (uid,)
            ).fetchone()
            summaries.append({
                "user_id": uid,
                "name": usuario["name"],
                "xp_total": usuario["xp_total"],
                "level": usuario["level"],
                "streak_current": usuario["streak_current"],
            })

    return {"ok": True, "summaries": summaries}


def _fechar_dia_usuario(user_id: int, hoje: str, conn, agora: str):
    """Calcula daily_summary, streaks, bônus de XP e badges de fim de dia."""
    eventos = conn.execute(
        """SELECT response FROM water_events
           WHERE user_id=? AND DATE(alarm_time)=?""",
        (user_id, hoje),
    ).fetchall()

    if not eventos:
        return

    total = len(eventos)
    positivos = sum(1 for e in eventos if e["response"] in ("drank", "empty_bottle"))
    away = sum(1 for e in eventos if e["response"] == "away")
    paused = sum(1 for e in eventos if e["was_paused"])
    pct = positivos / total if total else 0
    hit_goal = int(pct >= META_GOAL_PCT)

    # Upsert no daily_summary
    existente = conn.execute(
        "SELECT id FROM daily_summary WHERE user_id=? AND date=?", (user_id, hoje)
    ).fetchone()
    if existente:
        conn.execute(
            """UPDATE daily_summary
               SET alarms_total=?, alarms_positive=?, alarms_away=?,
                   alarms_paused=?, hit_goal=?, updated_at=?
               WHERE id=?""",
            (total, positivos, away, paused, hit_goal, agora, existente["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO daily_summary
               (user_id, date, alarms_total, alarms_positive, alarms_away,
                alarms_paused, hit_goal, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, hoje, total, positivos, away, paused, hit_goal, agora),
        )

    # Streak
    usuario = conn.execute(
        "SELECT streak_current, streak_best, streak_last_day FROM users WHERE id=?",
        (user_id,),
    ).fetchone()
    novo_sc, novo_sb, novo_sl = atualizar_streak(
        usuario["streak_current"],
        usuario["streak_best"],
        usuario["streak_last_day"],
        bool(pct >= 0.70),
        hoje,
    )

    # Bônus diário de XP
    xp_bonus = XP_BONUS_DIA if hit_goal else 0
    xp_atual = conn.execute("SELECT xp_total FROM users WHERE id=?", (user_id,)).fetchone()["xp_total"]
    novo_xp = xp_atual + xp_bonus
    novo_level, _, _ = calcular_level(novo_xp)

    conn.execute(
        """UPDATE users
           SET streak_current=?, streak_best=?, streak_last_day=?,
               xp_total=?, level=?, last_seen=?
           WHERE id=?""",
        (novo_sc, novo_sb, novo_sl, novo_xp, novo_level, agora, user_id),
    )

    # Badges de fim de dia
    verificar_badges_fim_dia(user_id, hoje, conn)


class ConfigBody(BaseModel):
    interval_min: int


@router.post("/config")
def session_config(body: ConfigBody, authorization: Optional[str] = Header(default=None)):
    _require_admin(authorization)
    if body.interval_min < 1 or body.interval_min > 120:
        raise HTTPException(status_code=422, detail="interval_min deve ser entre 1 e 120")
    agora = _agora()
    with get_db() as conn:
        conn.execute(
            "UPDATE session_state SET interval_min=?, updated_at=? WHERE id=1",
            (body.interval_min, agora),
        )
        return _session_response(conn)
