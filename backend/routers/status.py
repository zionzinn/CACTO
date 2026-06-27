from datetime import datetime, timezone
from fastapi import APIRouter

from database import get_db
from models import StatusResponse, AdminStateResponse, UserStatusItem, RankingItem

router = APIRouter(tags=["status"])


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@router.get("/status", response_model=StatusResponse)
def get_status():
    hoje = _today()

    with get_db() as conn:
        estado = conn.execute(
            "SELECT paused, version FROM admin_state WHERE id = 1"
        ).fetchone()

        # Usuários com sessão aberta hoje
        online = conn.execute(
            """SELECT
                u.id AS user_id,
                u.name,
                u.badge,
                u.xp_total,
                COALESCE(SUM(CASE WHEN a.ack_type = 'drink' THEN 1 ELSE 0 END), 0) AS alarms_acked,
                COALESCE(COUNT(a.id), 0) AS alarms_total
               FROM users u
               JOIN sessions s ON s.user_id = u.id
               LEFT JOIN alarms a ON a.user_id = u.id AND DATE(a.fired_at) = ?
               WHERE s.ended_at IS NULL AND DATE(s.started_at) = ?
               GROUP BY u.id""",
            (hoje, hoje),
        ).fetchall()

    return StatusResponse(
        admin_state=AdminStateResponse(
            paused=bool(estado["paused"]),
            version=estado["version"],
        ),
        usuarios_online=[
            UserStatusItem(
                user_id=row["user_id"],
                name=row["name"],
                badge=row["badge"],
                xp_total=row["xp_total"],
                alarms_acked=row["alarms_acked"],
                alarms_total=row["alarms_total"],
            )
            for row in online
        ],
    )


@router.get("/ranking", response_model=list[RankingItem])
def get_ranking():
    hoje = _today()

    with get_db() as conn:
        rows = conn.execute(
            """SELECT
                u.name AS nome,
                u.badge,
                u.xp_total,
                COALESCE(SUM(CASE WHEN a.ack_type = 'drink' THEN 1 ELSE 0 END), 0) AS alarms_acked,
                COALESCE(COUNT(a.id), 0) AS alarms_total
               FROM users u
               LEFT JOIN alarms a ON a.user_id = u.id AND DATE(a.fired_at) = ?
               WHERE u.active = 1
               GROUP BY u.id
               ORDER BY
                 CASE WHEN COALESCE(COUNT(a.id), 0) = 0 THEN 0
                      ELSE CAST(SUM(CASE WHEN a.ack_type = 'drink' THEN 1 ELSE 0 END) AS REAL)
                           / COUNT(a.id)
                 END DESC,
                 u.xp_total DESC""",
            (hoje,),
        ).fetchall()

    return [
        RankingItem(
            nome=row["nome"],
            alarms_acked=row["alarms_acked"],
            alarms_total=row["alarms_total"],
            pct=round(row["alarms_acked"] / row["alarms_total"], 4)
            if row["alarms_total"] > 0
            else 0.0,
            badge=row["badge"],
            xp_total=row["xp_total"],
        )
        for row in rows
    ]
