import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import auth, session, events, stats, admin

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cria tabelas e estado inicial do banco ao subir
    init_db()
    yield


app = FastAPI(
    title="CACTO API",
    description="Sistema de hidratação gamificado — Grupo Quatro5",
    version=APP_VERSION,
    lifespan=lifespan,
)

# CORS aberto — o dashboard será servido de outro domínio
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(session.router)
app.include_router(events.router)
app.include_router(stats.router)
app.include_router(admin.router)


@app.get("/health", tags=["infra"])
def health():
    from database import get_connection
    try:
        conn = get_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        db_status = "connected"
    except Exception:
        db_status = "error"

    return {"status": "ok", "version": APP_VERSION, "db": db_status}


@app.get("/version", tags=["infra"])
def version():
    return {"version": APP_VERSION, "download_url": ""}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
