"""Product team endpoints and one-time temporary account credentials."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from verboflex.auth.principal import CurrentPrincipal
from verboflex.db.session import get_db_session
from verboflex.schemas.product_team import (
    AddMemberInput,
    MemberAdded,
    MemberInput,
    ProductAccess,
    TeamResponse,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.services import product_team as service

router = APIRouter(
    tags=["product-team"],
    responses={
        **{code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 503)},
        422: {
            "content": {
                "application/json": {
                    "schema": {
                        "anyOf": [
                            {"$ref": "#/components/schemas/ErrorResponse"},
                            {"$ref": "#/components/schemas/HTTPValidationError"},
                        ]
                    }
                }
            }
        },
    },
)
Db = Annotated[Session, Depends(get_db_session, use_cache=False)]


def _run[T](session: Session, operation: Callable[[], T]) -> T:
    try:
        with session.begin():
            return operation()
    except service.TeamError as error:
        raise HTTPException(error.status, str(error)) from error


@router.get("/products/{product_id}/access", operation_id="getProductAccess")
def get_access(
    product_id: UUID, principal: CurrentPrincipal, session: Db, response: Response
) -> ProductAccess:
    response.headers["Cache-Control"] = "no-store"
    return _run(session, lambda: service.access(session, product_id, principal.user_id))


@router.get("/products/{product_id}/team", operation_id="getProductTeam")
def get_team(
    product_id: UUID, principal: CurrentPrincipal, session: Db, response: Response
) -> TeamResponse:
    response.headers["Cache-Control"] = "no-store"
    return _run(session, lambda: service.team(session, product_id, principal.user_id))


@router.put("/products/{product_id}/team/members", operation_id="setProductMember", status_code=204)
def set_member(
    product_id: UUID, data: MemberInput, principal: CurrentPrincipal, session: Db
) -> Response:
    _run(session, lambda: service.set_member(session, product_id, principal.user_id, data))
    return Response(status_code=204)


@router.delete(
    "/products/{product_id}/team/members/{user_id}",
    operation_id="removeProductMember",
    status_code=204,
)
def remove_member(
    product_id: UUID,
    user_id: UUID,
    expected_version: UUID,
    principal: CurrentPrincipal,
    session: Db,
) -> Response:
    _run(
        session,
        lambda: service.remove_member(
            session, product_id, principal.user_id, user_id, expected_version
        ),
    )
    return Response(status_code=204)


@router.post(
    "/products/{product_id}/team/members", operation_id="addProductMember", status_code=201
)
def add_member(
    product_id: UUID,
    data: AddMemberInput,
    principal: CurrentPrincipal,
    session: Db,
    response: Response,
) -> MemberAdded:
    response.headers["Cache-Control"] = "no-store"
    return _run(session, lambda: service.add_member(session, product_id, principal.user_id, data))
