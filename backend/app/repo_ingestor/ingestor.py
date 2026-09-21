"""
repo_ingestor — Clone a GitHub repo, detect primary language(s) and framework.

This is the first stage of the RepoLens pipeline. It:
1. Clones the repository to a local directory
2. Detects the primary programming language(s)
3. Detects framework conventions (Django, Flask, Express, Next.js, etc.)
4. Stores metadata in the repos table
"""

import os
import re
import json
import shutil
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from collections import Counter

from git import Repo as GitRepo
from git.exc import GitCommandError

from app.config import settings

logger = logging.getLogger(__name__)

# File extension -> language mapping
EXTENSION_LANG_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".h": "C",
    ".hpp": "C++",
    ".cs": "C#",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".r": "R",
    ".R": "R",
    ".lua": "Lua",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
}

# Directories to skip when scanning
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "venv", ".venv",
    "vendor", "dist", "build", ".next", ".nuxt", "target",
    "bin", "obj", ".tox", ".mypy_cache", ".pytest_cache",
    "coverage", ".coverage", "htmlcov", "egg-info",
}

# Files that should not count toward language detection
SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Pipfile.lock", "poetry.lock", "composer.lock",
}


def clone_repo(url: str) -> Path:
    """
    Clone a public GitHub repository to the local clone directory.
    Returns the path to the cloned repo.
    """
    # Extract repo name from URL
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]

    clone_path = Path(settings.clone_dir) / name

    # Remove existing clone if present
    if clone_path.exists():
        shutil.rmtree(clone_path, ignore_errors=True)

    logger.info(f"Cloning {url} to {clone_path}")

    try:
        GitRepo.clone_from(
            url,
            str(clone_path),
            depth=1,  # Shallow clone for speed
            single_branch=True,
        )
    except GitCommandError as e:
        logger.error(f"Failed to clone {url}: {e}")
        raise RuntimeError(f"Failed to clone repository: {e}")

    logger.info(f"Successfully cloned {url}")
    return clone_path


def _is_trivially_empty(fpath: Path) -> bool:
    """
    True if a file has no real code — only blank lines, comments, a bare
    docstring, or a lone `pass`/`...`. This is what lets a placeholder
    __init__.py get skipped without blacklisting __init__.py as a filename;
    one that actually re-exports symbols still has real code and is kept.
    """
    try:
        text = fpath.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False

    in_block_comment = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if in_block_comment:
            if line.endswith("*/"):
                in_block_comment = False
            continue
        if line.startswith("/*"):
            if not line.endswith("*/"):
                in_block_comment = True
            continue
        if line.startswith("#") or line.startswith("//"):
            continue
        if line in ("pass", "...", '"""', "'''"):
            continue
        if len(line) >= 6 and (
            (line.startswith('"""') and line.endswith('"""'))
            or (line.startswith("'''") and line.endswith("'''"))
        ):
            continue
        return False  # found a real line of code
    return True


def _walk_source_files(repo_path: Path) -> list[Path]:
    """Walk the repo and return all source code file paths."""
    source_files = []
    for root, dirs, files in os.walk(repo_path):
        # Prune skipped directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

        for f in files:
            if f in SKIP_FILES:
                continue
            fpath = Path(root) / f
            if fpath.suffix in EXTENSION_LANG_MAP and not _is_trivially_empty(fpath):
                source_files.append(fpath)

    return source_files


def detect_language(repo_path: Path) -> str:
    """
    Detect the primary language by counting source file extensions.
    Returns the most common language.
    """
    source_files = _walk_source_files(repo_path)
    lang_counter = Counter()

    for fpath in source_files:
        lang = EXTENSION_LANG_MAP.get(fpath.suffix)
        if lang:
            lang_counter[lang] += 1

    if not lang_counter:
        return "Unknown"

    primary = lang_counter.most_common(1)[0][0]
    logger.info(f"Detected primary language: {primary} (from {dict(lang_counter)})")
    return primary


def detect_framework(repo_path: Path, language: str) -> Optional[str]:
    """
    Detect framework conventions based on marker files.
    """
    markers = {
        # Python frameworks
        ("manage.py",): "Django",
        ("django",): "Django",
        ("flask",): "Flask",
        ("fastapi",): "FastAPI",
        ("streamlit",): "Streamlit",

        # JavaScript/TypeScript frameworks
        ("next.config.js", "next.config.mjs", "next.config.ts"): "Next.js",
        ("nuxt.config.js", "nuxt.config.ts"): "Nuxt.js",
        ("angular.json",): "Angular",
        ("svelte.config.js",): "Svelte",
        ("remix.config.js",): "Remix",
        ("gatsby-config.js",): "Gatsby",
        ("astro.config.mjs",): "Astro",

        # Other
        ("Cargo.toml",): "Rust/Cargo",
        ("go.mod",): "Go Modules",
        ("pom.xml",): "Maven",
        ("build.gradle", "build.gradle.kts"): "Gradle",
        ("Gemfile",): "Ruby/Bundler",
        ("composer.json",): "PHP/Composer",
        ("pubspec.yaml",): "Flutter/Dart",
        ("mix.exs",): "Elixir/Mix",
    }

    # Check for marker files in root
    root_files = set(f.name for f in repo_path.iterdir() if f.is_file())

    for marker_files, framework in markers.items():
        if any(m in root_files for m in marker_files):
            logger.info(f"Detected framework: {framework}")
            return framework

    # Check package.json for framework dependencies
    pkg_json = repo_path / "package.json"
    if pkg_json.exists():
        try:
            with open(pkg_json) as f:
                pkg = json.load(f)
            all_deps = {
                **pkg.get("dependencies", {}),
                **pkg.get("devDependencies", {}),
            }
            if "react" in all_deps:
                if "next" in all_deps:
                    return "Next.js"
                return "React"
            if "vue" in all_deps:
                return "Vue.js"
            if "@angular/core" in all_deps:
                return "Angular"
            if "svelte" in all_deps:
                return "Svelte"
            if "express" in all_deps:
                return "Express"
        except (json.JSONDecodeError, IOError):
            pass

    # Check requirements.txt / pyproject.toml for Python frameworks
    for req_file in ["requirements.txt", "requirements/base.txt"]:
        req_path = repo_path / req_file
        if req_path.exists():
            try:
                content = req_path.read_text().lower()
                if "django" in content:
                    return "Django"
                if "flask" in content:
                    return "Flask"
                if "fastapi" in content:
                    return "FastAPI"
            except IOError:
                pass

    pyproject = repo_path / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text().lower()
            if "django" in content:
                return "Django"
            if "flask" in content:
                return "Flask"
            if "fastapi" in content:
                return "FastAPI"
        except IOError:
            pass

    return None


def get_repo_name(url: str) -> str:
    """Extract repository name from URL."""
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def get_source_files(repo_path: Path) -> list[dict]:
    """
    Get all source files with their relative paths and detected languages.
    Returns a list of dicts with 'path' and 'language' keys.
    """
    source_files = _walk_source_files(repo_path)
    result = []

    for fpath in source_files:
        rel_path = str(fpath.relative_to(repo_path)).replace("\\", "/")
        lang = EXTENSION_LANG_MAP.get(fpath.suffix, "Unknown")
        result.append({
            "path": rel_path,
            "language": lang,
            "absolute_path": str(fpath),
        })

    return result


async def ingest_repo(url: str, session) -> dict:
    """
    Full ingestion pipeline:
    1. Clone the repo
    2. Detect language and framework
    3. Store in DB
    Returns repo metadata dict.
    """
    from app.models import Repo

    name = get_repo_name(url)

    # Clone — clone_repo() is synchronous (GitPython), so run it in a thread
    # instead of blocking the event loop (and every other in-flight request).
    repo_path = await asyncio.to_thread(clone_repo, url)

    # Detect
    language = detect_language(repo_path)
    framework = detect_framework(repo_path, language)

    # Get source file listing
    source_files = get_source_files(repo_path)

    logger.info(
        f"Ingested repo: {name} | Language: {language} | "
        f"Framework: {framework} | Files: {len(source_files)}"
    )

    return {
        "name": name,
        "url": url,
        "primary_language": language,
        "framework": framework,
        "clone_path": str(repo_path),
        "source_files": source_files,
    }