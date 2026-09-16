"""
insight_engine — Fully deterministic structural analysis of the dependency graph.

NO LLM calls here. This module computes:
1. Centrality scores (betweenness, in-degree, out-degree)
2. Entry point candidates (high out-degree, low in-degree)
3. Core module ranking (highest betweenness centrality)
4. Cyclic dependency detection
5. File role classification (entry_point, core_module, utility, test, config, leaf)

All results are grounded in graph topology — the foundation for the
summary_generator's LLM prompts.
"""

import re
import logging
from pathlib import PurePosixPath
from typing import Optional

import networkx as nx

logger = logging.getLogger(__name__)


# Patterns for heuristic role detection
ENTRY_POINT_PATTERNS = [
    r"(^|/)main\.(py|js|ts|jsx|tsx)$",
    r"(^|/)index\.(py|js|ts|jsx|tsx)$",
    r"(^|/)app\.(py|js|ts|jsx|tsx)$",
    r"(^|/)server\.(py|js|ts|jsx|tsx)$",
    r"(^|/)manage\.py$",
    r"(^|/)wsgi\.py$",
    r"(^|/)asgi\.py$",
    r"(^|/)cli\.(py|js|ts)$",
    r"(^|/)__main__\.py$",
]

TEST_PATTERNS = [
    r"(^|/)test[s]?/",
    r"(^|/)test_",
    r"(^|/)_test\.",
    r"\.test\.(js|ts|jsx|tsx)$",
    r"\.spec\.(js|ts|jsx|tsx)$",
    r"(^|/)conftest\.py$",
]

CONFIG_PATTERNS = [
    r"(^|/)config\.(py|js|ts)$",
    r"(^|/)settings\.(py|js|ts)$",
    r"(^|/)constants?\.(py|js|ts)$",
    r"(^|/)\.env",
    r"(^|/)setup\.(py|cfg)$",
    r"(^|/)vite\.config",
    r"(^|/)webpack\.config",
    r"(^|/)tsconfig",
    r"(^|/)tailwind\.config",
    r"(^|/)postcss\.config",
    r"(^|/)next\.config",
]


def _matches_any(path: str, patterns: list[str]) -> bool:
    """Check if a file path matches any of the given regex patterns."""
    return any(re.search(p, path) for p in patterns)


def compute_centrality(graph: nx.DiGraph) -> dict[str, dict]:
    """
    Compute centrality metrics for all nodes in the graph.

    Returns dict mapping node_id -> {
        betweenness: float,
        in_degree: int,
        out_degree: int,
        pagerank: float,
        combined_score: float  (weighted composite)
    }
    """
    if graph.number_of_nodes() == 0:
        return {}

    # Betweenness centrality — measures how often a node lies on shortest paths
    betweenness = nx.betweenness_centrality(graph)

    # PageRank — importance based on incoming link quality
    try:
        pagerank = nx.pagerank(graph, alpha=0.85)
    except nx.PowerIterationFailedConvergence:
        pagerank = {n: 1.0 / graph.number_of_nodes() for n in graph.nodes()}

    centrality = {}
    for node in graph.nodes():
        in_deg = graph.in_degree(node)
        out_deg = graph.out_degree(node)
        btwn = betweenness.get(node, 0.0)
        pr = pagerank.get(node, 0.0)

        # Combined score: weighted sum (betweenness is strongest signal)
        combined = (btwn * 0.4) + (pr * 0.3) + (in_deg * 0.02) + (out_deg * 0.01)

        centrality[node] = {
            "betweenness": round(btwn, 6),
            "in_degree": in_deg,
            "out_degree": out_deg,
            "pagerank": round(pr, 6),
            "combined_score": round(combined, 6),
        }

    return centrality


def detect_entry_points(graph: nx.DiGraph, centrality: dict) -> list[dict]:
    """
    Identify entry point candidates.

    Entry points typically have:
    - High out-degree (they import many things)
    - Low in-degree (few things import them)
    - Match entry point filename patterns
    """
    candidates = []

    for node in graph.nodes():
        score = 0.0
        reasons = []

        metrics = centrality.get(node, {})
        in_deg = metrics.get("in_degree", 0)
        out_deg = metrics.get("out_degree", 0)

        # Filename pattern match is a strong signal
        if _matches_any(node, ENTRY_POINT_PATTERNS):
            score += 10.0
            reasons.append("filename_match")

        # High out-degree (imports many modules) + low in-degree (not imported by others)
        if out_deg > 0 and in_deg == 0:
            score += 5.0
            reasons.append("root_node")
        elif out_deg > in_deg and in_deg <= 2:
            score += 3.0
            reasons.append("high_fan_out")

        if score > 0:
            candidates.append({
                "path": node,
                "score": round(score, 2),
                "reasons": reasons,
                **metrics,
            })

    # Sort by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:10]  # Top 10


def rank_core_modules(graph: nx.DiGraph, centrality: dict) -> list[dict]:
    """
    Rank modules by their structural importance (core modules).

    Core modules have:
    - High betweenness centrality (they connect many parts of the codebase)
    - High in-degree (many files import them)
    - High PageRank
    """
    modules = []

    for node in graph.nodes():
        # Skip tests and config
        if _matches_any(node, TEST_PATTERNS) or _matches_any(node, CONFIG_PATTERNS):
            continue

        metrics = centrality.get(node, {})
        in_deg = metrics.get("in_degree", 0)
        btwn = metrics.get("betweenness", 0.0)
        pr = metrics.get("pagerank", 0.0)

        # Core module score: heavily weighted toward in-degree and betweenness
        score = (in_deg * 2.0) + (btwn * 50.0) + (pr * 10.0)

        if score > 0:
            modules.append({
                "path": node,
                "score": round(score, 2),
                **metrics,
            })

    modules.sort(key=lambda x: x["score"], reverse=True)
    return modules[:15]  # Top 15


def detect_cycles(graph: nx.DiGraph) -> list[list[str]]:
    """
    Detect cyclic dependencies in the graph.
    Returns a list of cycles, where each cycle is a list of file paths.
    """
    try:
        cycles = list(nx.simple_cycles(graph))
        # Limit to top 20 cycles, sorted by length
        cycles.sort(key=len)
        return cycles[:20]
    except Exception as e:
        logger.warning(f"Cycle detection failed: {e}")
        return []


def classify_files(
    graph: nx.DiGraph,
    centrality: dict,
    entry_points: list[dict],
    core_modules: list[dict],
) -> dict[str, str]:
    """
    Assign a role to each file based on structural analysis.

    Roles: entry_point, core_module, utility, test, config, leaf
    """
    entry_point_paths = {ep["path"] for ep in entry_points[:5]}
    core_module_paths = {cm["path"] for cm in core_modules[:10]}

    roles = {}
    for node in graph.nodes():
        if _matches_any(node, TEST_PATTERNS):
            roles[node] = "test"
        elif _matches_any(node, CONFIG_PATTERNS):
            roles[node] = "config"
        elif node in entry_point_paths:
            roles[node] = "entry_point"
        elif node in core_module_paths:
            roles[node] = "core_module"
        elif graph.in_degree(node) == 0 and graph.out_degree(node) == 0:
            roles[node] = "leaf"
        elif graph.in_degree(node) == 0:
            roles[node] = "utility"
        else:
            metrics = centrality.get(node, {})
            if metrics.get("in_degree", 0) >= 3:
                roles[node] = "core_module"
            elif metrics.get("out_degree", 0) == 0:
                roles[node] = "leaf"
            else:
                roles[node] = "utility"

    return roles


def analyze(graph: nx.DiGraph) -> dict:
    """
    Run the full deterministic analysis pipeline on a dependency graph.

    Returns a dict with all insights:
    {
        centrality: {node -> metrics},
        entry_points: [{path, score, ...}],
        core_modules: [{path, score, ...}],
        cycles: [[path, ...], ...],
        roles: {node -> role},
        stats: {total_files, total_deps, ...}
    }
    """
    logger.info(f"Analyzing graph with {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

    centrality = compute_centrality(graph)
    entry_points = detect_entry_points(graph, centrality)
    core_modules = rank_core_modules(graph, centrality)
    cycles = detect_cycles(graph)
    roles = classify_files(graph, centrality, entry_points, core_modules)

    # Update graph nodes with computed attributes
    for node in graph.nodes():
        metrics = centrality.get(node, {})
        graph.nodes[node]["centrality_score"] = metrics.get("combined_score", 0.0)
        graph.nodes[node]["role"] = roles.get(node, "utility")
        graph.nodes[node]["in_degree"] = metrics.get("in_degree", 0)
        graph.nodes[node]["out_degree"] = metrics.get("out_degree", 0)

    # Compute stats
    languages = set()
    for node in graph.nodes():
        lang = graph.nodes[node].get("language", "")
        if lang:
            languages.add(lang)

    stats = {
        "total_files": graph.number_of_nodes(),
        "total_dependencies": graph.number_of_edges(),
        "languages": list(languages),
        "entry_points_count": len(entry_points),
        "core_modules_count": len(core_modules),
        "cycles_count": len(cycles),
        "role_distribution": {},
    }

    for role in roles.values():
        stats["role_distribution"][role] = stats["role_distribution"].get(role, 0) + 1

    logger.info(
        f"Analysis complete: {len(entry_points)} entry points, "
        f"{len(core_modules)} core modules, {len(cycles)} cycles"
    )

    return {
        "centrality": centrality,
        "entry_points": entry_points,
        "core_modules": core_modules,
        "cycles": cycles,
        "roles": roles,
        "stats": stats,
    }