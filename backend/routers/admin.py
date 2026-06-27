import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from database import get_db
from models import AdminUserItem

router = APIRouter(prefix="/admin", tags=["admin"])


def _verificar_auth(authorization: Optional[str]):
    secret = os.getenv("SECRET_KEY", "")
    if not secret:
        raise HTTPException(status_code=500, detail="SECRET_KEY não configurado no servidor")
    esperado = f"Bearer {secret}"
    if authorization != esperado:
        raise HTTPException(status_code=401, detail="Não autorizado")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/pause")
def admin_pause(authorization: Optional[str] = Header(default=None)):
    _verificar_auth(authorization)
    with get_db() as conn:
        conn.execute(
            "UPDATE admin_state SET paused = 1, paused_at = ? WHERE id = 1",
            (_now_iso(),),
        )
    return {"ok": True, "paused": True}


@router.post("/resume")
def admin_resume(authorization: Optional[str] = Header(default=None)):
    _verificar_auth(authorization)
    with get_db() as conn:
        conn.execute(
            "UPDATE admin_state SET paused = 0, resumed_at = ? WHERE id = 1",
            (_now_iso(),),
        )
    return {"ok": True, "paused": False}


@router.post("/users", response_model=list[AdminUserItem])
def admin_users(authorization: Optional[str] = Header(default=None)):
    _verificar_auth(authorization)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, computer_id, is_admin, active, xp_total, badge, created_at FROM users ORDER BY name"
        ).fetchall()

    return [
        AdminUserItem(
            id=row["id"],
            name=row["name"],
            computer_id=row["computer_id"],
            is_admin=bool(row["is_admin"]),
            active=bool(row["active"]),
            xp_total=row["xp_total"],
            badge=row["badge"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
