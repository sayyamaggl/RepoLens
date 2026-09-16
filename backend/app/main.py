"""
RepoLens Comprehension Engine — FastAPI application entry point.

This is the main app that mounts all routes and configures middleware.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.api.routes import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Filter out the constant /status polling logs
        return "/status" not in record.getMessage()

logging.getLogger("uvicorn.access").addFilter(EndpointFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    logger.info("RepoLens starting up...")
    await init_db()
    logger.info("Database initialized")
    
    import asyncio
    from sqlalchemy import select
    from app.models import Repo
    from app.database import async_session_factory
    from app.api.routes import _run_pipeline_background

    # Resume interrupted tasks
    async with async_session_factory() as session:
        result = await session.execute(
            select(Repo).where(Repo.status.in_(["cloning", "parsing", "graphing", "analyzing", "summarizing"]))
        )
        interrupted_repos = result.scalars().all()
        for repo in interrupted_repos:
            logger.info(f"Resuming interrupted analysis for {repo.url}")
            asyncio.create_task(_run_pipeline_background(repo.url, is_resume=True))
            
    yield
    logger.info("RepoLens shutting down...")


app = FastAPI(
    title="RepoLens Comprehension Engine",
    description=(
        "AI-powered tool that instantly explains any Git repository's architecture. "
        "Deterministic structural analysis + LLM-grounded summaries."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "repolens"}