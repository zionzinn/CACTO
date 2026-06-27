import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from database import get_db
from models import (
    SessionStartRequest, SessionStartResponse, AdminStateResponse,
    SessionEndRequest, calcular_badge,
    XP_POR_DRINK, XP_BONUS_META_DIA, META_MINIMA_PCT,
)

router = APIRouter(prefix="/session", tags=["session"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@router.post("/start", response_model=SessionStartResponse)
def session_start(body: SessionStartRequest):
    with get_db() as conn:
        # Registra ou atualiza usuário
        agora = _now_iso()
        usuario = conn.execute(
            "SELECT id FROM users WHERE computer_id = ?", (body.computer_id,)
        ).fetchone()

        if usuario is None:
            user_id = body.user_id or str(uuid.uuid4())
            conn.execute(
                """INSERT INTO users (id, name, computer_id, created_at)
                   VALUES (?, ?, ?, ?)""",
                (user_id, body.name, body.computer_id, agora),
            )
        else:
            user_id = usuario["id"]
            # Atualiza nome caso tenha mudado
            conn.execute(
                "UPDATE users SET name = ? WHERE id = ?",
                (body.name, user_id),
            )

        # Fecha sessão anterior aberta do mesmo usuário, se existir
        conn.execute(
            """UPDATE sessions SET ended_at = ?
               WHERE user_id = ? AND ended_at IS NULL""",
            (agora, user_id),
        )

        # Cria nova sessão
        session_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO sessions (id, user_id, started_at) VALUES (?, ?, ?)",
            (session_id, user_id, agora),
        )

        # Lê estado do admin
        estado = conn.execute(
            "SELECT paused, version FROM admin_state WHERE id = 1"
        ).fetchone()

    return SessionStartResponse(
        session_id=session_id,
        admin_state=AdminStateResponse(
            paused=bool(estado["paused"]),
            version=estado["version"],
        ),
    )


@router.post("/end")
def session_end(body: SessionEndRequest):
    agora = _now_iso()
    hoje = _today()

    with get_db() as conn:
        sessao = conn.execute(
            "SELECT id, user_id FROM sessions WHERE id = ? AND user_id = ?",
            (body.session_id, body.user_id),
        ).fetchone()
        if sessao is None:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")

        # Fecha sessão
        conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (agora, body.session_id),
        )

        # Calcula resumo do dia
        contagem = conn.execute(
            """SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN ack_type = 'drink' THEN 1 ELSE 0 END) AS bebidos
               FROM alarms
               WHERE user_id = ? AND DATE(fired_at) = ?""",
            (body.user_id, hoje),
        ).fetchone()

        total = contagem["total"] or 0
        bebidos = contagem["bebidos"] or 0
        pct = (bebidos / total) if total > 0 else 0.0
        meta_batida = int(pct >= META_MINIMA_PCT and total > 0)

        xp_ganho = bebidos * XP_POR_DRINK
        if meta_batida:
            xp_ganho += XP_BONUS_META_DIA

        # Upsert no daily_summary
        resumo_existente = conn.execute(
            "SELECT id FROM daily_summary WHERE user_id = ? AND date = ?",
            (body.user_id, hoje),
        ).fetchone()

        if resumo_existente:
            conn.execute(
                """UPDATE daily_summary
                   SET alarms_total = ?, alarms_acked = ?, goal_pct = ?,
                       goal_met = ?, xp_earned = ?
                   WHERE id = ?""",
                (total, bebidos, pct, meta_batida, xp_ganho, resumo_existente["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO daily_summary
                   (id, user_id, date, alarms_total, alarms_acked, goal_pct, goal_met, xp_earned)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), body.user_id, hoje, total, bebidos, pct, meta_batida, xp_ganho),
            )

        # Atualiza XP e badge do usuário
        usuario = conn.execute(
            "SELECT xp_total FROM users WHERE id = ?", (body.user_id,)
        ).fetchone()
        novo_xp = (usuario["xp_total"] or 0) + xp_ganho
        novo_badge = calcular_badge(novo_xp)

        conn.execute(
            "UPDATE users SET xp_total = ?, badge = ? WHERE id = ?",
            (novo_xp, novo_badge, body.user_id),
        )

    return {"ok": True}
