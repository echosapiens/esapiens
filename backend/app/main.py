"""E.sapiens Bio-Orchestrator — FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import pipeline, jobs, cost, chat
from app.database import init_db

app = FastAPI(title="E.sapiens Bio-Orchestrator", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router, prefix=f"{settings.API_V1_STR}")
app.include_router(jobs.router, prefix=f"{settings.API_V1_STR}")
app.include_router(cost.router, prefix=f"{settings.API_V1_STR}")
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}")


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/health")
async def health():
    return {"status": "ok", "runtime": "split-architecture"}