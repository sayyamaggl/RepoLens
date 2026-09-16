"""Pydantic request/response schemas for the RepoLens API."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# === Request Schemas ===

class AnalyzeRequest(BaseModel):
    repo_url: str = Field(..., description="Public GitHub repository URL")


# === Response Schemas ===

class RepoInfo(BaseModel):
    id: int
    url: str
    name: Optional[str] = None
    primary_language: Optional[str] = None
    framework: Optional[str] = None
    status: str = "pending"
    error_message: Optional[str] = None
    last_analyzed: Optional[datetime] = None

    class Config:
        from_attributes = True


class FileInfo(BaseModel):
    id: int
    path: str
    language: Optional[str] = None
    role: Optional[str] = None
    centrality_score: float = 0.0
    in_degree: int = 0
    out_degree: int = 0
    functions: list[str] = []
    classes: list[str] = []
    summary: Optional[str] = None

    class Config:
        from_attributes = True


class DependencyEdge(BaseModel):
    source: str
    target: str
    import_name: Optional[str] = None


class GraphNode(BaseModel):
    id: str
    language: str = ""
    functions: list[str] = []
    classes: list[str] = []
    role: str = ""
    centrality_score: float = 0.0
    in_degree: int = 0
    out_degree: int = 0


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[DependencyEdge]


class EntryPointInfo(BaseModel):
    path: str
    score: float
    reasons: list[str] = []
    in_degree: int = 0
    out_degree: int = 0


class CoreModuleInfo(BaseModel):
    path: str
    score: float
    in_degree: int = 0
    out_degree: int = 0
    betweenness: float = 0.0


class OverviewResponse(BaseModel):
    repo: RepoInfo
    narrative: Optional[str] = None
    entry_points: list[EntryPointInfo] = []
    core_modules: list[CoreModuleInfo] = []
    cycles: list[list[str]] = []
    stats: Optional[dict] = None
    generated_at: Optional[datetime] = None


class FileSummaryResponse(BaseModel):
    file: FileInfo
    dependents: list[str] = []
    dependencies: list[str] = []


class AnalyzeResponse(BaseModel):
    repo_id: int
    status: str
    message: str


class RepoListResponse(BaseModel):
    repos: list[RepoInfo]
    total: int