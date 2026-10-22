"""Read-only, bounded email workspace projections from the current imported dataset."""

import re
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from verboflex.auth.product_access import product_roles
from verboflex.localization.html_preview import passive_html_preview
from verboflex.models.import_job import ImportExecution
from verboflex.models.product import Product
from verboflex.models.review import TranslationProposalValue
from verboflex.models.translation import TranslationKey, TranslationValue, TranslationValueLocator
from verboflex.services.product_summary import _ACTIVE_MAPPING_SQL


class HtmlEditorUnavailable(LookupError):
    """The current authorized HTML dataset is unavailable."""


MAX_EDITOR_TEXT_BYTES = 2_097_152


class HtmlTemplateOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_id: UUID
    scope_id: UUID
    name: str
    language: str
    base_language: str | None
    path: str


class HtmlTemplateCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[HtmlTemplateOption]
    next_cursor: UUID | None


class HtmlEditorFragment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_id: UUID
    marker: str
    position: int
    element: str
    text: str


class HtmlEditorDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: UUID
    language: str
    path: str
    execution_id: UUID
    document: Annotated[str, Field(max_length=2_097_152)]
    fragments: list[HtmlEditorFragment]
    missing_images: Annotated[int, Field(ge=0)]


_CATALOG = text(f"""
SELECT value.id AS group_id, scope.id AS scope_id, key.raw_key,
       value.language, mapping.base_language, locator.path
FROM products AS product
JOIN localization_scopes AS scope ON scope.product_id = product.id
 AND scope.active_execution_id IS NOT NULL AND {_ACTIVE_MAPPING_SQL}
JOIN product_repository_mappings AS mapping ON mapping.id = scope.current_mapping_id
JOIN translation_keys AS key ON key.scope_id = scope.id AND key.product_id = product.id
JOIN translation_values AS value ON value.translation_key_id = key.id AND value.scope_id = scope.id
JOIN translation_value_locators AS locator ON locator.value_id = value.id
 AND locator.import_execution_id = scope.active_execution_id
WHERE product.id = :product_id AND product.is_active AND product.deleted_at IS NULL
 AND NOT key.is_deleted AND NOT value.is_deleted
 AND locator.format = 'html' AND locator.position = 0
 AND value.id > :after
ORDER BY value.id
LIMIT 201
""")


def list_templates(
    session: Session, *, product_id: UUID, actor_id: UUID, after: UUID | None
) -> HtmlTemplateCatalog:
    product = session.get(Product, product_id)
    if (
        product is None
        or not product.is_active
        or product.deleted_at is not None
        or not product_roles(session, actor_id, product_id)
    ):
        raise HtmlEditorUnavailable
    rows = (
        session.execute(_CATALOG, {"product_id": product_id, "after": after or UUID(int=0)})
        .mappings()
        .all()
    )
    return HtmlTemplateCatalog(
        items=[
            HtmlTemplateOption(
                group_id=row["group_id"],
                scope_id=row["scope_id"],
                name=row["raw_key"].rsplit("::", 1)[0],
                language=row["language"],
                base_language=row["base_language"],
                path=row["path"],
            )
            for row in rows[:200]
        ],
        next_cursor=rows[199]["group_id"] if len(rows) > 200 else None,
    )


def editor_document(
    session: Session, *, group_id: UUID, product_id: UUID, language: str
) -> HtmlEditorDocument:
    """Caller must resolve current group access before reading this projection."""
    anchor = session.get(TranslationValueLocator, group_id)
    value = session.get(TranslationValue, group_id)
    if anchor is None or anchor.format != "html" or value is None or value.is_deleted:
        raise HtmlEditorUnavailable
    query = (
        select(TranslationValue, TranslationValueLocator, TranslationProposalValue.proposed_text)
        .join(TranslationValueLocator, TranslationValueLocator.value_id == TranslationValue.id)
        .join(TranslationKey, TranslationKey.id == TranslationValue.translation_key_id)
        .outerjoin(
            TranslationProposalValue,
            TranslationProposalValue.translation_value_id == TranslationValue.id,
        )
        .where(
            TranslationKey.product_id == product_id,
            TranslationKey.is_deleted.is_(False),
            TranslationValue.scope_id == value.scope_id,
            TranslationValue.language == language,
            TranslationValue.is_deleted.is_(False),
            TranslationValueLocator.import_execution_id == anchor.import_execution_id,
            TranslationValueLocator.repository_id == anchor.repository_id,
            TranslationValueLocator.repository_side == anchor.repository_side,
            TranslationValueLocator.path == anchor.path,
            TranslationValueLocator.format == "html",
        )
        .order_by(TranslationValueLocator.position)
        .limit(5001)
    )
    # Check the aggregate in PostgreSQL before loading pending text into memory:
    # individually valid proposals can collectively exceed the imported file size.
    count, text_bytes = session.execute(
        query.with_only_columns(
            func.count(),
            func.coalesce(
                func.sum(
                    func.octet_length(
                        func.coalesce(
                            TranslationProposalValue.proposed_text,
                            TranslationValue.translated_text,
                            TranslationValue.source_text,
                            "",
                        )
                    )
                ),
                0,
            ),
        )
        .order_by(None)
        .limit(None)
    ).one()
    if not 0 < count <= 5000 or text_bytes > MAX_EDITOR_TEXT_BYTES:
        raise HtmlEditorUnavailable
    rows = session.execute(query).all()
    skeleton = None
    fragments = []
    nonce = uuid4().hex
    markers = {}
    for item, locator, pending in rows:
        element = "text"
        for node in item.structure:
            if not isinstance(node, dict):
                continue
            for field in node.get("fields", []):
                if not isinstance(field, dict):
                    continue
                if node.get("kind") == "html:document" and field.get("name") == "skeleton":
                    skeleton = field.get("value")
                if node.get("kind") == "html:text" and field.get("name") == "element":
                    element = str(field.get("value", "text"))
        marker = f"VERBOFLEX-EDITOR:{nonce}:{locator.position}"
        markers[str(locator.position)] = marker
        fragments.append(
            HtmlEditorFragment(
                group_id=item.id,
                marker=f"<!--{marker}-->",
                position=locator.position,
                element=element,
                text=pending
                if pending is not None
                else (
                    item.translated_text
                    if item.translated_text is not None
                    else item.source_text or ""
                ),
            )
        )
    if not isinstance(skeleton, str) or len(rows) > 5000 or not rows:
        raise HtmlEditorUnavailable
    document = re.sub(
        r"<!--VERBOFLEX-TEXT:(\d+)-->",
        lambda match: f"<!--{markers[match[1]]}-->" if match[1] in markers else "",
        skeleton,
    )
    execution = session.get(ImportExecution, anchor.import_execution_id)
    images = (
        (execution.html_preview_images or {}).get(anchor.repository_side, {}) if execution else {}
    )
    preview = passive_html_preview(
        document, template_path=anchor.path, images=images, markers=frozenset(markers.values())
    )
    if any(fragment.marker not in preview.document for fragment in fragments):
        raise HtmlEditorUnavailable
    return HtmlEditorDocument(
        product_id=product_id,
        language=language,
        path=anchor.path,
        execution_id=anchor.import_execution_id,
        document=preview.document,
        fragments=fragments,
        missing_images=preview.missing_images,
    )
