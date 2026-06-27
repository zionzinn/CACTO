import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_pool, init_db
from routers import auth, session, events, stats, admin

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERRO FATAL: variável de ambiente DATABASE_URL não configurada.", flush=True)
        sys.exit(1)

    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        print("ERRO FATAL: variável de ambiente SECRET_KEY não configurada.", flush=True)
        sys.exit(1)

    print(f"Iniciando CACTO API v{APP_VERSION}...", flush=True)
    init_pool()
    init_db()
    print("Banco de dados conectado e tabelas prontas.", flush=True)
    yield


app = FastAPI(
    title="CACTO API",
    description="Sistema de hidratação gamificado — Grupo Quatro5",
    version=APP_VERSION,
    lifespan=lifespan,
)

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
    from database import get_conn, release
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        release(conn)
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    return {"status": "ok", "version": APP_VERSION, "db": db_status}


@app.get("/version", tags=["infra"])
def version():
    return {"version": APP_VERSION, "download_url": ""}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
