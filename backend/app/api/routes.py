"""
api_service — FastAPI routes for RepoLens.

Endpoints:
  POST /api/analyze          - Trigger full analysis pipeline
  GET  /api/repos            - List all analyzed repos
  GET  /api/repo/{id}/status - Pipeline progress
  GET  /api/repo/{id}/overview - Architecture narrative + insights
  GET  /api/repo/{id}/graph  - Dependency graph as nodes/edges JSON
  GET  /api/repo/{id}/files  - All files with summaries
  GET  /api/repo/{id}/file/{file_id}/summary - Per-file grounded summary
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_session, async_session_factory
from app.models import Repo, File, Dependency, ArchitectureOverview
from app.api.schemas import (
    AnalyzeRequest, AnalyzeResponse,
    RepoInfo, RepoListResponse,
    OverviewResponse, EntryPointInfo, CoreModuleInfo,
    GraphResponse, GraphNode, DependencyEdge,
    FileInfo, FileSummaryResponse,
)
from app.pipeline import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["RepoLens"])


async def _run_pipeline_background(repo_url: str, is_resume: bool = False):
    """Run the pipeline in a background task with its own session."""
    async with async_session_factory() as session:
        try:
            await run_pipeline(repo_url, session, is_resume=is_resume)
        except Exception as e:
            logger.error(f"Background pipeline failed: {e}", exc_info=True)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_repo(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Trigger analysis of a GitHub repository.
    The pipeline runs in the background; poll /repo/{id}/status for progress.
    """
    repo_url = request.repo_url.strip()

    # Validate URL
    if not repo_url.startswith("https://github.com/"):
        raise HTTPException(400, "Only public GitHub URLs are supported (https://github.com/...)")

    # Check if repo already exists
    result = await session.execute(select(Repo).where(Repo.url == repo_url))
    existing = result.scalar_one_or_none()

    if existing and existing.status in ("cloning", "parsing", "graphing", "analyzing", "summarizing"):
        return AnalyzeResponse(
            repo_id=existing.id,
            status=existing.status,
            message="Analysis already in progress",
        )

    if existing:
        repo_id = existing.id
        existing.status = "cloning"
        existing.error_message = None
        await session.commit()
    else:
        repo = Repo(url=repo_url, status="cloning")
        session.add(repo)
        await session.commit()
        await session.refresh(repo)
        repo_id = repo.id

    # Run pipeline in background
    background_tasks.add_task(_run_pipeline_background, repo_url)

    return AnalyzeResponse(
        repo_id=repo_id,
        status="cloning",
        message="Analysis started. Poll /api/repo/{id}/status for progress.",
    )


@router.get("/repos", response_model=RepoListResponse)
async def list_repos(session: AsyncSession = Depends(get_session)):
    """List all analyzed repositories."""
    result = await session.execute(
        select(Repo).order_by(Repo.last_analyzed.desc().nullslast())
    )
    repos = result.scalars().all()

    return RepoListResponse(
        repos=[RepoInfo.model_validate(r) for r in repos],
        total=len(repos),
    )


@router.get("/repo/{repo_id}/status")
async def get_repo_status(repo_id: int, session: AsyncSession = Depends(get_session)):
    """Get the current analysis status of a repository."""
    result = await session.execute(select(Repo).where(Repo.id == repo_id))
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(404, "Repository not found")

    return {
        "repo_id": repo.id,
        "url": repo.url,
        "status": repo.status,
        "error_message": repo.error_message,
        "name": repo.name,
        "primary_language": repo.primary_language,
        "framework": repo.framework,
    }


@router.delete("/repo/{repo_id}")
async def delete_repo(repo_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a repository and all its associated data."""
    result = await session.execute(select(Repo).where(Repo.id == repo_id))
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(404, "Repository not found")

    await session.delete(repo)
    await session.commit()
    
    return {"status": "success", "message": "Repository deleted"}


@router.get("/repo/{repo_id}/overview", response_model=OverviewResponse)
async def get_repo_overview(repo_id: int, session: AsyncSession = Depends(get_session)):
    """Get the architecture overview for a repository."""
    result = await session.execute(select(Repo).where(Repo.id == repo_id))
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(404, "Repository not found")

    if repo.status != "done":
        raise HTTPException(400, f"Analysis not complete. Current status: {repo.status}")

    # Get the latest overview
    overview_result = await session.execute(
        select(ArchitectureOverview)
        .where(ArchitectureOverview.repo_id == repo_id)
        .order_by(ArchitectureOverview.generated_at.desc())
        .limit(1)
    )
    overview = overview_result.scalar_one_or_none()

    entry_points = []
    core_modules = []
    cycles = []
    stats = None
    narrative = None
    generated_at = None

    if overview:
        narrative = overview.narrative
        generated_at = overview.generated_at
        cycles = overview.cycles or []
        stats = overview.stats

        for ep in (overview.entry_points or []):
            entry_points.append(EntryPointInfo(
                path=ep.get("path", ""),
                score=ep.get("score", 0),
                reasons=ep.get("reasons", []),
                in_degree=ep.get("in_degree", 0),
                out_degree=ep.get("out_degree", 0),
            ))

        for cm in (overview.core_modules or []):
            core_modules.append(CoreModuleInfo(
                path=cm.get("path", ""),
                score=cm.get("score", 0),
                in_degree=cm.get("in_degree", 0),
                out_degree=cm.get("out_degree", 0),
                betweenness=cm.get("betweenness", 0),
            ))

    return OverviewResponse(
        repo=RepoInfo.model_validate(repo),
        narrative=narrative,
        entry_points=entry_points,
        core_modules=core_modules,
        cycles=cycles,
        stats=stats,
        generated_at=generated_at,
    )


@router.get("/repo/{repo_id}/graph", response_model=GraphResponse)
async def get_repo_graph(repo_id: int, session: AsyncSession = Depends(get_session)):
    """Get the dependency graph for a repository."""
    result = await session.execute(select(Repo).where(Repo.id == repo_id))
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(404, "Repository not found")

    # Get files
    files_result = await session.execute(
        select(File).where(File.repo_id == repo_id)
    )
    files = files_result.scalars().all()
    file_map = {f.id: f for f in files}

    # Get dependencies
    deps_result = await session.execute(
        select(Dependency).where(Dependency.repo_id == repo_id)
    )
    deps = deps_result.scalars().all()

    nodes = [
        GraphNode(
            id=f.path,
            language=f.language or "",
            functions=f.functions or [],
            classes=f.classes or [],
            role=f.role or "",
            centrality_score=f.centrality_score or 0.0,
            in_degree=f.in_degree or 0,
            out_degree=f.out_degree or 0,
        )
        for f in files
    ]

    edges = []
    for d in deps:
        source = file_map.get(d.source_file_id)
        target = file_map.get(d.target_file_id)
        if source and target:
            edges.append(DependencyEdge(
                source=source.path,
                target=target.path,
                import_name=d.import_name,
            ))

    return GraphResponse(nodes=nodes, edges=edges)


@router.get("/repo/{repo_id}/files")
async def get_repo_files(
    repo_id: int,
    role: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """Get all files for a repository, optionally filtered by role."""
    query = select(File).where(File.repo_id == repo_id)

    if role:
        query = query.where(File.role == role)

    query = query.order_by(File.centrality_score.desc())

    result = await session.execute(query)
    files = result.scalars().all()

    return {
        "files": [FileInfo.model_validate(f) for f in files],
        "total": len(files),
    }


@router.get("/repo/{repo_id}/file/{file_id}/summary", response_model=FileSummaryResponse)
async def get_file_summary(
    repo_id: int,
    file_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get the grounded summary for a specific file."""
    result = await session.execute(
        select(File).where(File.id == file_id, File.repo_id == repo_id)
    )
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(404, "File not found")

    # Get dependents (files that import this file)
    dependents_result = await session.execute(
        select(File.path)
        .join(Dependency, Dependency.source_file_id == File.id)
        .where(Dependency.target_file_id == file_id)
    )
    dependents = [r[0] for r in dependents_result.all()]

    # Get dependencies (files this file imports)
    deps_result = await session.execute(
        select(File.path)
        .join(Dependency, Dependency.target_file_id == File.id)
        .where(Dependency.source_file_id == file_id)
    )
    dependencies = [r[0] for r in deps_result.all()]

    return FileSummaryResponse(
        file=FileInfo.model_validate(file),
        dependents=dependents,
        dependencies=dependencies,
    )