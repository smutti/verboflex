"""Administrator-only, optimistic source fallback configuration; no repository I/O."""

import hashlib
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, select

from verboflex.api.v1.routes.admin_products import AdminPrincipal, AdminSession
from verboflex.audit.ledger import record_audit
from verboflex.models.product import Product
from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.models.source_fallback import SourceFallbackPolicy, SourceFallbackText
from verboflex.schemas.source_fallback import SourceFallbackResponse, SourceFallbackWrite
from verboflex.schemas.system import ErrorResponse

router = APIRouter(prefix="/admin/products/{product_id}/source-fallback", tags=["admin-products"])
ERRORS: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse} for status in (401, 403, 404, 409)
}


def _product(session: AdminSession, product_id: UUID, *, lock: bool = False) -> Product:
    statement = select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
    product = session.scalar(statement.with_for_update() if lock else statement)
    if product is None:
        raise HTTPException(404, "Product unavailable")
    return product


def _languages(session: AdminSession, product: Product) -> list[str]:
    return list(
        session.scalars(
            select(ProductRepositoryMapping.base_language)
            .where(
                ProductRepositoryMapping.revision_id == product.active_revision_id,
                ProductRepositoryMapping.base_language.is_not(None),
            )
            .distinct()
            .order_by(ProductRepositoryMapping.base_language)
        )
    )


def _response(session: AdminSession, product: Product) -> SourceFallbackResponse:
    policy = session.get(SourceFallbackPolicy, product.id)
    texts = list(
        session.scalars(
            select(SourceFallbackText.source_text)
            .where(
                SourceFallbackText.product_id == product.id,
            )
            .order_by(SourceFallbackText.source_text)
        )
    )
    return SourceFallbackResponse(
        product_id=product.id,
        version=policy.version if policy else 0,
        enabled=policy.enabled if policy else False,
        language=policy.language if policy else None,
        source_texts=texts,
        available_languages=_languages(session, product),
    )


@router.get(
    "",
    operation_id="get_admin_source_fallback",
    response_model=SourceFallbackResponse,
    responses=ERRORS,
)
def get_policy(
    product_id: UUID, principal: AdminPrincipal, session: AdminSession
) -> SourceFallbackResponse:
    # Serialize configuration reads with writes so version and selection are one snapshot.
    return _response(session, _product(session, product_id, lock=True))


@router.put(
    "",
    operation_id="update_admin_source_fallback",
    response_model=SourceFallbackResponse,
    responses=ERRORS,
)
def update_policy(
    product_id: UUID, payload: SourceFallbackWrite, principal: AdminPrincipal, session: AdminSession
) -> SourceFallbackResponse:
    product = _product(session, product_id, lock=True)
    policy = session.get(SourceFallbackPolicy, product_id)
    if payload.expected_version != (policy.version if policy else 0):
        raise HTTPException(409, "Source fallback settings changed; reload before saving")
    if payload.enabled and payload.language not in _languages(session, product):
        raise HTTPException(409, "Select a base language in the published product configuration")
    if policy is None:
        policy = SourceFallbackPolicy(
            product_id=product_id, version=1, enabled=payload.enabled, language=payload.language
        )
        session.add(policy)
    else:
        policy.version += 1
        policy.enabled, policy.language = payload.enabled, payload.language
    session.flush()
    session.execute(delete(SourceFallbackText).where(SourceFallbackText.product_id == product_id))
    session.add_all(
        SourceFallbackText(
            product_id=product_id,
            source_digest=hashlib.sha256(value.encode("utf-8")).hexdigest(),
            source_text=value,
        )
        for value in payload.source_texts
    )
    record_audit(
        session, actor_id=principal.user_id, action="product.updated", entity_id=product_id
    )
    session.flush()
    response = _response(session, product)
    session.commit()
    return response
