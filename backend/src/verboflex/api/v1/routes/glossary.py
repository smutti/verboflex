"""Project glossary administration and read-only term matching."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response

from verboflex.api.v1.routes.authoring import Db
from verboflex.auth.principal import CurrentPrincipal
from verboflex.schemas.glossary import (
    GlossaryInput,
    GlossaryMatches,
    GlossaryMatchQuery,
    GlossaryPage,
    GlossaryResponse,
)
from verboflex.services import glossary as service
from verboflex.services.translation_authoring import AuthoringError

router = APIRouter(
    prefix="/products/{product_id}/glossary",
    tags=["glossary"],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Permission denied"},
        404: {"description": "Resource unavailable"},
        409: {"description": "Current version changed"},
    },
)


@router.get("", response_model=GlossaryPage, operation_id="listGlossaryTerms")
def list_terms(
    product_id: UUID,
    principal: CurrentPrincipal,
    session: Db,
    after: UUID | None = None,
    q: Annotated[str, Query(max_length=256)] = "",
) -> GlossaryPage:
    try:
        with session.begin():
            return service.list_entries(
                session, product_id=product_id, actor_id=principal.user_id, after=after, query=q
            )
    except AuthoringError as error:
        raise HTTPException(error.status, str(error)) from error


@router.put("/{entry_id}", response_model=GlossaryResponse, operation_id="saveGlossaryTerm")
def save_term(
    product_id: UUID, entry_id: UUID, body: GlossaryInput, principal: CurrentPrincipal, session: Db
) -> GlossaryResponse:
    try:
        with session.begin():
            return service.save(
                session,
                product_id=product_id,
                actor_id=principal.user_id,
                entry_id=entry_id,
                data=body,
            )
    except AuthoringError as error:
        raise HTTPException(error.status, str(error)) from error


@router.delete("/{entry_id}", status_code=204, operation_id="deleteGlossaryTerm")
def delete_term(
    product_id: UUID,
    entry_id: UUID,
    principal: CurrentPrincipal,
    session: Db,
    expected_version: Annotated[int, Query(ge=1, le=9007199254740991)],
) -> Response:
    try:
        with session.begin():
            service.delete(
                session,
                product_id=product_id,
                actor_id=principal.user_id,
                entry_id=entry_id,
                expected_version=expected_version,
            )
    except AuthoringError as error:
        raise HTTPException(error.status, str(error)) from error
    return Response(status_code=204)


@router.post("/matches", response_model=GlossaryMatches, operation_id="matchGlossaryTerms")
def match_terms(
    product_id: UUID, body: GlossaryMatchQuery, principal: CurrentPrincipal, session: Db
) -> GlossaryMatches:
    try:
        with session.begin():
            return service.matches(
                session, product_id=product_id, actor_id=principal.user_id, query=body
            )
    except AuthoringError as error:
        raise HTTPException(error.status, str(error)) from error
