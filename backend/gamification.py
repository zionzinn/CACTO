"""Regras de gamificação do CACTO — XP, níveis, streaks e badges."""

from datetime import datetime, date, timedelta
from database import cursor as db_cursor

# ---------------------------------------------------------------------------
# XP base por tipo de resposta
# ---------------------------------------------------------------------------
XP_BASE = {
    "drank": 10,
    "empty_bottle": 8,
    "catchup_yes": 5,
    "catchup_no": 0,
    "timeout": 0,
    "away": 0,
}

# ---------------------------------------------------------------------------
# Níveis
# ---------------------------------------------------------------------------
LEVELS = [
    (1,  "Girino",   0),
    (2,  "Peixinho", 500),
    (3,  "Golfinho", 1_500),
    (4,  "Tubarão",  4_000),
    (5,  "Baleia",   10_000),
    (6,  "Oceano",   25_000),
]

# ---------------------------------------------------------------------------
# Metas diárias
# ---------------------------------------------------------------------------
META_STREAK_PCT = 0.70
META_GOAL_PCT   = 0.75

XP_BONUS_DIA = 50

# ---------------------------------------------------------------------------
# Funções de XP
# ---------------------------------------------------------------------------

def calcular_xp(response: str, response_secs: float | None, streak_current: int) -> int:
    """Calcula XP final do evento com bônus de velocidade e multiplicador de streak."""
    xp_base = XP_BASE.get(response, 0)
    if xp_base == 0:
        return 0

    xp_velocidade = 0
    if response not in ("catchup_yes", "catchup_no") and response_secs is not None:
        if response_secs < 3:
            xp_velocidade = 5
        elif response_secs < 5:
            xp_velocidade = 2

    if response in ("catchup_yes", "catchup_no"):
        multiplicador = 1.0
    else:
        multiplicador = _multiplicador_streak(streak_current)

    return round((xp_base + xp_velocidade) * multiplicador)


def _multiplicador_streak(streak: int) -> float:
    if streak >= 30:
        return 2.0
    if streak >= 7:
        return 1.5
    if streak >= 3:
        return 1.2
    return 1.0


def calcular_level(xp_total: int) -> tuple[int, str, int | None]:
    """Retorna (level, level_name, xp_para_proximo) dado o xp_total."""
    level_atual = LEVELS[0]
    for lvl in LEVELS:
        if xp_total >= lvl[2]:
            level_atual = lvl

    proximo = None
    for lvl in LEVELS:
        if lvl[0] == level_atual[0] + 1:
            proximo = lvl[2] - xp_total
            break

    return level_atual[0], level_atual[1], proximo


def atualizar_streak(
    streak_current: int,
    streak_best: int,
    streak_last_day: str | None,
    hit_meta: bool,
    hoje: str,
) -> tuple[int, int, str]:
    """Retorna (novo_streak_current, novo_streak_best, novo_streak_last_day)."""
    if not hit_meta:
        return 0, streak_best, hoje

    ontem = (date.fromisoformat(hoje) - timedelta(days=1)).isoformat()

    if streak_last_day == ontem:
        novo_current = streak_current + 1
    elif streak_last_day == hoje:
        novo_current = streak_current
    else:
        novo_current = 1

    novo_best = max(streak_best, novo_current)
    return novo_current, novo_best, hoje


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------

BADGES_DEFINICOES = {
    "primeiro_gole":  "Primeiro Gole",
    "mare_alta":      "Maré Alta",
    "relampago":      "Relâmpago",
    "diamante":       "Diamante",
    "em_chamas":      "Em Chamas",
    "abastecedor":    "Abastecedor",
    "cacto_seco":     "Cacto Seco",
    "rei_da_semana":  "Rei da Semana",
}


def verificar_badges_evento(user_id: int, response: str, conn) -> list[str]:
    """Verifica e concede badges disparadas por evento. Retorna lista de badge_keys novas."""
    novos = []

    # primeiro_gole — primeiro evento positivo do usuário
    if response in ("drank", "empty_bottle", "catchup_yes"):
        cur = db_cursor(conn)
        cur.execute(
            "SELECT 1 FROM badges WHERE user_id=%s AND badge_key='primeiro_gole'",
            (user_id,),
        )
        if not cur.fetchone():
            _conceder_badge(user_id, "primeiro_gole", conn)
            novos.append("primeiro_gole")

    # em_chamas e diamante — baseados no streak atual
    cur = db_cursor(conn)
    cur.execute("SELECT streak_current FROM users WHERE id=%s", (user_id,))
    usuario = cur.fetchone()

    if usuario and usuario["streak_current"] >= 7:
        cur2 = db_cursor(conn)
        cur2.execute(
            "SELECT 1 FROM badges WHERE user_id=%s AND badge_key='em_chamas'",
            (user_id,),
        )
        if not cur2.fetchone():
            _conceder_badge(user_id, "em_chamas", conn)
            novos.append("em_chamas")

    if usuario and usuario["streak_current"] >= 30:
        cur3 = db_cursor(conn)
        cur3.execute(
            "SELECT 1 FROM badges WHERE user_id=%s AND badge_key='diamante'",
            (user_id,),
        )
        if not cur3.fetchone():
            _conceder_badge(user_id, "diamante", conn)
            novos.append("diamante")

    # abastecedor — 50 empty_bottle no total
    if response == "empty_bottle":
        cur4 = db_cursor(conn)
        cur4.execute(
            "SELECT COUNT(*) AS c FROM water_events WHERE user_id=%s AND response='empty_bottle'",
            (user_id,),
        )
        total_empty = cur4.fetchone()["c"]
        if total_empty >= 50:
            cur5 = db_cursor(conn)
            cur5.execute(
                "SELECT 1 FROM badges WHERE user_id=%s AND badge_key='abastecedor'",
                (user_id,),
            )
            if not cur5.fetchone():
                _conceder_badge(user_id, "abastecedor", conn)
                novos.append("abastecedor")

    return novos


def verificar_badges_fim_dia(user_id: int, hoje: str, conn) -> list[str]:
    """Verifica badges de fim de dia. Retorna lista de badge_keys novas."""
    novos = []

    cur = db_cursor(conn)
    cur.execute(
        """SELECT response, response_secs
           FROM water_events
           WHERE user_id=%s AND LEFT(alarm_time, 10)=%s""",
        (user_id, hoje),
    )
    eventos_hoje = cur.fetchall()

    if not eventos_hoje:
        return novos

    positivos = [e for e in eventos_hoje if e["response"] in ("drank", "empty_bottle")]
    total = len(eventos_hoje)

    # mare_alta — 100% dos alarmes positivos
    if total > 0 and len(positivos) == total:
        cur2 = db_cursor(conn)
        cur2.execute(
            "SELECT 1 FROM badges WHERE user_id=%s AND badge_key='mare_alta'",
            (user_id,),
        )
        if not cur2.fetchone():
            _conceder_badge(user_id, "mare_alta", conn)
            novos.append("mare_alta")

    # relampago — todos os positivos respondidos em < 3s
    tempos = [e["response_secs"] for e in positivos if e["response_secs"] is not None]
    if positivos and tempos and all(t < 3 for t in tempos) and len(tempos) == total:
        cur3 = db_cursor(conn)
        cur3.execute(
            "SELECT 1 FROM badges WHERE user_id=%s AND badge_key='relampago'",
            (user_id,),
        )
        if not cur3.fetchone():
            _conceder_badge(user_id, "relampago", conn)
            novos.append("relampago")

    return novos


def _conceder_badge(user_id: int, badge_key: str, conn):
    agora = datetime.utcnow().isoformat()
    cur = db_cursor(conn)
    cur.execute(
        "INSERT INTO badges (user_id, badge_key, earned_at) VALUES (%s, %s, %s)",
        (user_id, badge_key, agora),
    )
