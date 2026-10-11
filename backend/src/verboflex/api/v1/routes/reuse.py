"""Read-only translation suggestions, shared by browser and MCP clients."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from verboflex.api.v1.routes.authoring import Db
from verboflex.auth.principal import CurrentPrincipal
from verboflex.schemas.reuse import ReusePage, ReuseQuery, ReuseResolve, ReuseSuggestion
from verboflex.services.translation_authoring import AuthoringError
from verboflex.services.translation_reuse import resolve, suggest

router = APIRouter(
    prefix="/products/{product_id}/reuse",
    tags=["translation-reuse"],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Permission denied"},
        404: {"description": "Resource unavailable"},
        409: {"description": "Suggestion changed"},
        503: {"description": "Lookup unavailable"},
    },
)


@router.post("/suggestions", response_model=ReusePage, operation_id="getTranslationSuggestions")
def suggestions(
    product_id: UUID, body: ReuseQuery, principal: CurrentPrincipal, session: Db
) -> ReusePage:
    try:
        with session.begin():
            return suggest(session, product_id=product_id, actor_id=principal.user_id, query=body)
    except AuthoringError as error:
        raise HTTPException(error.status, str(error)) from error


@router.post(
    "/resolve", response_model=ReuseSuggestion, operation_id="resolveTranslationSuggestion"
)
def resolve_suggestion(
    product_id: UUID, body: ReuseResolve, principal: CurrentPrincipal, session: Db
) -> ReuseSuggestion:
    try:
        with session.begin():
            return resolve(session, product_id=product_id, actor_id=principal.user_id, data=body)
    except AuthoringError as error:
        raise HTTPException(error.status, str(error)) from error
