"""Registro, login e perfil do usuário."""

import uuid
import hashlib
from datetime import datetime
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from database import get_conn, release, cursor as db_cursor

router = APIRouter(tags=["auth"])


def _hash(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()


def _verify(pwd: str, stored: str) -> bool:
    return hashlib.sha256(pwd.encode()).hexdigest() == stored


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
    cur = db_cursor(conn)
    cur.execute("SELECT * FROM users WHERE token=%s", (token,))
    usuario = cur.fetchone()
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
    senha_hash = _hash(body.password)

    conn = get_conn()
    try:
        cur = db_cursor(conn)
        cur.execute("SELECT id FROM users WHERE email=%s", (body.email,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Email já cadastrado")

        cur.execute(
            """INSERT INTO users (name, email, password_hash, token, created_at)
               VALUES (%s, %s, %s, %s, %s)""",
            (body.name, body.email, senha_hash, token, agora),
        )

        cur.execute(
            "SELECT id, name, level, xp_total FROM users WHERE token=%s", (token,)
        )
        usuario = cur.fetchone()
        conn.commit()
    finally:
        release(conn)

    return {
        "token": token,
        "user_id": usuario["id"],
        "name": usuario["name"],
        "level": usuario["level"],
        "xp_total": usuario["xp_total"],
    }


@router.post("/login")
def login(body: LoginBody):
    conn = get_conn()
    try:
        cur = db_cursor(conn)
        cur.execute("SELECT * FROM users WHERE email=%s", (body.email,))
        usuario = cur.fetchone()
    finally:
        release(conn)

    if not usuario or not _verify(body.password, usuario["password_hash"]):
        raise HTTPException(status_code=401, detail="Email ou senha incorretos")

    return {
        "token": usuario["token"],
        "user_id": usuario["id"],
        "name": usuario["name"],
        "email": usuario["email"],
        "is_admin": bool(usuario["is_admin"]),
        "level": usuario["level"],
        "xp_total": usuario["xp_total"],
        "streak_current": usuario["streak_current"],
    }


@router.get("/me")
def me(authorization: Optional[str] = Header(default=None)):
    token = extrair_token(authorization)

    conn = get_conn()
    try:
        usuario = get_current_user(token, conn)

        cur = db_cursor(conn)
        cur.execute(
            "SELECT badge_key, earned_at FROM badges WHERE user_id=%s ORDER BY earned_at",
            (usuario["id"],),
        )
        badges = cur.fetchall()
    finally:
        release(conn)

    return {
        "id": usuario["id"],
        "name": usuario["name"],
        "email": usuario["email"],
        "is_admin": bool(usuario["is_admin"]),
        "level": usuario["level"],
        "xp_total": usuario["xp_total"],
        "streak_current": usuario["streak_current"],
        "streak_best": usuario["streak_best"],
        "popup_mode": usuario["popup_mode"],
        "agent_version": usuario["agent_version"],
        "last_seen": usuario["last_seen"],
        "created_at": str(usuario["created_at"]),
        "badges": [{"key": b["badge_key"], "earned_at": b["earned_at"]} for b in badges],
    }
