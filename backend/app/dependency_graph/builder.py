"""
dependency_graph — Build a NetworkX directed graph from parsed import statements.

Resolves import paths to actual files in the repo and creates edges.
This is the foundation for the insight_engine's deterministic analysis.
"""

import os
import logging
from pathlib import Path, PurePosixPath
from typing import Optional

import networkx as nx

from app.ast_parser.parser import ParsedFile

logger = logging.getLogger(__name__)


def _normalize_path(path: str) -> str:
    """Normalize file path separators to forward slashes."""
    return path.replace("\\", "/")


def _build_file_index(parsed_files: list[ParsedFile]) -> dict[str, str]:
    """
    Build an index mapping possible import references to actual file paths.
    For example:
        "src/utils/helper" -> "src/utils/helper.py"
        "src/utils/helper" -> "src/utils/helper.js"
        "utils.helper"     -> "src/utils/helper.py" (Python dotted imports)
    """
    index = {}

    for pf in parsed_files:
        norm_path = _normalize_path(pf.path)
        # Map the full path (without extension)
        base = norm_path.rsplit(".", 1)[0] if "." in norm_path.split("/")[-1] else norm_path
        index[norm_path] = norm_path
        index[base] = norm_path

        # Map without common prefixes (src/, lib/, app/)
        for prefix in ["src/", "lib/", "app/"]:
            if norm_path.startswith(prefix):
                trimmed = norm_path[len(prefix):]
                trimmed_base = trimmed.rsplit(".", 1)[0] if "." in trimmed.split("/")[-1] else trimmed
                index[trimmed] = norm_path
                index[trimmed_base] = norm_path

        # Python dotted path (e.g., "app.utils.helper" -> "app/utils/helper.py")
        if pf.language == "Python":
            dotted = base.replace("/", ".")
            index[dotted] = norm_path

        # Handle index files (index.js, __init__.py)
        filename = norm_path.split("/")[-1]
        if filename in ("index.js", "index.ts", "index.jsx", "index.tsx"):
            dir_path = "/".join(norm_path.split("/")[:-1])
            if dir_path:
                index[dir_path] = norm_path
        elif filename == "__init__.py":
            dir_path = "/".join(norm_path.split("/")[:-1])
            if dir_path:
                index[dir_path] = norm_path
                index[dir_path.replace("/", ".")] = norm_path

    return index


def _resolve_python_import(
    import_path: str,
    source_file: str,
    file_index: dict[str, str],
) -> Optional[str]:
    """Resolve a Python import to an actual file path."""
    import_path = import_path.strip()

    # Relative imports (starts with .)
    if import_path.startswith("."):
        dots = len(import_path) - len(import_path.lstrip("."))
        remainder = import_path[dots:]

        source_parts = _normalize_path(source_file).split("/")
        # Go up `dots` directories from the source file's directory
        base_parts = source_parts[:-1]  # Remove filename
        for _ in range(dots - 1):
            if base_parts:
                base_parts.pop()

        if remainder:
            candidate = "/".join(base_parts + remainder.split("."))
        else:
            candidate = "/".join(base_parts)

        # Try resolving
        for suffix in ["", ".py", "/__init__.py"]:
            check = candidate + suffix
            if check in file_index:
                return file_index[check]

        return file_index.get(candidate)

    # Absolute imports — try dotted path -> file path
    as_path = import_path.replace(".", "/")

    for suffix in ["", ".py", "/__init__.py"]:
        check = as_path + suffix
        if check in file_index:
            return file_index[check]

    # Try with common prefixes
    for prefix in ["", "src/", "app/", "lib/"]:
        for suffix in ["", ".py", "/__init__.py"]:
            check = prefix + as_path + suffix
            if check in file_index:
                return file_index[check]

    return file_index.get(import_path)


def _resolve_js_import(
    import_path: str,
    source_file: str,
    file_index: dict[str, str],
) -> Optional[str]:
    """Resolve a JavaScript/TypeScript import to an actual file path."""
    import_path = import_path.strip()

    # Skip external packages (no relative path prefix)
    if not import_path.startswith(".") and not import_path.startswith("/"):
        return None

    # Resolve relative path
    source_dir = "/".join(_normalize_path(source_file).split("/")[:-1])

    if import_path.startswith("./") or import_path.startswith("../"):
        parts = source_dir.split("/") if source_dir else []
        import_parts = import_path.split("/")

        for part in import_parts:
            if part == ".":
                continue
            elif part == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(part)

        resolved = "/".join(parts)
    else:
        resolved = import_path.lstrip("/")

    # Try resolving with various extensions
    extensions = [".js", ".jsx", ".ts", ".tsx", "/index.js", "/index.ts", "/index.jsx", "/index.tsx"]

    if resolved in file_index:
        return file_index[resolved]

    for ext in extensions:
        check = resolved + ext
        if check in file_index:
            return file_index[check]

    # Check without extension in index
    return file_index.get(resolved)


def build_graph(parsed_files: list[ParsedFile]) -> nx.DiGraph:
    """
    Build a NetworkX directed graph from parsed files and their imports.

    Nodes = files (keyed by relative path)
    Edges = import dependencies (source imports target)

    Returns a DiGraph with node attributes (language, functions, classes, etc.)
    """
    graph = nx.DiGraph()
    file_index = _build_file_index(parsed_files)

    # Add all files as nodes
    for pf in parsed_files:
        norm_path = _normalize_path(pf.path)
        graph.add_node(
            norm_path,
            language=pf.language,
            functions=pf.functions,
            classes=pf.classes,
            imports=pf.imports,
            exports=pf.exports,
        )

    # Add edges from imports
    edges_added = 0
    for pf in parsed_files:
        source = _normalize_path(pf.path)

        for import_path in pf.raw_import_paths:
            if pf.language == "Python":
                target = _resolve_python_import(import_path, source, file_index)
            else:
                target = _resolve_js_import(import_path, source, file_index)

            if target and target != source and target in graph:
                graph.add_edge(source, target, import_name=import_path)
                edges_added += 1

    logger.info(
        f"Built dependency graph: {graph.number_of_nodes()} nodes, "
        f"{graph.number_of_edges()} edges ({edges_added} resolved imports)"
    )

    return graph


def graph_to_json(graph: nx.DiGraph) -> dict:
    """
    Convert a NetworkX graph to a JSON-serializable dict for the API.
    Format: {nodes: [{id, ...attrs}], edges: [{source, target, ...attrs}]}
    """
    nodes = []
    for node_id, attrs in graph.nodes(data=True):
        nodes.append({
            "id": node_id,
            "language": attrs.get("language", ""),
            "functions": attrs.get("functions", []),
            "classes": attrs.get("classes", []),
            "role": attrs.get("role", ""),
            "centrality_score": attrs.get("centrality_score", 0.0),
            "in_degree": graph.in_degree(node_id),
            "out_degree": graph.out_degree(node_id),
        })

    edges = []
    for source, target, attrs in graph.edges(data=True):
        edges.append({
            "source": source,
            "target": target,
            "import_name": attrs.get("import_name", ""),
        })

    return {"nodes": nodes, "edges": edges}