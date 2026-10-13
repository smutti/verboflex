"""Bounded syntax extraction without compiling or executing application code."""

from __future__ import annotations

import fnmatch
import json
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated, Literal

import tree_sitter_java
import tree_sitter_kotlin
from pydantic import BaseModel, ConfigDict, Field, field_validator
from tree_sitter import Language, Node, Parser, Tree

from verboflex.integrations.bitbucket.urls import validate_repository_relative_path

MAX_FILES = 500
MAX_FILE_BYTES = 1_048_576
MAX_TOTAL_BYTES = 20_971_520
MAX_NODES = 250_000
MAX_KEYS = 50_000
_EXCLUDED = {"build", ".gradle", ".git", "test", "androidTest", "screenshotTest", "generated"}
_FUNCTIONS = {"function_declaration", "method_declaration"}
_CLASSES = {"object_declaration", "class_declaration", "enum_declaration"}
_ACCESS = {"navigation_expression", "field_access", "scoped_identifier", "qualified_identifier"}


class ComposeCaptureConfig(BaseModel):
    """Reviewed runner and callable fixture previews; no repository commands."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    runner_profile: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
    module: Annotated[str, Field(pattern=r"^(:[A-Za-z][A-Za-z0-9_-]*)+$")] = ":app"
    variant: Annotated[str, Field(pattern=r"^[A-Z][A-Za-z0-9]{0,63}$")] = "Debug"
    preview_functions: Annotated[tuple[str, ...], Field(min_length=1, max_length=100)]
    width_dp: Annotated[int, Field(ge=200, le=2048)] = 1280
    height_dp: Annotated[int, Field(ge=200, le=2048)] = 800

    @field_validator("preview_functions")
    @classmethod
    def functions(cls, names: tuple[str, ...]) -> tuple[str, ...]:
        if any(
            not name or len(name) > 512 or not all(part.isidentifier() for part in name.split("."))
            for name in names
        ) or len(set(names)) != len(names):
            raise ValueError("Invalid preview function")
        return names


class CodeSourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    resource_roots: Annotated[tuple[str, ...], Field(max_length=20)] = ("Res.strings",)
    declaration_symbols: Annotated[tuple[str, ...], Field(max_length=100)] = ()
    localization_calls: Annotated[tuple[str, ...], Field(max_length=20)] = ()
    compose: ComposeCaptureConfig | None = None

    @field_validator("resource_roots", "declaration_symbols", "localization_calls")
    @classmethod
    def valid_names(cls, names: tuple[str, ...]) -> tuple[str, ...]:
        if any(
            not name
            or len(name) > 512
            or any(not part.isidentifier() and part != "*" for part in name.split("."))
            for name in names
        ):
            raise ValueError("Invalid code symbol")
        if len(set(names)) != len(names):
            raise ValueError("Duplicate code symbol")
        return names


class CodeOccurrence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    path: str
    line: int
    column: int
    symbol: str
    function: str | None
    kind: Literal["reference", "declaration", "call"]


class CodePreview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    function: str
    path: str
    line: int
    keys: tuple[str, ...]
    annotation: str
    evidence: Literal["static_reference"] = "static_reference"


class CodeKeyCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    keys: tuple[str, ...]
    occurrences: tuple[CodeOccurrence, ...]
    previews: tuple[CodePreview, ...]


@dataclass
class _Source:
    path: str
    parser: Parser
    tree: Tree
    root: Node
    package: str
    imports: dict[str, str]


def _text(node: Node | None) -> str:
    return (node.text or b"").decode("utf-8") if node is not None else ""


def _walk(root: Node) -> Iterator[Node]:
    stack = [root]
    count = 0
    while stack:
        node = stack.pop()
        count += 1
        if count > MAX_NODES:
            raise ValueError("Code syntax budget exceeded")
        yield node
        stack.extend(reversed(node.named_children))


def _chain(node: Node | None) -> str:
    if node is None:
        return ""
    if node.type in {"identifier", "simple_identifier"}:
        return _text(node)
    if node.type in _ACCESS:
        parts = [_chain(child) for child in node.named_children]
        return ".".join(parts) if all(parts) else ""
    return ""


def _qualified(node: Node, source: _Source) -> str:
    names = [_text(node.child_by_field_name("name"))]
    parent = node.parent
    while parent is not None:
        if parent.type in _CLASSES:
            names.insert(0, _text(parent.child_by_field_name("name")))
        parent = parent.parent
    return ".".join(part for part in (source.package, *names) if part)


def _function(node: Node, source: _Source) -> str | None:
    parent: Node | None = node
    while parent is not None:
        if parent.type in _FUNCTIONS:
            return _qualified(parent, source)
        parent = parent.parent
    return None


def _expand(name: str, source: _Source) -> str:
    first, dot, rest = name.partition(".")
    return source.imports.get(first, first) + (dot + rest if dot else "")


def _source(path: str, content: bytes) -> _Source:
    grammar = tree_sitter_java if path.endswith(".java") else tree_sitter_kotlin
    parser = Parser(Language(grammar.language()))
    tree = parser.parse(content)
    root = tree.root_node
    if root.has_error:
        raise ValueError(f"Incomplete code syntax: {path}")
    package = ""
    imports: dict[str, str] = {}
    for node in root.named_children:
        if node.type in {"package_header", "package_declaration"}:
            package = _text(node).removeprefix("package ").rstrip("; ").strip()
        if node.type in {"import", "import_declaration"}:
            raw = _text(node).removeprefix("import ").removeprefix("static ").rstrip("; ")
            target, _, alias = raw.partition(" as ")
            if target.endswith(".*"):
                continue
            local = alias or target.rsplit(".", 1)[-1]
            if local in imports and imports[local] != target:
                imports[local] = "<ambiguous>"
            else:
                imports[local] = target
    return _Source(path, parser, tree, root, package, imports)


def _occurrence(
    key: str,
    node: Node,
    source: _Source,
    symbol: str,
    kind: Literal["reference", "declaration", "call"],
) -> CodeOccurrence:
    if not key or len(key) > 4096 or "\x00" in key:
        raise ValueError("Invalid localization key")
    return CodeOccurrence(
        key=key,
        path=source.path,
        line=node.start_point.row + 1,
        column=node.start_point.column + 1,
        symbol=symbol,
        function=_function(node, source),
        kind=kind,
    )


def _reference(node: Node, source: _Source, config: CodeSourceConfig) -> str | None:
    name = _chain(node)
    if node.type == "method_invocation":
        args = node.child_by_field_name("arguments")
        method = _text(node.child_by_field_name("name"))
        if args is not None and not args.named_children and method.startswith("get"):
            member = method[3:]
            if member:
                obj = _chain(node.child_by_field_name("object")).removesuffix(".INSTANCE")
                name = obj + "." + member[0].lower() + member[1:]
    if not name:
        return None
    expanded = _expand(name, source)
    for root in config.resource_roots:
        for candidate in (expanded, name):
            prefix = root + "."
            if candidate.startswith(prefix):
                key = candidate[len(prefix) :]
                if key.isidentifier() and key not in {"untranslated", "INSTANCE"}:
                    return key
    return None


def _declaration(node: Node, source: _Source) -> tuple[str, Node] | None:
    expression: Node | None
    parent: Node | None
    if node.type == "property_declaration":
        modifiers = next((c for c in node.named_children if c.type == "modifiers"), None)
        variable = next((c for c in node.named_children if c.type == "variable_declaration"), None)
        if "const" not in _text(modifiers).split() or variable is None:
            return None
        name = _text(variable.named_children[0])
        expression = node.named_children[-1]
    elif node.type == "variable_declarator" and node.parent is not None:
        parent = node.parent
        if parent.type != "field_declaration":
            return None
        modifiers = next((c for c in parent.named_children if c.type == "modifiers"), None)
        if not {"static", "final"}.issubset(_text(modifiers).split()):
            return None
        name = _text(node.child_by_field_name("name"))
        expression = node.child_by_field_name("value")
        if expression is None:
            return None
    elif node.type in {"enum_entry", "enum_constant"}:
        name = _text(node.child_by_field_name("name")) or _text(node.named_children[0])
        arguments = next(
            (c for c in node.named_children if c.type in {"value_arguments", "argument_list"}), None
        )
        expression = node
        if arguments is not None and len(arguments.named_children) == 1:
            expression = arguments.named_children[0]
            if expression.type == "value_argument":
                expression = expression.named_children[-1]
    else:
        return None
    ancestors: list[str] = []
    parent = node.parent
    while parent is not None:
        if parent.type in _CLASSES:
            ancestors.insert(0, _text(parent.child_by_field_name("name")))
        parent = parent.parent
    return ".".join(p for p in (source.package, *ancestors, name) if p), expression


def _literal(node: Node) -> str | None:
    if node.type != "string_literal":
        return None
    if any(
        c.type in {"interpolation", "interpolated_expression", "interpolated_identifier"}
        for c in _walk(node)
    ):
        raise ValueError("Dynamic localization key")
    raw = _text(node)
    if raw.startswith('"""'):
        value = raw[3:-3]
        if "$" in value:
            raise ValueError("Dynamic raw string key")
        return value
    # JSON and ordinary Kotlin/Java strings share the escapes used by keys.
    try:
        value = json.loads(raw.replace("\\$", "$"))
    except ValueError as error:
        raise ValueError("Unsupported localization key escape") from error
    if not isinstance(value, str):
        raise ValueError("Invalid string key")
    return value


def _resolve(
    node: Node,
    scope: str,
    declarations: dict[str, tuple[Node, _Source]],
    seen: frozenset[str] = frozenset(),
) -> str:
    if len(seen) > 64:
        raise ValueError("Constant resolution budget exceeded")
    literal = _literal(node)
    if literal is not None:
        if len(literal) > 4096:
            raise ValueError("Localization key length exceeded")
        return literal
    if node.type == "binary_expression":
        left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
        operators = [c.type for c in node.children if not c.is_named]
        if left is not None and right is not None and operators == ["+"]:
            value = _resolve(left, scope, declarations, seen) + _resolve(
                right, scope, declarations, seen
            )
            if len(value) > 4096:
                raise ValueError("Localization key length exceeded")
            return value
    name = _chain(node)
    options = [key for key in (scope + "." + name, name) if key in declarations]
    if not options:
        options = [key for key in declarations if key.endswith("." + name)] if name else []
    if len(set(options)) != 1 or options[0] in seen:
        raise ValueError("Unresolved or cyclic localization key")
    symbol = options[0]
    expression, _ = declarations[symbol]
    return _resolve(expression, symbol.rpartition(".")[0], declarations, seen | {symbol})


def _call(node: Node) -> tuple[str, Node | None]:
    if node.type == "method_invocation":
        receiver = _chain(node.child_by_field_name("object"))
        method = _text(node.child_by_field_name("name"))
        name = receiver + "." + method if receiver else method
        return name, node.child_by_field_name("arguments")
    if node.type == "call_expression" and node.named_children:
        name = _chain(node.named_children[0])
        args = next((c for c in node.named_children if c.type == "value_arguments"), None)
        return name, args
    return "", None


def _previews(sources: list[_Source], occurrences: list[CodeOccurrence]) -> tuple[CodePreview, ...]:
    keys: dict[str, set[str]] = defaultdict(set)
    for occurrence in occurrences:
        if occurrence.function:
            keys[occurrence.function].add(occurrence.key)
    functions: dict[str, list[Node]] = defaultdict(list)
    for source in sources:
        for node in _walk(source.root):
            if node.type in _FUNCTIONS:
                functions[_qualified(node, source)].append(node)
    calls: dict[str, set[str]] = defaultdict(set)
    for name, overloads in functions.items():
        # Static evidence is conservative: include all overload bodies, without
        # claiming which overload or branch the compiler/runtime will select.
        for function in overloads:
            for node in _walk(function):
                called, _ = _call(node)
                matches = (
                    [n for n in functions if n == called or n.endswith("." + called)]
                    if called
                    else []
                )
                if len(matches) == 1:
                    calls[name].add(matches[0])
    result: list[CodePreview] = []
    for source in sources:
        for node in _walk(source.root):
            if node.type not in _FUNCTIONS:
                continue
            modifiers = next((c for c in node.named_children if c.type == "modifiers"), None)
            if modifiers is None:
                continue
            annotations = [
                c
                for c in _walk(modifiers)
                if c.type == "annotation"
                and _text(c).split("(", 1)[0].split(".")[-1] in {"@Preview", "Preview"}
            ]
            if not annotations:
                continue
            name = _qualified(node, source)
            visited: set[str] = set()
            pending = [name]
            while pending:
                target = pending.pop()
                if target not in visited:
                    visited.add(target)
                    pending.extend(calls[target] - visited)
            related = tuple(sorted({key for target in visited for key in keys[target]}))
            for annotation in annotations:
                result.append(
                    CodePreview(
                        function=name,
                        path=source.path,
                        line=node.start_point.row + 1,
                        keys=related,
                        annotation=_text(annotation)[:4096],
                    )
                )
    return tuple(result)


def extract_catalog(files: dict[str, bytes], config: CodeSourceConfig) -> CodeKeyCatalog:
    """Return a complete catalog or fail; never return a partial successful result."""
    if len(files) > MAX_FILES or sum(len(content) for content in files.values()) > MAX_TOTAL_BYTES:
        raise ValueError("Code source budget exceeded")
    sources: list[_Source] = []
    for path, content in sorted(files.items()):
        validate_repository_relative_path(path)
        if len(content) > MAX_FILE_BYTES:
            raise ValueError("Code file budget exceeded")
        if not path.endswith((".kt", ".java")) or _EXCLUDED.intersection(path.split("/")):
            continue
        content.decode("utf-8", errors="strict")
        source = _source(path, content)
        for local, target in source.imports.items():
            if target == "<ambiguous>" and any(
                local in root.split(".") for root in config.resource_roots
            ):
                raise ValueError(f"Ambiguous resource import: {path}")
        sources.append(source)
    declarations: dict[str, tuple[Node, _Source]] = {}
    occurrences: list[CodeOccurrence] = []
    for source in sources:
        for node in _walk(source.root):
            definition = (
                _declaration(node, source)
                if (config.declaration_symbols or config.localization_calls)
                else None
            )
            if definition:
                symbol, expression = definition
                if symbol in declarations:
                    raise ValueError("Ambiguous constant declaration")
                declarations[symbol] = expression, source
    declared_keys: set[str] = set()
    for symbol, (expression, source) in declarations.items():
        if any(fnmatch.fnmatchcase(symbol, pattern) for pattern in config.declaration_symbols):
            key = _resolve(expression, symbol.rpartition(".")[0], declarations, frozenset({symbol}))
            if key in declared_keys:
                raise ValueError("Duplicate localization key declaration")
            declared_keys.add(key)
            occurrences.append(_occurrence(key, expression, source, symbol, "declaration"))
    for source in sources:
        for node in _walk(source.root):
            referenced_key = _reference(node, source, config)
            if referenced_key:
                occurrences.append(
                    _occurrence(referenced_key, node, source, _text(node), "reference")
                )
            name, args = _call(node)
            if (
                name
                and args is not None
                and (
                    name in config.localization_calls
                    or _expand(name, source) in config.localization_calls
                )
            ):
                if not args.named_children:
                    raise ValueError("Localization call requires a key")
                argument = args.named_children[0]
                expression = (
                    argument.named_children[-1] if argument.type == "value_argument" else argument
                )
                key = _resolve(expression, source.package, declarations)
                occurrences.append(_occurrence(key, node, source, name, "call"))
            if len(occurrences) > MAX_KEYS:
                raise ValueError("Code key budget exceeded")
    occurrences.sort(key=lambda item: (item.path, item.line, item.column, item.key))
    return CodeKeyCatalog(
        keys=tuple(sorted({item.key for item in occurrences})),
        occurrences=tuple(occurrences),
        previews=_previews(sources, occurrences),
    )
