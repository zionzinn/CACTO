import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from database import get_db
from models import AlarmAckRequest

router = APIRouter(prefix="/alarm", tags=["alarm"])

TIPOS_VALIDOS = {"drink", "miss", "away"}


@router.post("/ack")
def alarm_ack(body: AlarmAckRequest):
    if body.ack_type not in TIPOS_VALIDOS:
        raise HTTPException(
            status_code=422,
            detail=f"ack_type inválido. Use: {TIPOS_VALIDOS}",
        )

    agora = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        sessao = conn.execute(
            "SELECT id FROM sessions WHERE id = ? AND user_id = ?",
            (body.session_id, body.user_id),
        ).fetchone()
        if sessao is None:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")

        conn.execute(
            """INSERT INTO alarms (id, session_id, user_id, fired_at, acked_at, ack_type)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                body.session_id,
                body.user_id,
                body.fired_at,
                agora,
                body.ack_type,
            ),
        )

    return {"ok": True}
