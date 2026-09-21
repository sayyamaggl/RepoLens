"""
ast_parser — Parse source files with tree-sitter to extract structural info.

Extracts functions, classes, imports, and exports from Python and JS/TS files.
This feeds the dependency_graph and insight_engine modules.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Parser

logger = logging.getLogger(__name__)

# Initialize languages
PY_LANGUAGE = Language(tspython.language(), "python")
JS_LANGUAGE = Language(tsjavascript.language(), "javascript")
TS_LANGUAGE = Language(tstypescript.language_typescript(), "typescript")
TSX_LANGUAGE = Language(tstypescript.language_tsx(), "tsx")

# Language name -> tree-sitter Language mapping.
# NOTE: "TypeScript" defaults to the plain .ts grammar here; parse_file()
# switches to TSX_LANGUAGE for files ending in .tsx, since JSX syntax needs
# the tsx grammar specifically (the plain ts grammar can't parse JSX).
LANG_MAP = {
    "Python": PY_LANGUAGE,
    "JavaScript": JS_LANGUAGE,
    "TypeScript": TS_LANGUAGE,
}


@dataclass
class ParsedFile:
    """Structured representation of a parsed source file."""
    path: str
    language: str
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    raw_import_paths: list[str] = field(default_factory=list)  # Resolved import paths
    parse_error: Optional[str] = None


def _get_node_text(node, source_code: bytes) -> str:
    """Extract text content from a tree-sitter node."""
    return source_code[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _extract_python(root_node, source_code: bytes) -> ParsedFile:
    """Extract structures from a Python AST."""
    functions = []
    classes = []
    imports = []
    raw_import_paths = []
    exports = []

    def walk(node, depth=0):
        # Function definitions (top-level and class methods)
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node and depth <= 1:
                functions.append(_get_node_text(name_node, source_code))

        # Class definitions
        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                classes.append(_get_node_text(name_node, source_code))

        # Import statements
        elif node.type == "import_statement":
            text = _get_node_text(node, source_code)
            imports.append(text)
            # Extract module path
            for child in node.children:
                if child.type == "dotted_name":
                    raw_import_paths.append(_get_node_text(child, source_code))

        elif node.type == "import_from_statement":
            text = _get_node_text(node, source_code)
            imports.append(text)
            # Extract module path
            module_node = node.child_by_field_name("module_name")
            if module_node:
                raw_import_paths.append(_get_node_text(module_node, source_code))
            else:
                # Relative imports like "from . import x"
                for child in node.children:
                    if child.type == "relative_import":
                        raw_import_paths.append(_get_node_text(child, source_code))

        # __all__ exports
        elif node.type == "expression_statement":
            text = _get_node_text(node, source_code)
            if "__all__" in text:
                exports.append(text)

        # Recurse into children
        for child in node.children:
            new_depth = depth + 1 if node.type == "class_definition" else depth
            walk(child, new_depth)

    walk(root_node)

    return ParsedFile(
        path="",
        language="Python",
        functions=functions,
        classes=classes,
        imports=imports,
        exports=exports,
        raw_import_paths=raw_import_paths,
    )


def _extract_javascript(root_node, source_code: bytes) -> ParsedFile:
    """Extract structures from a JavaScript/TypeScript AST."""
    functions = []
    classes = []
    imports = []
    raw_import_paths = []
    exports = []

    def walk(node, depth=0):
        # Function declarations
        if node.type in ("function_declaration", "generator_function_declaration"):
            name_node = node.child_by_field_name("name")
            if name_node and depth == 0:
                functions.append(_get_node_text(name_node, source_code))

        # Arrow functions / const assignments at top level
        elif node.type == "lexical_declaration" and depth == 0:
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    value_node = child.child_by_field_name("value")
                    if name_node and value_node and value_node.type == "arrow_function":
                        functions.append(_get_node_text(name_node, source_code))

        # Class declarations
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                classes.append(_get_node_text(name_node, source_code))

        # Import statements
        elif node.type == "import_statement":
            text = _get_node_text(node, source_code)
            imports.append(text)
            source_node = node.child_by_field_name("source")
            if source_node:
                path = _get_node_text(source_node, source_code).strip("'\"")
                raw_import_paths.append(path)

        # Export statements
        elif node.type in ("export_statement",):
            text = _get_node_text(node, source_code)
            exports.append(text)
            # Check for re-exports
            source_node = node.child_by_field_name("source")
            if source_node:
                path = _get_node_text(source_node, source_code).strip("'\"")
                raw_import_paths.append(path)

        # Require calls (CommonJS)
        elif node.type == "call_expression":
            fn_node = node.child_by_field_name("function")
            if fn_node and _get_node_text(fn_node, source_code) == "require":
                args = node.child_by_field_name("arguments")
                if args and args.child_count > 1:
                    arg = args.children[1]  # Skip the opening paren
                    path = _get_node_text(arg, source_code).strip("'\"")
                    imports.append(f'require("{path}")')
                    raw_import_paths.append(path)

        for child in node.children:
            walk(child, depth + (1 if node.type in ("class_declaration", "class_body") else 0))

    walk(root_node)

    return ParsedFile(
        path="",
        language="JavaScript",
        functions=functions,
        classes=classes,
        imports=imports,
        exports=exports,
        raw_import_paths=raw_import_paths,
    )


def parse_file(file_path: str, language: str) -> ParsedFile:
    """
    Parse a single source file and extract its structural information.

    Args:
        file_path: Absolute path to the source file
        language: Programming language ("Python", "JavaScript", "TypeScript")

    Returns:
        ParsedFile with extracted functions, classes, imports, exports
    """
    ts_language = LANG_MAP.get(language)
    if not ts_language:
        return ParsedFile(
            path=file_path,
            language=language,
            parse_error=f"Unsupported language: {language}",
        )

    # .tsx needs the dedicated tsx grammar (JSX syntax), not the plain ts one.
    if language == "TypeScript" and file_path.endswith(".tsx"):
        ts_language = TSX_LANGUAGE

    try:
        with open(file_path, "rb") as f:
            source_code = f.read()
    except (IOError, OSError) as e:
        return ParsedFile(
            path=file_path,
            language=language,
            parse_error=f"Could not read file: {e}",
        )

    # Skip very large files (>500KB) to avoid memory issues
    if len(source_code) > 500_000:
        return ParsedFile(
            path=file_path,
            language=language,
            parse_error="File too large (>500KB), skipped",
        )

    parser = Parser()
    parser.set_language(ts_language)
    tree = parser.parse(source_code)

    if language == "Python":
        parsed = _extract_python(tree.root_node, source_code)
    else:
        # TS/TSX grammars are structural supersets of JS for the node types
        # we extract (functions, classes, imports, exports), so the same
        # walker works for JavaScript, TypeScript, and TSX.
        parsed = _extract_javascript(tree.root_node, source_code)
        parsed.language = language

    parsed.path = file_path
    return parsed


def parse_repo(source_files: list[dict]) -> list[ParsedFile]:
    """
    Parse all source files in a repository.

    Args:
        source_files: List of dicts with 'path', 'language', 'absolute_path'

    Returns:
        List of ParsedFile objects
    """
    parsed_files = []

    for file_info in source_files:
        language = file_info["language"]
        if language not in LANG_MAP:
            continue

        parsed = parse_file(file_info["absolute_path"], language)
        parsed.path = file_info["path"]  # Use relative path
        parsed_files.append(parsed)

        if parsed.parse_error:
            logger.warning(f"Parse error for {file_info['path']}: {parsed.parse_error}")
        else:
            logger.debug(
                f"Parsed {file_info['path']}: "
                f"{len(parsed.functions)} functions, "
                f"{len(parsed.classes)} classes, "
                f"{len(parsed.imports)} imports"
            )

    logger.info(f"Parsed {len(parsed_files)} files total")
    return parsed_files