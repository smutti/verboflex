"""Administrator-only product identity and candidate revision routes."""

from typing import Annotated, Any, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from verboflex.auth.principal import Principal, require_roles
from verboflex.db.session import get_db_session
from verboflex.schemas.admin_products import (
    AdminProductConflictResponse,
    AdminProductCreateRequest,
    AdminProductLifecycleConflictResponse,
    AdminProductListResponse,
    AdminProductPublishRequest,
    AdminProductReactivateRequest,
    AdminProductResponse,
    AdminProductRevisionSummary,
    AdminProductStatus,
    AdminProductUpdateRequest,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.schemas.users import RoleName
from verboflex.services.products import (
    InvalidProductCursor,
    ProductNameConflict,
    ProductNotFound,
    ProductRecord,
    ProductRevisionRecord,
    ProductVersionConflict,
    create_product,
    get_product,
    list_products,
    save_product_candidate,
)
from verboflex.services.publication import (
    PublicationBlocked,
    PublicationConflict,
    PublicationNotFound,
    deactivate_product,
    publish_product_candidate,
    reactivate_product,
)

router = APIRouter(prefix="/admin/products", tags=["admin-products"])
AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.ADMIN))]
AdminSession = Annotated[Session, Depends(get_db_session, use_cache=False)]


def _revision_response(
    revision: ProductRevisionRecord | None,
) -> AdminProductRevisionSummary | None:
    if revision is None:
        return None
    return AdminProductRevisionSummary(
        id=revision.id,
        version=revision.version,
        name=revision.name,
        description=revision.description,
        is_published=revision.is_published,
    )


def _response(record: ProductRecord) -> AdminProductResponse:
    return AdminProductResponse(
        id=record.id,
        name=record.name,
        is_active=record.is_active,
        active_revision=_revision_response(record.active_revision),
        candidate_revision=_revision_response(record.candidate_revision),
    )


def _name_conflict_response() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Product name is unavailable", "field": "name"},
    )


def _raise_product_error(error: Exception) -> NoReturn:
    if isinstance(error, ProductNotFound):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product unavailable",
        ) from error
    if isinstance(error, ProductVersionConflict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product candidate conflict",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="Invalid product input",
    ) from error


AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
}
CREATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_RESPONSES,
    status.HTTP_409_CONFLICT: {"model": AdminProductConflictResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}
DETAIL_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_RESPONSES,
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}
UPDATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_RESPONSES,
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": AdminProductConflictResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}
LIFECYCLE_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_RESPONSES,
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": AdminProductLifecycleConflictResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}


def _lifecycle_conflict_response(error: Exception) -> JSONResponse:
    if isinstance(error, PublicationBlocked):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "Product publication blocked",
                "blockers": [blocker.value for blocker in error.blockers],
            },
        )
    if isinstance(error, PublicationConflict):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Product lifecycle conflict", "blockers": []},
        )
    if isinstance(error, PublicationNotFound):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product unavailable",
        ) from error
    raise error


@router.get(
    "",
    operation_id="list_admin_products",
    response_model=AdminProductListResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def list_admin_product_collection(
    _principal: AdminPrincipal,
    session: AdminSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    status_filter: Annotated[AdminProductStatus | None, Query(alias="status")] = None,
) -> AdminProductListResponse:
    """List products in stable server-owned identity order."""
    try:
        page = list_products(
            session,
            limit=limit,
            cursor=cursor,
            status=status_filter,
        )
    except InvalidProductCursor as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid cursor",
        ) from error
    return AdminProductListResponse(
        items=[_response(record) for record in page.items],
        next_cursor=page.next_cursor,
    )


@router.post(
    "",
    operation_id="create_admin_product",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminProductResponse,
    responses=CREATE_RESPONSES,
)
async def create_admin_product(
    payload: AdminProductCreateRequest,
    _principal: AdminPrincipal,
    session: AdminSession,
) -> AdminProductResponse | JSONResponse:
    """Create one stable UUID with an unpublished candidate revision."""
    try:
        product = create_product(
            session,
            name=payload.name,
            description=payload.description,
        )
        record = get_product(session, product_id=product.id)
    except ProductNameConflict:
        return _name_conflict_response()
    except (ProductNotFound, ProductVersionConflict, ValueError) as error:
        _raise_product_error(error)
    return _response(record)


@router.get(
    "/{product_id}",
    operation_id="get_admin_product",
    response_model=AdminProductResponse,
    responses=DETAIL_RESPONSES,
)
async def get_admin_product_detail(
    product_id: UUID,
    _principal: AdminPrincipal,
    session: AdminSession,
) -> AdminProductResponse:
    """Return explicitly separate active and candidate summaries."""
    try:
        record = get_product(session, product_id=product_id)
    except ProductNotFound as error:
        _raise_product_error(error)
    return _response(record)


@router.patch(
    "/{product_id}",
    operation_id="update_admin_product_candidate",
    response_model=AdminProductResponse,
    responses=UPDATE_RESPONSES,
)
async def update_admin_product_candidate(
    product_id: UUID,
    payload: AdminProductUpdateRequest,
    _principal: AdminPrincipal,
    session: AdminSession,
) -> AdminProductResponse | JSONResponse:
    """Compare and save one candidate without exposing publication mechanics."""
    try:
        save_product_candidate(
            session,
            product_id=product_id,
            expected_version=payload.expected_candidate_version,
            name=payload.name,
            description=payload.description,
        )
        record = get_product(session, product_id=product_id)
    except ProductNameConflict:
        return _name_conflict_response()
    except (ProductNotFound, ProductVersionConflict, ValueError) as error:
        _raise_product_error(error)
    return _response(record)


@router.post(
    "/{product_id}/publish",
    operation_id="publish_admin_product_candidate",
    response_model=AdminProductResponse,
    responses=LIFECYCLE_RESPONSES,
)
async def publish_admin_product(
    product_id: UUID,
    payload: AdminProductPublishRequest,
    _principal: AdminPrincipal,
    session: AdminSession,
) -> AdminProductResponse | JSONResponse:
    """Publish only a complete and currently confirmed candidate revision."""
    try:
        publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=payload.candidate_revision_id,
            expected_candidate_version=payload.expected_candidate_version,
        )
        return _response(get_product(session, product_id=product_id))
    except (PublicationBlocked, PublicationConflict, PublicationNotFound) as error:
        return _lifecycle_conflict_response(error)


@router.post(
    "/{product_id}/deactivate",
    operation_id="deactivate_admin_product",
    response_model=AdminProductResponse,
    responses={
        **AUTH_RESPONSES,
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
async def deactivate_admin_product(
    product_id: UUID,
    _principal: AdminPrincipal,
    session: AdminSession,
) -> AdminProductResponse | JSONResponse:
    """Suspend operation while retaining active and candidate configuration."""
    try:
        deactivate_product(session, product_id=product_id)
        return _response(get_product(session, product_id=product_id))
    except PublicationNotFound as error:
        return _lifecycle_conflict_response(error)


@router.post(
    "/{product_id}/reactivate",
    operation_id="reactivate_admin_product",
    response_model=AdminProductResponse,
    responses=LIFECYCLE_RESPONSES,
)
async def reactivate_admin_product_route(
    product_id: UUID,
    payload: AdminProductReactivateRequest,
    _principal: AdminPrincipal,
    session: AdminSession,
) -> AdminProductResponse | JSONResponse:
    """Resume only a published revision with a current preview confirmation."""
    try:
        reactivate_product(
            session,
            product_id=product_id,
            active_revision_id=payload.active_revision_id,
            expected_active_version=payload.expected_active_version,
        )
        return _response(get_product(session, product_id=product_id))
    except (PublicationBlocked, PublicationConflict, PublicationNotFound) as error:
        return _lifecycle_conflict_response(error)
