"""
Pipeline orchestrator — coordinates the full analysis pipeline.

repo_ingestor -> ast_parser -> dependency_graph -> insight_engine -> summary_generator

Each stage updates the repo status in the database for progress tracking.
"""

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models import Repo, File, Dependency, ArchitectureOverview
from app.repo_ingestor.ingestor import ingest_repo, get_source_files
from app.ast_parser.parser import parse_repo
from app.dependency_graph.builder import build_graph, graph_to_json
from app.insight_engine.analyzer import analyze
from app.summary_generator.generator import generate_all_summaries

logger = logging.getLogger(__name__)


async def _update_status(session: AsyncSession, repo_id: int, status: str, error: str = None):
    """Update repo status in the database."""
    stmt = (
        update(Repo)
        .where(Repo.id == repo_id)
        .values(status=status, error_message=error)
    )
    await session.execute(stmt)
    await session.commit()


async def run_pipeline(repo_url: str, session: AsyncSession, is_resume: bool = False) -> int:
    """
    Run the full analysis pipeline for a repository.

    Returns the repo_id.
    """
    # 1. Check if already analyzed
    result = await session.execute(select(Repo).where(Repo.url == repo_url))
    existing = result.scalar_one_or_none()

    existing_summaries = {}

    if existing:
        repo_id = existing.id
        
        if is_resume:
            # We want to keep existing summaries
            files_result = await session.execute(select(File).where(File.repo_id == repo_id))
            for f in files_result.scalars().all():
                if f.summary:
                    existing_summaries[f.path] = f.summary
            
            # Now update status back to cloning to re-run fast steps
            await session.execute(
                update(Repo).where(Repo.id == repo_id).values(
                    status="cloning", error_message=None
                )
            )
        else:
            # Explicit re-analyze, clean state
            await session.execute(
                update(Repo).where(Repo.id == repo_id).values(
                    status="cloning", error_message=None
                )
            )

        # Delete old files, deps, overviews (cascade should handle this)
        from sqlalchemy import delete
        await session.execute(delete(ArchitectureOverview).where(ArchitectureOverview.repo_id == repo_id))
        await session.execute(delete(Dependency).where(Dependency.repo_id == repo_id))
        await session.execute(delete(File).where(File.repo_id == repo_id))
        await session.commit()
    else:
        # Create new repo record
        repo = Repo(url=repo_url, status="cloning")
        session.add(repo)
        await session.commit()
        await session.refresh(repo)
        repo_id = repo.id

    try:
        # === Stage 1: Clone & Ingest ===
        logger.info(f"[Pipeline] Stage 1: Cloning {repo_url}")
        await _update_status(session, repo_id, "cloning")

        repo_data = await ingest_repo(repo_url, session)

        await session.execute(
            update(Repo).where(Repo.id == repo_id).values(
                name=repo_data["name"],
                primary_language=repo_data["primary_language"],
                framework=repo_data["framework"],
                status="parsing",
            )
        )
        await session.commit()

        # === Stage 2: AST Parsing ===
        logger.info(f"[Pipeline] Stage 2: Parsing {len(repo_data['source_files'])} files")
        await _update_status(session, repo_id, "parsing")

        parsed_files = parse_repo(repo_data["source_files"])

        # === Stage 3: Dependency Graph ===
        logger.info("[Pipeline] Stage 3: Building dependency graph")
        await _update_status(session, repo_id, "graphing")

        graph = build_graph(parsed_files)

        # === Stage 4: Insight Engine (deterministic) ===
        logger.info("[Pipeline] Stage 4: Running insight engine")
        await _update_status(session, repo_id, "analyzing")

        insights = analyze(graph)

        # Persist files to DB
        file_id_map = {}
        for node in graph.nodes():
            node_data = graph.nodes[node]
            file_record = File(
                repo_id=repo_id,
                path=node,
                language=node_data.get("language", ""),
                role=node_data.get("role", "utility"),
                centrality_score=node_data.get("centrality_score", 0.0),
                in_degree=node_data.get("in_degree", 0),
                out_degree=node_data.get("out_degree", 0),
                functions=node_data.get("functions", []),
                classes=node_data.get("classes", []),
                imports=node_data.get("imports", []),
                exports=node_data.get("exports", []),
            )
            session.add(file_record)
            await session.flush()
            file_id_map[node] = file_record.id

        # Persist dependency edges
        for source, target, edge_data in graph.edges(data=True):
            if source in file_id_map and target in file_id_map:
                dep = Dependency(
                    repo_id=repo_id,
                    source_file_id=file_id_map[source],
                    target_file_id=file_id_map[target],
                    import_name=edge_data.get("import_name", ""),
                )
                session.add(dep)

        await session.commit()

        # === Stage 5: Summary Generation (LLM) ===
        logger.info("[Pipeline] Stage 5: Generating summaries")
        await _update_status(session, repo_id, "summarizing")

        file_summaries, narrative = await generate_all_summaries(
            repo_name=repo_data["name"],
            language=repo_data["primary_language"],
            framework=repo_data["framework"],
            graph=graph,
            insights=insights,
            clone_path=repo_data["clone_path"],
            existing_summaries=existing_summaries,
            session=session,
            file_id_map=file_id_map
        )

        # Update file summaries in DB
        for file_path, summary in file_summaries.items():
            if file_path in file_id_map:
                await session.execute(
                    update(File)
                    .where(File.id == file_id_map[file_path])
                    .values(summary=summary)
                )

        # Store architecture overview
        overview = ArchitectureOverview(
            repo_id=repo_id,
            narrative=narrative,
            entry_points=[
                {"file_id": file_id_map.get(ep["path"]), "path": ep["path"], "score": ep["score"]}
                for ep in insights.get("entry_points", [])
                if ep["path"] in file_id_map
            ],
            core_modules=[
                {"file_id": file_id_map.get(cm["path"]), "path": cm["path"], "score": cm["score"]}
                for cm in insights.get("core_modules", [])
                if cm["path"] in file_id_map
            ],
            cycles=insights.get("cycles", []),
            stats=insights.get("stats", {}),
            generated_at=datetime.utcnow(),
        )
        session.add(overview)

        # Mark as done
        await session.execute(
            update(Repo).where(Repo.id == repo_id).values(
                status="done",
                last_analyzed=datetime.utcnow(),
            )
        )
        await session.commit()

        logger.info(f"[Pipeline] Complete for repo {repo_id}")
        return repo_id

    except Exception as e:
        logger.error(f"[Pipeline] Failed for {repo_url}: {e}", exc_info=True)
        await _update_status(session, repo_id, "error", str(e))
        raise