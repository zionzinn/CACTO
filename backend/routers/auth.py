"""Registro, login e perfil do usuário."""

import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from passlib.context import CryptContext
from typing import Optional

from database import get_db

router = APIRouter(tags=["auth"])

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterBody(BaseModel):
    name: str
    email: str
    password: str


class LoginBody(BaseModel):
    email: str
    password: str


# ---------------------------------------------------------------------------
# Helpers de autenticação (importados pelos outros routers)
# ---------------------------------------------------------------------------

def get_current_user(token: str, conn):
    """Busca usuário pelo token ou levanta 401."""
    usuario = conn.execute(
        "SELECT * FROM users WHERE token=?", (token,)
    ).fetchone()
    if not usuario:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    return usuario


def extrair_token(authorization: Optional[str]) -> str:
    """Extrai o token do header Authorization: Bearer <token>."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Header de autorização ausente ou inválido")
    return authorization[len("Bearer "):]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register")
def register(body: RegisterBody):
    agora = datetime.utcnow().isoformat()
    token = str(uuid.uuid4())
    senha_hash = pwd_ctx.hash(body.password)

    with get_db() as conn:
        existente = conn.execute(
            "SELECT id FROM users WHERE email=?", (body.email,)
        ).fetchone()
        if existente:
            raise HTTPException(status_code=409, detail="Email já cadastrado")

        conn.execute(
            """INSERT INTO users (name, email, password_hash, token, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (body.name, body.email, senha_hash, token, agora),
        )
        usuario = conn.execute(
            "SELECT id, name, level, xp_total FROM users WHERE token=?", (token,)
        ).fetchone()

    return {
        "token": token,
        "user_id": usuario["id"],
        "name": usuario["name"],
        "level": usuario["level"],
        "xp_total": usuario["xp_total"],
    }


@router.post("/login")
def login(body: LoginBody):
    with get_db() as conn:
        usuario = conn.execute(
            "SELECT * FROM users WHERE email=?", (body.email,)
        ).fetchone()
        if not usuario or not pwd_ctx.verify(body.password, usuario["password_hash"]):
            raise HTTPException(status_code=401, detail="Email ou senha incorretos")

    return {
        "token": usuario["token"],
        "user_id": usuario["id"],
        "name": usuario["name"],
        "level": usuario["level"],
        "xp_total": usuario["xp_total"],
        "streak_current": usuario["streak_current"],
    }


@router.get("/me")
def me(authorization: Optional[str] = Header(default=None)):
    token = extrair_token(authorization)
    with get_db() as conn:
        usuario = get_current_user(token, conn)
        badges = conn.execute(
            "SELECT badge_key, earned_at FROM badges WHERE user_id=? ORDER BY earned_at",
            (usuario["id"],),
        ).fetchall()

    return {
        "id": usuario["id"],
        "name": usuario["name"],
        "email": usuario["email"],
        "level": usuario["level"],
        "xp_total": usuario["xp_total"],
        "streak_current": usuario["streak_current"],
        "streak_best": usuario["streak_best"],
        "popup_mode": usuario["popup_mode"],
        "agent_version": usuario["agent_version"],
        "last_seen": usuario["last_seen"],
        "created_at": usuario["created_at"],
        "badges": [{"key": b["badge_key"], "earned_at": b["earned_at"]} for b in badges],
    }
