from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import create_tables
from app.routers import (
    auth_router, business_router, chat_router,
    document_router, billing_router, team_router, integration_router,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    await create_tables()
    try:
        from app.embeddings import embed_sync
        embed_sync(["warmup"])
    except Exception:
        pass
    yield


app = FastAPI(
    title="Business Buddy API",
    version="0.3.0",
    description="AI Business Consultant — Phase 3 (billing + team + integrations)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(business_router)
app.include_router(chat_router)
app.include_router(document_router)
app.include_router(billing_router)
app.include_router(team_router)
app.include_router(integration_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.3.0"}
