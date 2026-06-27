from pydantic import BaseModel
from typing import Optional


# --- Thresholds de XP para cada badge ---
BADGE_THRESHOLDS = [
    (1500, "CACTO LENDÁRIO"),
    (700,  "CACTO FLORIDO"),
    (300,  "CACTO"),
    (100,  "BROTO"),
    (0,    "SEMENTE"),
]

XP_POR_DRINK = 10
XP_BONUS_META_DIA = 50
META_MINIMA_PCT = 0.75


def calcular_badge(xp_total: int) -> str:
    for minimo, badge in BADGE_THRESHOLDS:
        if xp_total >= minimo:
            return badge
    return "SEMENTE"


# --- Schemas de request ---

class SessionStartRequest(BaseModel):
    user_id: str
    computer_id: str
    name: str


class SessionEndRequest(BaseModel):
    session_id: str
    user_id: str


class AlarmAckRequest(BaseModel):
    session_id: str
    user_id: str
    ack_type: str  # 'drink' | 'miss' | 'away'
    fired_at: str


# --- Schemas de response ---

class AdminStateResponse(BaseModel):
    paused: bool
    version: str


class SessionStartResponse(BaseModel):
    session_id: str
    admin_state: AdminStateResponse


class UserStatusItem(BaseModel):
    user_id: str
    name: str
    badge: str
    xp_total: int
    alarms_acked: int
    alarms_total: int


class StatusResponse(BaseModel):
    admin_state: AdminStateResponse
    usuarios_online: list[UserStatusItem]


class RankingItem(BaseModel):
    nome: str
    alarms_acked: int
    alarms_total: int
    pct: float
    badge: str
    xp_total: int


class AdminUserItem(BaseModel):
    id: str
    name: str
    computer_id: str
    is_admin: bool
    active: bool
    xp_total: int
    badge: str
    created_at: Optional[str]
