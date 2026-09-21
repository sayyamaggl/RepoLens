"""
summary_generator — LLM-powered grounded summary generation.

This module constructs prompts from VERIFIED structural facts (from insight_engine)
and code snippets, then calls the LLM to produce:
1. Per-file/module summaries
2. One overall architecture narrative per repo

CRITICAL: The LLM never sees raw unstructured code dumps. Every prompt is
grounded in deterministic facts: the file's role, its dependencies,
its function/class signatures, and relevant code snippets.
"""

import logging
import asyncio
from typing import Optional
import requests

import networkx as nx

from app.config import settings

logger = logging.getLogger(__name__)


async def _call_openrouter(prompt: str, system_prompt: str, max_tokens: int = 1500) -> str:
    """Call OpenRouter API."""
    from openai import AsyncOpenAI
    
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )
    
    try:
        response = await client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
        )
        choice = response.choices[0]
        content = choice.message.content
        if not content or not content.strip():
            raise ValueError("OpenRouter returned an empty response (no exception raised)")
        if getattr(choice, "finish_reason", None) == "length":
            logger.warning(f"OpenRouter response was truncated at max_tokens={max_tokens}")
        return content
    except Exception as e:
        logger.error(f"OpenRouter API error: {e}")
        raise


async def _call_anthropic(prompt: str, system_prompt: str, max_tokens: int = 1500) -> str:
    """Call Anthropic Claude API."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text if response.content else None
        if not content or not content.strip():
            raise ValueError("Anthropic returned an empty response (no exception raised)")
        if getattr(response, "stop_reason", None) == "max_tokens":
            logger.warning(f"Anthropic response was truncated at max_tokens={max_tokens}")
        return content
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        raise


async def _call_google(prompt: str, system_prompt: str, max_tokens: int = 1500) -> str:
    """Call Google Gemini API."""
    import google.generativeai as genai

    genai.configure(api_key=settings.google_api_key)
    model = genai.GenerativeModel(
        "gemini-3.6-flash",
        system_instruction=system_prompt,
    )

    try:
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens),
        )
        content = response.text
        if not content or not content.strip():
            raise ValueError("Google returned an empty response (no exception raised)")
        candidates = getattr(response, "candidates", None)
        if candidates and getattr(candidates[0], "finish_reason", None) == 2:  # 2 == MAX_TOKENS
            logger.warning(f"Google response was truncated at max_output_tokens={max_tokens}")
        return content
    except Exception as e:
        logger.error(f"Google API error: {e}")
        raise


async def _ensure_ollama_model(model_name: str, base_url: str = None):
    """Check if Ollama model exists, and pull it if not."""
    if not base_url:
        base_url = settings.ollama_base_url
    tags_url = f"{base_url}/api/tags"
    try:
        response = await asyncio.to_thread(requests.get, tags_url)
        if response.status_code == 200:
            models = response.json().get("models", [])
            if any(m.get("name") == model_name or m.get("name") == f"{model_name}:latest" for m in models):
                return  # Model exists
                
        logger.info(f"Ollama model {model_name} not found locally. Pulling it now (this may take a while)...")
        pull_url = f"{base_url}/api/pull"
        pull_response = await asyncio.to_thread(
            requests.post, 
            pull_url, 
            json={"name": model_name, "stream": False},
            timeout=600  # Pulling can take several minutes depending on network speed
        )
        pull_response.raise_for_status()
        logger.info(f"Successfully pulled {model_name}")
    except Exception as e:
        logger.error(f"Failed to check or pull Ollama model {model_name}: {e}")

async def _call_llm(prompt: str, system_prompt: str, max_tokens: int = 1500) -> str:
    """Route to the configured LLM provider, with fallback to others, and finally local Ollama."""
    
    # Try OpenRouter if configured
    if settings.openrouter_api_key:
        try:
            return await _call_openrouter(prompt, system_prompt, max_tokens=max_tokens)
        except Exception as e:
            logger.warning(f"OpenRouter failed: {e}. Trying next provider...")

    # Try Google if configured
    if settings.google_api_key:
        try:
            return await _call_google(prompt, system_prompt, max_tokens=max_tokens)
        except Exception as e:
            logger.warning(f"Google API failed: {e}. Trying next provider...")

    # Try Anthropic if configured
    if settings.anthropic_api_key:
        try:
            return await _call_anthropic(prompt, system_prompt, max_tokens=max_tokens)
        except Exception as e:
            logger.warning(f"Anthropic API failed: {e}. Trying next provider...")

    logger.warning("All configured cloud APIs failed or none configured. Falling back to local Ollama...")
    
    # Local Fallback using Ollama
    base_url = settings.ollama_base_url
    model_name = "qwen2.5-coder"
    
    await _ensure_ollama_model(model_name, base_url)
    
    url = f"{base_url}/api/generate"
    payload = {
        "model": model_name,
        "prompt": f"{system_prompt}\n\n{prompt}",
        "stream": False,
        "options": {"num_predict": max_tokens},
    }
    
    try:
        response = await asyncio.to_thread(requests.post, url, json=payload)
        response.raise_for_status()
        result = response.json().get('response')
        if not result or not result.strip():
            raise ValueError("Ollama returned an empty response")
        return result
    except Exception as local_error:
        logger.error(f"Local LLM fallback failed: {local_error}")
        return f"System Failure: Both Cloud and Local APIs are down. Error: {local_error}"

def _read_file_snippet(file_path: str, max_lines: int = 80) -> str:
    """Read the first N lines of a file for context."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append(f"... ({i} more lines)")
                    break
                lines.append(line.rstrip())
            return "\n".join(lines)
    except (IOError, OSError):
        return "(file not readable)"


def build_file_prompt(
    file_path: str,
    role: str,
    centrality_score: float,
    functions: list[str],
    classes: list[str],
    imports: list[str],
    dependents: list[str],
    dependencies: list[str],
    code_snippet: str,
) -> str:
    """
    Build a grounded prompt for per-file summary generation.
    Only includes verified structural facts.
    """
    prompt = f"""Analyze the following source file and write a concise, accurate summary.

FILE: {file_path}
ROLE: {role} (determined by structural analysis)
CENTRALITY SCORE: {centrality_score:.4f}

STRUCTURAL FACTS (verified by AST and graph analysis):
- Functions defined: {', '.join(functions) if functions else 'none'}
- Classes defined: {', '.join(classes) if classes else 'none'}
- Imports: {', '.join(imports[:20]) if imports else 'none'}
- Files that depend on this file: {', '.join(dependents[:10]) if dependents else 'none'}
- Files this file depends on: {', '.join(dependencies[:10]) if dependencies else 'none'}

CODE (first 80 lines):
```
{code_snippet}
```

INSTRUCTIONS:
1. Write a 2-4 sentence summary explaining what this file does
2. Mention its role in the broader codebase based on the structural facts
3. Reference ONLY functions, classes, and files that appear in the facts above
4. Do NOT guess or hallucinate connections that aren't in the structural facts
5. Be concise and technical"""

    return prompt


def build_architecture_prompt(
    repo_name: str,
    language: str,
    framework: Optional[str],
    entry_points: list[dict],
    core_modules: list[dict],
    cycles: list[list[str]],
    stats: dict,
    file_summaries: dict[str, str],
) -> str:
    """
    Build a grounded prompt for the overall architecture narrative.
    """
    ep_text = "\n".join(
        f"  - {ep['path']} (score: {ep['score']}, reasons: {', '.join(ep.get('reasons', []))})"
        for ep in entry_points[:5]
    ) or "  (none detected)"

    cm_text = "\n".join(
        f"  - {cm['path']} (score: {cm['score']}, in-degree: {cm.get('in_degree', 0)})"
        for cm in core_modules[:10]
    ) or "  (none detected)"

    cycle_text = "\n".join(
        f"  - {' -> '.join(c)} -> {c[0]}"
        for c in cycles[:5]
    ) or "  (no cycles detected)"

    summaries_text = "\n\n".join(
        f"### {path}\n{summary}"
        for path, summary in list(file_summaries.items())[:20]
    ) or "(no file summaries available)"

    prompt = f"""Write a comprehensive architecture overview for this repository.

REPOSITORY: {repo_name}
PRIMARY LANGUAGE: {language}
FRAMEWORK: {framework or 'none detected'}

STATISTICS:
- Total source files: {stats.get('total_files', 0)}
- Total dependencies: {stats.get('total_dependencies', 0)}
- Languages: {', '.join(stats.get('languages', []))}
- Role distribution: {stats.get('role_distribution', dict())}

ENTRY POINTS (determined by graph analysis):
{ep_text}

CORE MODULES (ranked by structural importance):
{cm_text}

CYCLIC DEPENDENCIES:
{cycle_text}

FILE SUMMARIES:
{summaries_text}

INSTRUCTIONS:
1. Start with ONE short standalone sentence stating what this project is as a whole (e.g. "This is a full-stack tool that does X"), before any frontend/backend breakdown
2. Then write a 3-5 paragraph architecture overview in plain English
3. Explain the overall structure and how the main components connect
4. Highlight the entry points and what they do
5. Mention the core modules and why they're central
6. Note any concerning patterns (cycles, isolated files)
7. Reference ONLY files and relationships that appear in the facts above
8. Be technical but accessible — this is for a developer trying to understand the codebase
9. Do NOT guess about functionality that isn't supported by the structural evidence"""

    return prompt


import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Result of grounding-checking an LLM-generated summary against known code facts."""
    is_grounded: bool
    checked_references: int
    unverified_references: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.is_grounded

    @property
    def grounding_score(self) -> float:
        """Fraction of checkable references that were actually verified. 1.0 if none to check."""
        if self.checked_references == 0:
            return 1.0
        verified = self.checked_references - len(self.unverified_references)
        return verified / self.checked_references


# Tokens the model itself marked as an identifier/path by formatting: `like_this`
_BACKTICK_REF_RE = re.compile(r"`([^`]+)`")
# Bare call-style mentions: someFunction(
_CALL_REF_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
# Tokens shaped like a repo-relative file path
_PATH_REF_RE = re.compile(r"[\w./-]+\.(?:py|js|jsx|ts|tsx|json|yml|yaml|toml|sql)\b")


def validate_summary(
    summary: str,
    known_files: set[str],
    known_functions: set[str],
    known_classes: set[str],
) -> ValidationResult:
    """
    Check that identifiers/paths the LLM explicitly called out in a summary
    actually exist in this codebase's structural facts.

    This is deliberately precision-first, not full NER over the prose: only
    tokens the model marked as identifiers/paths (backtick-quoted, call-style,
    or path-shaped) are checked. Checking every capitalized word in free text
    would misfire constantly ("the Router class", "the API layer") on ordinary
    English, not hallucination. A flagged token is a strong hallucination
    signal; an unflagged summary isn't proof every sentence is grounded, but
    it catches the concrete, checkable claims — which is what actually matters
    for "did the model invent a file/function/class that doesn't exist."
    """
    known_function_names = {f.rsplit(".", 1)[-1] for f in known_functions} | known_functions
    known_class_names = {c.rsplit(".", 1)[-1] for c in known_classes} | known_classes
    known_file_names = {f.rsplit("/", 1)[-1] for f in known_files} | known_files

    candidates: set[str] = set()
    candidates.update(_BACKTICK_REF_RE.findall(summary))
    candidates.update(_CALL_REF_RE.findall(summary))
    candidates.update(_PATH_REF_RE.findall(summary))

    unverified = []
    checked = 0
    for raw in candidates:
        token = raw.strip().rstrip("()").strip()
        if len(token) < 3:
            continue  # too short to be a meaningful check (avoids noise like "x", "i")
        checked += 1
        if (
            token in known_file_names
            or token in known_function_names
            or token in known_class_names
        ):
            continue
        unverified.append(token)

    return ValidationResult(
        is_grounded=len(unverified) == 0,
        checked_references=checked,
        unverified_references=sorted(unverified),
    )


async def generate_file_summary(
    file_path: str,
    absolute_path: str,
    role: str,
    centrality_score: float,
    functions: list[str],
    classes: list[str],
    imports: list[str],
    graph: nx.DiGraph,
) -> str:
    """Generate a grounded summary for a single file."""
    # Get dependents and dependencies from graph
    dependents = [pred for pred in graph.predecessors(file_path)] if file_path in graph else []
    dependencies = [succ for succ in graph.successors(file_path)] if file_path in graph else []

    # Read code snippet
    code_snippet = _read_file_snippet(absolute_path)

    prompt = build_file_prompt(
        file_path=file_path,
        role=role,
        centrality_score=centrality_score,
        functions=functions,
        classes=classes,
        imports=imports,
        dependents=dependents,
        dependencies=dependencies,
        code_snippet=code_snippet,
    )

    system_prompt = (
        "You are a senior software engineer analyzing a codebase. "
        "Your summaries must be grounded in the structural facts provided. "
        "Never invent or hallucinate connections between files."
    )

    try:
        summary = await _call_llm(prompt, system_prompt)
        return (summary or "").strip() or "Summary generation failed: LLM returned an empty response"
    except Exception as e:
        logger.error(f"Failed to generate summary for {file_path}: {e}")
        return f"Summary generation failed: {e}"


async def generate_architecture_narrative(
    repo_name: str,
    language: str,
    framework: Optional[str],
    insights: dict,
    file_summaries: dict[str, str],
) -> str:
    """Generate the overall architecture narrative."""
    prompt = build_architecture_prompt(
        repo_name=repo_name,
        language=language,
        framework=framework,
        entry_points=insights.get("entry_points", []),
        core_modules=insights.get("core_modules", []),
        cycles=insights.get("cycles", []),
        stats=insights.get("stats", {}),
        file_summaries=file_summaries,
    )

    system_prompt = (
        "You are a senior software architect writing a technical overview. "
        "Your narrative must be grounded in the verified structural facts. "
        "Write in clear, accessible English suitable for a developer new to this codebase."
    )

    try:
        narrative = await _call_llm(prompt, system_prompt, max_tokens=3000)
        return (narrative or "").strip() or "Architecture narrative generation failed: LLM returned an empty response"
    except Exception as e:
        logger.error(f"Failed to generate architecture narrative: {e}")
        return f"Architecture narrative generation failed: {e}"


async def generate_all_summaries(
    repo_name: str,
    language: str,
    framework: Optional[str],
    graph: nx.DiGraph,
    insights: dict,
    clone_path: str,
    existing_summaries: dict = None,
    session = None,
    file_id_map: dict = None,
    max_concurrent: int = 3,
) -> tuple[dict[str, str], str]:
    """
    Generate summaries for all significant files and the overall architecture.

    Returns (file_summaries, architecture_narrative)
    """
    roles = insights.get("roles", {})
    centrality = insights.get("centrality", {})

    # Build the "known facts" sets once, up front — used to ground-check every
    # summary against what actually exists in this repo (see validate_summary).
    known_files: set[str] = set(graph.nodes())
    known_functions: set[str] = set()
    known_classes: set[str] = set()
    for _, node_data in graph.nodes(data=True):
        known_functions.update(node_data.get("functions", []))
        known_classes.update(node_data.get("classes", []))

    # Sort files by importance (core modules and entry points first)
    role_priority = {"entry_point": 0, "core_module": 1, "utility": 2, "leaf": 3, "config": 4, "test": 5}
    sorted_nodes = sorted(
        graph.nodes(),
        key=lambda n: (
            role_priority.get(roles.get(n, "utility"), 3),
            -centrality.get(n, {}).get("combined_score", 0),
        ),
    )

    # Limit to top 50 most important files for LLM processing
    significant_files = sorted_nodes[:50]

    file_summaries = {}
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _summarize(node):
        async with semaphore:
            if existing_summaries and node in existing_summaries and existing_summaries[node]:
                file_summaries[node] = existing_summaries[node]
                logger.info(f"Skipped summary generation for {node} (already exists)")
                return

            node_data = graph.nodes[node]
            metrics = centrality.get(node, {})

            absolute_path = f"{clone_path}/{node}"

            summary = await generate_file_summary(
                file_path=node,
                absolute_path=absolute_path,
                role=roles.get(node, "utility"),
                centrality_score=metrics.get("combined_score", 0.0),
                functions=node_data.get("functions", []),
                classes=node_data.get("classes", []),
                imports=node_data.get("imports", []),
                graph=graph,
            )

            validation = validate_summary(summary, known_files, known_functions, known_classes)
            if not validation.is_grounded:
                logger.warning(
                    f"Summary for {node} references names not found in the codebase "
                    f"(grounding score {validation.grounding_score:.2f}): "
                    f"{validation.unverified_references}"
                )

            file_summaries[node] = summary
            logger.info(f"Generated summary for {node}")
            
            # Incremental save
            if session and file_id_map and node in file_id_map:
                from sqlalchemy import update
                from app.models import File
                try:
                    await session.execute(
                        update(File)
                        .where(File.id == file_id_map[node])
                        .values(summary=summary)
                    )
                    await session.commit()
                except Exception as e:
                    logger.error(f"Failed to incrementally save summary for {node}: {e}")

    # Generate file summaries concurrently (with rate limiting)
    tasks = [_summarize(node) for node in significant_files]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Generate architecture narrative using file summaries
    narrative = await generate_architecture_narrative(
        repo_name=repo_name,
        language=language,
        framework=framework,
        insights=insights,
        file_summaries=file_summaries,
    )

    narrative_validation = validate_summary(narrative, known_files, known_functions, known_classes)
    if not narrative_validation.is_grounded:
        logger.warning(
            f"Architecture narrative references names not found in the codebase "
            f"(grounding score {narrative_validation.grounding_score:.2f}): "
            f"{narrative_validation.unverified_references}"
        )

    return file_summaries, narrative