"""SQLAlchemy ORM models for RepoLens."""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, Text, ForeignKey,
    DateTime, ARRAY, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Repo(Base):
    __tablename__ = "repos"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(Text, unique=True, nullable=False)
    name = Column(Text)
    primary_language = Column(Text)
    framework = Column(Text)
    status = Column(Text, default="pending")
    error_message = Column(Text)
    last_analyzed = Column(DateTime)

    # Relationships
    files = relationship("File", back_populates="repo", cascade="all, delete-orphan")
    dependencies = relationship("Dependency", back_populates="repo", cascade="all, delete-orphan")
    overviews = relationship("ArchitectureOverview", back_populates="repo", cascade="all, delete-orphan")


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    path = Column(Text, nullable=False)
    language = Column(Text)
    role = Column(Text)
    centrality_score = Column(Float, default=0.0)
    in_degree = Column(Integer, default=0)
    out_degree = Column(Integer, default=0)
    functions = Column(ARRAY(Text))
    classes = Column(ARRAY(Text))
    imports = Column(ARRAY(Text))
    exports = Column(ARRAY(Text))
    summary = Column(Text)

    __table_args__ = (
        UniqueConstraint("repo_id", "path", name="uq_file_repo_path"),
        Index("idx_files_repo_id", "repo_id"),
        Index("idx_files_role", "role"),
    )

    # Relationships
    repo = relationship("Repo", back_populates="files")
    outgoing_deps = relationship(
        "Dependency", foreign_keys="Dependency.source_file_id",
        back_populates="source_file", cascade="all, delete-orphan"
    )
    incoming_deps = relationship(
        "Dependency", foreign_keys="Dependency.target_file_id",
        back_populates="target_file", cascade="all, delete-orphan"
    )


class Dependency(Base):
    __tablename__ = "dependencies"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    source_file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    target_file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    import_name = Column(Text)

    __table_args__ = (
        UniqueConstraint("repo_id", "source_file_id", "target_file_id", name="uq_dep_edge"),
        Index("idx_deps_repo_id", "repo_id"),
        Index("idx_deps_source", "source_file_id"),
        Index("idx_deps_target", "target_file_id"),
    )

    # Relationships
    repo = relationship("Repo", back_populates="dependencies")
    source_file = relationship("File", foreign_keys=[source_file_id], back_populates="outgoing_deps")
    target_file = relationship("File", foreign_keys=[target_file_id], back_populates="incoming_deps")


class ArchitectureOverview(Base):
    __tablename__ = "architecture_overviews"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    narrative = Column(Text)
    entry_points = Column(JSONB)
    core_modules = Column(JSONB)
    cycles = Column(JSONB)
    stats = Column(JSONB)
    generated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_arch_repo_id", "repo_id"),
    )

    # Relationships
    repo = relationship("Repo", back_populates="overviews")