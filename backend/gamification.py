"""Regras de gamificação do CACTO — XP, níveis, streaks e badges."""

from datetime import datetime, date, timedelta

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
# Meta diária para streak
# ---------------------------------------------------------------------------
META_STREAK_PCT = 0.70
META_GOAL_PCT   = 0.75  # usada no hit_goal / bônus diário

XP_BONUS_DIA = 50

# ---------------------------------------------------------------------------
# Funções principais
# ---------------------------------------------------------------------------

def calcular_xp(response: str, response_secs: float | None, streak_current: int) -> int:
    """Calcula o XP final de um evento, aplicando bônus de velocidade e streak."""
    xp_base = XP_BASE.get(response, 0)
    if xp_base == 0:
        return 0

    # Bônus de velocidade (apenas em respostas normais, não catchup)
    xp_velocidade = 0
    if response not in ("catchup_yes", "catchup_no") and response_secs is not None:
        if response_secs < 3:
            xp_velocidade = 5
        elif response_secs < 5:
            xp_velocidade = 2

    # Multiplicador de streak (não se aplica a catchup)
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
    """
    Atualiza streak_current, streak_best e streak_last_day.
    Retorna (novo_streak_current, novo_streak_best, novo_streak_last_day).
    """
    if not hit_meta:
        # Não bateu a meta hoje, streak zera
        return 0, streak_best, hoje

    ontem = (date.fromisoformat(hoje) - timedelta(days=1)).isoformat()

    if streak_last_day == ontem:
        novo_current = streak_current + 1
    elif streak_last_day == hoje:
        # Já foi contado hoje (sessão fechada duas vezes)
        novo_current = streak_current
    else:
        # Quebrou a sequência
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


def verificar_badges_evento(
    user_id: int,
    response: str,
    conn,
) -> list[str]:
    """
    Verifica e concede badges disparadas por evento individual.
    Retorna lista de badge_keys conquistadas agora.
    """
    novos = []

    # primeiro_gole — primeiro evento positivo do usuário
    if response in ("drank", "empty_bottle", "catchup_yes"):
        ja_tem = conn.execute(
            "SELECT 1 FROM badges WHERE user_id=? AND badge_key='primeiro_gole'",
            (user_id,),
        ).fetchone()
        if not ja_tem:
            _conceder_badge(user_id, "primeiro_gole", conn)
            novos.append("primeiro_gole")

    # em_chamas — streak atinge 7
    usuario = conn.execute(
        "SELECT streak_current FROM users WHERE id=?", (user_id,)
    ).fetchone()
    if usuario and usuario["streak_current"] >= 7:
        ja_tem = conn.execute(
            "SELECT 1 FROM badges WHERE user_id=? AND badge_key='em_chamas'",
            (user_id,),
        ).fetchone()
        if not ja_tem:
            _conceder_badge(user_id, "em_chamas", conn)
            novos.append("em_chamas")

    # diamante — streak atinge 30
    if usuario and usuario["streak_current"] >= 30:
        ja_tem = conn.execute(
            "SELECT 1 FROM badges WHERE user_id=? AND badge_key='diamante'",
            (user_id,),
        ).fetchone()
        if not ja_tem:
            _conceder_badge(user_id, "diamante", conn)
            novos.append("diamante")

    # abastecedor — 50 empty_bottle no total
    if response == "empty_bottle":
        total_empty = conn.execute(
            "SELECT COUNT(*) AS c FROM water_events WHERE user_id=? AND response='empty_bottle'",
            (user_id,),
        ).fetchone()["c"]
        if total_empty >= 50:
            ja_tem = conn.execute(
                "SELECT 1 FROM badges WHERE user_id=? AND badge_key='abastecedor'",
                (user_id,),
            ).fetchone()
            if not ja_tem:
                _conceder_badge(user_id, "abastecedor", conn)
                novos.append("abastecedor")

    return novos


def verificar_badges_fim_dia(user_id: int, hoje: str, conn) -> list[str]:
    """
    Verifica badges que só podem ser concedidas ao fechar o dia.
    Retorna lista de badge_keys conquistadas agora.
    """
    novos = []

    eventos_hoje = conn.execute(
        """SELECT response, response_secs
           FROM water_events
           WHERE user_id=? AND DATE(alarm_time)=?""",
        (user_id, hoje),
    ).fetchall()

    if not eventos_hoje:
        return novos

    positivos = [e for e in eventos_hoje if e["response"] in ("drank", "empty_bottle")]
    total = len(eventos_hoje)

    # mare_alta — 100% dos alarmes positivos
    if total > 0 and len(positivos) == total:
        ja_tem = conn.execute(
            "SELECT 1 FROM badges WHERE user_id=? AND badge_key='mare_alta'",
            (user_id,),
        ).fetchone()
        if not ja_tem:
            _conceder_badge(user_id, "mare_alta", conn)
            novos.append("mare_alta")

    # relampago — todos respondidos em < 3s
    tempos = [e["response_secs"] for e in positivos if e["response_secs"] is not None]
    if positivos and tempos and all(t < 3 for t in tempos) and len(tempos) == total:
        ja_tem = conn.execute(
            "SELECT 1 FROM badges WHERE user_id=? AND badge_key='relampago'",
            (user_id,),
        ).fetchone()
        if not ja_tem:
            _conceder_badge(user_id, "relampago", conn)
            novos.append("relampago")

    return novos


def _conceder_badge(user_id: int, badge_key: str, conn):
    agora = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO badges (user_id, badge_key, earned_at) VALUES (?, ?, ?)",
        (user_id, badge_key, agora),
    )
