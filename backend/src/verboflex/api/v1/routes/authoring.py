"""Authenticated authoring; all repository I/O remains in submission workers."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from verboflex.auth.principal import CurrentPrincipal
from verboflex.db.session import get_db_session
from verboflex.schemas.authoring import (
    AuthoringDestinations,
    AuthoringInput,
    AuthoringPage,
    AuthoringResponse,
    AuthoringReview,
    PluralFormOption,
    PluralFormsResponse,
)
from verboflex.services import translation_authoring as service

router = APIRouter(
    prefix="/products/{product_id}/authoring",
    tags=["translation-authoring"],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Permission denied"},
        404: {"description": "Resource unavailable"},
        409: {"description": "Current version or source changed"},
    },
)
Db = Annotated[Session, Depends(get_db_session, use_cache=False)]


@router.get(
    "/destinations", response_model=AuthoringDestinations, operation_id="getAuthoringDestinations"
)
def get_destinations(
    product_id: UUID, principal: CurrentPrincipal, session: Db
) -> AuthoringDestinations:
    try:
        with session.begin():
            return service.destinations(session, product_id=product_id, actor_id=principal.user_id)
    except service.AuthoringError as error:
        raise HTTPException(error.status, str(error)) from error


@router.get(
    "/plural-forms", response_model=PluralFormsResponse, operation_id="getAuthoringPluralForms"
)
def get_plural_forms(
    product_id: UUID,
    principal: CurrentPrincipal,
    session: Db,
    format: Annotated[str, Query(max_length=24)],
    language: Annotated[str, Query(max_length=32)],
) -> PluralFormsResponse:
    from verboflex.localization.plural_forms import plural_forms

    try:
        with session.begin():
            service._product(session, product_id, principal.user_id, "read")
            return PluralFormsResponse(
                profile="Qt 6.10" if format == "qt_ts" else "CLDR 46",
                forms=[
                    PluralFormOption(form=key, label=label)
                    for key, label in plural_forms(format, language)
                ],
            )
    except service.AuthoringError as error:
        raise HTTPException(error.status, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("", response_model=AuthoringPage, operation_id="listAuthoringRequests")
def list_requests(
    product_id: UUID,
    principal: CurrentPrincipal,
    session: Db,
    after: UUID | None = None,
    q: Annotated[str, Query(max_length=256)] = "",
) -> AuthoringPage:
    try:
        with session.begin():
            return service.list_requests(
                session, product_id=product_id, actor_id=principal.user_id, after=after, query=q
            )
    except service.AuthoringError as error:
        raise HTTPException(error.status, str(error)) from error


@router.put("/{request_id}", response_model=AuthoringResponse, operation_id="saveAuthoringRequest")
def save_request(
    product_id: UUID,
    request_id: UUID,
    body: AuthoringInput,
    principal: CurrentPrincipal,
    session: Db,
) -> AuthoringResponse:
    try:
        with session.begin():
            return service.save(
                session,
                product_id=product_id,
                actor_id=principal.user_id,
                request_id=request_id,
                data=body,
            )
    except service.AuthoringError as error:
        raise HTTPException(error.status, str(error)) from error


@router.post(
    "/{request_id}/review", response_model=AuthoringResponse, operation_id="reviewAuthoringRequest"
)
def review_request(
    product_id: UUID,
    request_id: UUID,
    body: AuthoringReview,
    principal: CurrentPrincipal,
    session: Db,
) -> AuthoringResponse:
    try:
        with session.begin():
            result = service.transition(
                session,
                product_id=product_id,
                actor_id=principal.user_id,
                request_id=request_id,
                expected_version=body.expected_version,
                state=body.state,
            )
            assert result is not None
            return result
    except service.AuthoringError as error:
        raise HTTPException(error.status, str(error)) from error


@router.delete("/{request_id}", status_code=204, operation_id="discardAuthoringRequest")
def discard_request(
    product_id: UUID,
    request_id: UUID,
    principal: CurrentPrincipal,
    session: Db,
    expected_version: Annotated[int, Query(ge=1, le=9007199254740991)],
) -> Response:
    try:
        with session.begin():
            service.transition(
                session,
                product_id=product_id,
                actor_id=principal.user_id,
                request_id=request_id,
                expected_version=expected_version,
                state=None,
            )
    except service.AuthoringError as error:
        raise HTTPException(error.status, str(error)) from error
    return Response(status_code=204)
