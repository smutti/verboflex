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
    AdminProductListResponse,
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
    if isinstance(error, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid product input",
        ) from error
    raise error


COMMON_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": AdminProductConflictResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}


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
    principal: AdminPrincipal,
    session: AdminSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    status_filter: Annotated[AdminProductStatus | None, Query(alias="status")] = None,
) -> AdminProductListResponse:
    """List products in stable server-owned identity order."""
    del principal
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
    responses=COMMON_RESPONSES,
)
async def create_admin_product(
    payload: AdminProductCreateRequest,
    principal: AdminPrincipal,
    session: AdminSession,
) -> AdminProductResponse | JSONResponse:
    """Create one stable UUID with an unpublished candidate revision."""
    del principal
    try:
        product = create_product(
            session,
            name=payload.name,
            description=payload.description,
        )
        record = get_product(session, product_id=product.id)
    except ProductNameConflict:
        return _name_conflict_response()
    except Exception as error:
        _raise_product_error(error)
    return _response(record)


@router.get(
    "/{product_id}",
    operation_id="get_admin_product",
    response_model=AdminProductResponse,
    responses=COMMON_RESPONSES,
)
async def get_admin_product_detail(
    product_id: UUID,
    principal: AdminPrincipal,
    session: AdminSession,
) -> AdminProductResponse:
    """Return explicitly separate active and candidate summaries."""
    del principal
    try:
        record = get_product(session, product_id=product_id)
    except Exception as error:
        _raise_product_error(error)
    return _response(record)


@router.patch(
    "/{product_id}",
    operation_id="update_admin_product_candidate",
    response_model=AdminProductResponse,
    responses=COMMON_RESPONSES,
)
async def update_admin_product_candidate(
    product_id: UUID,
    payload: AdminProductUpdateRequest,
    principal: AdminPrincipal,
    session: AdminSession,
) -> AdminProductResponse | JSONResponse:
    """Compare and save one candidate without exposing publication mechanics."""
    del principal
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
    except Exception as error:
        _raise_product_error(error)
    return _response(record)
