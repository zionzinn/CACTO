"""Estatísticas individuais, ranking e visão geral do time."""

from datetime import datetime, date, timedelta
from fastapi import APIRouter, Header
from typing import Optional

from database import get_conn, release, cursor as db_cursor
from routers.auth import get_current_user, extrair_token
from gamification import calcular_level, LEVELS
from routers.session import _calcular_next_alarm, _ler_session

router = APIRouter(tags=["stats"])

LEVEL_NAMES = {lvl[0]: lvl[1] for lvl in LEVELS}


def _hoje() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# /stats/me
# ---------------------------------------------------------------------------

@router.get("/stats/me")
def stats_me(authorization: Optional[str] = Header(default=None)):
    token = extrair_token(authorization)

    conn = get_conn()
    try:
        usuario = get_current_user(token, conn)

        # Histórico dos últimos 7 dias
        sete_dias = [
            (date.today() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)
        ]
        historico = []
        for d in sete_dias:
            cur = db_cursor(conn)
            cur.execute(
                "SELECT * FROM daily_summary WHERE user_id=%s AND date=%s",
                (usuario["id"], d),
            )
            row = cur.fetchone()
            historico.append(dict(row) if row else {"date": d, "alarms_positive": 0, "alarms_total": 0})

        cur2 = db_cursor(conn)
        cur2.execute(
            "SELECT badge_key, earned_at FROM badges WHERE user_id=%s ORDER BY earned_at",
            (usuario["id"],),
        )
        badges = cur2.fetchall()

        cur3 = db_cursor(conn)
        cur3.execute(
            """SELECT
                SUM(CASE WHEN response='drank'        THEN 1 ELSE 0 END) AS total_drank,
                SUM(CASE WHEN response='empty_bottle' THEN 1 ELSE 0 END) AS total_empty,
                SUM(CASE WHEN response='timeout'      THEN 1 ELSE 0 END) AS total_timeout
               FROM water_events WHERE user_id=%s""",
            (usuario["id"],),
        )
        totais = cur3.fetchone()

        _, level_name, xp_proximo = calcular_level(usuario["xp_total"])
    finally:
        release(conn)

    return {
        "xp_total": usuario["xp_total"],
        "level": usuario["level"],
        "level_name": level_name,
        "streak_current": usuario["streak_current"],
        "streak_best": usuario["streak_best"],
        "xp_para_proximo_nivel": xp_proximo,
        "historico_7_dias": historico,
        "badges": [{"key": b["badge_key"], "earned_at": b["earned_at"]} for b in badges],
        "total_drank": totais["total_drank"] or 0,
        "total_empty": totais["total_empty"] or 0,
        "total_timeout": totais["total_timeout"] or 0,
    }


# ---------------------------------------------------------------------------
# /stats/ranking
# ---------------------------------------------------------------------------

@router.get("/stats/ranking")
def stats_ranking(period: str = "day"):
    """Ranking por período: day | week | month."""
    hoje = date.today()
    if period == "week":
        inicio = (hoje - timedelta(days=hoje.weekday())).isoformat()
    elif period == "month":
        inicio = hoje.replace(day=1).isoformat()
    else:
        inicio = hoje.isoformat()

    conn = get_conn()
    try:
        cur = db_cursor(conn)
        cur.execute(
            """SELECT
                u.id,
                u.name,
                u.xp_total,
                u.level,
                u.streak_current,
                COALESCE(SUM(CASE WHEN we.response IN ('drank','empty_bottle') THEN 1 ELSE 0 END), 0) AS alarms_positive,
                COALESCE(COUNT(we.id), 0) AS alarms_total,
                COALESCE(SUM(we.xp_earned), 0) AS xp_periodo
               FROM users u
               LEFT JOIN water_events we
                 ON we.user_id = u.id AND LEFT(we.alarm_time, 10) >= %s
               WHERE u.is_admin = FALSE
               GROUP BY u.id, u.name, u.xp_total, u.level, u.streak_current
               ORDER BY xp_periodo DESC, alarms_positive DESC""",
            (inicio,),
        )
        rows = cur.fetchall()
    finally:
        release(conn)

    resultado = []
    for i, row in enumerate(rows, start=1):
        total = row["alarms_total"] or 0
        pos   = row["alarms_positive"] or 0
        pct   = round(pos / total, 4) if total > 0 else 0.0
        resultado.append({
            "rank": i,
            "name": row["name"],
            "xp": row["xp_periodo"],
            "alarms_positive": pos,
            "alarms_total": total,
            "pct": pct,
            "level_name": LEVEL_NAMES.get(row["level"], "Girino"),
            "streak": row["streak_current"],
        })

    return resultado


# ---------------------------------------------------------------------------
# /stats/team
# ---------------------------------------------------------------------------

@router.get("/stats/team")
def stats_team():
    """Visão geral do time — sem autenticação."""
    hoje = _hoje()
    dois_min_atras = (datetime.utcnow() - timedelta(minutes=2)).isoformat()

    conn = get_conn()
    try:
        cur = db_cursor(conn)
        cur.execute(
            "SELECT COUNT(*) AS c FROM users WHERE last_seen >= %s AND is_admin = FALSE",
            (dois_min_atras,),
        )
        total_online = cur.fetchone()["c"]

        cur2 = db_cursor(conn)
        cur2.execute(
            """SELECT COUNT(DISTINCT user_id) AS c FROM water_events
               WHERE LEFT(alarm_time, 10)=%s AND response IN ('drank','empty_bottle')""",
            (hoje,),
        )
        bebendo_hoje = cur2.fetchone()["c"]

        cur3 = db_cursor(conn)
        cur3.execute(
            """SELECT AVG(
                CASE WHEN alarms_total > 0
                     THEN CAST(alarms_positive AS REAL) / alarms_total
                     ELSE 0 END
               ) AS media_pct
               FROM daily_summary WHERE date=%s""",
            (hoje,),
        )
        medias = cur3.fetchone()
        team_pct = round((medias["media_pct"] or 0.0) * 100, 1)

        cur4 = db_cursor(conn)
        cur4.execute(
            "SELECT name, streak_current FROM users WHERE is_admin = FALSE ORDER BY streak_current DESC LIMIT 1"
        )
        top_streak = cur4.fetchone()

        state = _ler_session(conn)
        next_alarm = _calcular_next_alarm(state)
    finally:
        release(conn)

    return {
        "total_online": total_online,
        "total_drinking_today": bebendo_hoje,
        "team_pct_today": team_pct,
        "top_streak": {
            "name": top_streak["name"] if top_streak else None,
            "streak_current": top_streak["streak_current"] if top_streak else 0,
        },
        "session_active": bool(state.get("is_active")),
        "next_alarm_at": next_alarm,
    }
