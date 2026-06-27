import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

from database import init_db
from routers import session, alarm, status, admin

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cria tabelas no banco na inicialização
    init_db()
    yield


app = FastAPI(
    title="CACTO API",
    description="Sistema de hidratação gamificado do Grupo Quatro5",
    version=APP_VERSION,
    lifespan=lifespan,
)

app.include_router(session.router)
app.include_router(alarm.router)
app.include_router(status.router)
app.include_router(admin.router)


@app.get("/health", tags=["infra"])
def health():
    return {"status": "ok", "version": APP_VERSION}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
