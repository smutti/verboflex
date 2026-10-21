"""HTML email text fragments identified by filename and structural address."""

from verboflex.localization.html import html_path, html_skeleton, html_variables, index_html
from verboflex.localization.importing.core import (
    CanonicalIssue,
    CanonicalLocator,
    CanonicalParseResult,
    CanonicalParserInput,
    CanonicalSelector,
    CanonicalStructureNode,
    CanonicalValue,
    CanonicalValueBuffer,
    canonical_value_order,
)
from verboflex.localization.preview.core import normalize_preview_locale


def parse_html(parser_input: CanonicalParserInput) -> CanonicalParseResult:
    try:
        identity = html_path(parser_input.path)
        root = parser_input.layout_identity.removeprefix("html:")
        if (
            parser_input.format != "html"
            or not parser_input.layout_identity.startswith("html:")
            or identity is None
            or (root != "." and not parser_input.path.startswith(root + "/"))
        ):
            raise ValueError("HTML layout mismatch")
        language, family, _ = identity
        relative_family = family if root == "." else family.removeprefix(root + "/")
        fragments, protected_digest = index_html(parser_input.content)
        skeleton = html_skeleton(parser_input.content, fragments)
        values = CanonicalValueBuffer(source_bytes=len(parser_input.content))
        for position, fragment in enumerate(fragments):
            source = parser_input.repository_side == "keys" or language == normalize_preview_locale(
                parser_input.base_language
            )
            values.append(
                CanonicalValue(
                    logical_key=f"{relative_family}::{fragment.address}",
                    language=language,
                    selector=CanonicalSelector(kind="scalar", fields=()),
                    source_text=fragment.text if source else None,
                    translated_text=None if source else fragment.text,
                    display_text=fragment.text,
                    structure=(
                        CanonicalStructureNode(
                            kind="html:document",
                            fields=(("protected_digest", protected_digest),)
                            + ((("skeleton", skeleton),) if position == 0 else ()),
                        ),
                        CanonicalStructureNode(
                            kind="html:text", fields=(("element", fragment.element),)
                        ),
                    ),
                    locator=CanonicalLocator(
                        format="html",
                        repository_side=parser_input.repository_side,
                        path=parser_input.path,
                        position=position,
                        structural_address=(fragment.address,),
                    ),
                )
            )
        return CanonicalParseResult(values=tuple(sorted(values, key=canonical_value_order)))
    except ValueError, UnicodeError:
        return CanonicalParseResult(
            issues=(
                CanonicalIssue(
                    code="unsupported_structure",
                    repository_side=parser_input.repository_side,
                    path=parser_input.path,
                    message="Unsupported HTML document or filename locale.",
                ),
            )
        )


def compatible_html_peers(inputs: tuple[CanonicalParserInput, ...]) -> bool:
    """Decline accidental text alignment when language peers have different shapes."""
    shapes: dict[tuple[str, str], tuple[object, ...]] = {}
    for item in inputs:
        if item.format != "html":
            continue
        identity = html_path(item.path)
        if identity is None:
            return False
        try:
            fragments, _ = index_html(item.content)
        except ValueError, UnicodeError:
            return False
        shape = tuple((part.address, html_variables(part.text)) for part in fragments)
        key = (item.repository_side, identity[1])
        if key in shapes and shapes[key] != shape:
            return False
        shapes[key] = shape
    return True
