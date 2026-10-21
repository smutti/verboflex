"""Authenticated code context and durable capture operations, with no build I/O."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from verboflex.auth.principal import CurrentPrincipal
from verboflex.core.config import Settings, get_settings
from verboflex.db.session import get_db_session
from verboflex.models.screenshot import ScreenshotJob
from verboflex.schemas.screenshots import (
    CodeCatalogPage,
    CodeContextResponse,
    CodeSourcePage,
    ScreenshotPage,
    ScreenshotRequest,
    ScreenshotResponse,
)
from verboflex.schemas.system import ErrorResponse
from verboflex.services import screenshots as service

router = APIRouter(
    tags=["screenshots"],
    responses={
        **{code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 429, 503)},
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


def _error(error: service.ScreenshotError) -> HTTPException:
    return HTTPException(
        error.status, str(error), headers={"Retry-After": "60"} if error.status == 429 else None
    )


@router.get(
    "/products/{product_id}/code-sources",
    response_model=CodeSourcePage,
    operation_id="listProductCodeSources",
)
def code_sources(
    product_id: UUID, principal: CurrentPrincipal, session: Db, after: UUID | None = None
) -> CodeSourcePage:
    try:
        with session.begin():
            return service.code_sources(session, principal, product_id, after)
    except service.ScreenshotError as error:
        raise _error(error) from error


@router.get(
    "/translations/{group_id}/code-context",
    response_model=CodeContextResponse,
    operation_id="getTranslationCodeContext",
)
def code_context(group_id: UUID, principal: CurrentPrincipal, session: Db) -> CodeContextResponse:
    try:
        with session.begin():
            return service.context(session, principal, group_id)
    except service.ScreenshotError as error:
        raise _error(error) from error


@router.get(
    "/localization-scopes/{scope_id}/code-keys",
    response_model=CodeCatalogPage,
    operation_id="listCodeKeys",
)
def code_keys(
    scope_id: UUID,
    principal: CurrentPrincipal,
    session: Db,
    after: Annotated[str | None, Query(max_length=4096)] = None,
) -> CodeCatalogPage:
    try:
        with session.begin():
            return service.catalog_page(session, principal, scope_id, after)
    except service.ScreenshotError as error:
        raise _error(error) from error


@router.put(
    "/translations/{group_id}/screenshots/{job_id}",
    status_code=202,
    response_model=ScreenshotResponse,
    operation_id="requestTranslationScreenshot",
)
def request_screenshot(
    group_id: UUID,
    job_id: UUID,
    body: ScreenshotRequest,
    principal: CurrentPrincipal,
    session: Db,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ScreenshotResponse:
    try:
        with session.begin():
            row = service.request_capture(
                session,
                principal,
                group_id,
                job_id,
                body,
                runner_enabled=bool(settings.screenshot_runner_command),
            )
            response = ScreenshotResponse.model_validate(row)
    except service.ScreenshotError as error:
        raise _error(error) from error
    # The worker must see the committed snapshot, even if it starts immediately.
    # Retrying a queued request may resend its UUID; the worker claims it once.
    if response.state == "queued":
        service.enqueue_capture(response.id)
    return response


@router.get(
    "/translations/{group_id}/screenshots",
    response_model=ScreenshotPage,
    operation_id="listTranslationScreenshots",
)
def screenshots(
    group_id: UUID, principal: CurrentPrincipal, session: Db, after: UUID | None = None
) -> ScreenshotPage:
    try:
        with session.begin():
            service._group(session, principal, group_id)
            statement = select(ScreenshotJob.id).where(
                ScreenshotJob.group_id == group_id,
                ScreenshotJob.actor_id == principal.user_id,
            )
            if after is not None:
                cursor = session.get(ScreenshotJob, after)
                if (
                    cursor is None
                    or cursor.group_id != group_id
                    or cursor.actor_id != principal.user_id
                ):
                    raise service.ScreenshotError("Invalid screenshot cursor")
                statement = statement.where(
                    or_(
                        ScreenshotJob.created_at < cursor.created_at,
                        and_(
                            ScreenshotJob.created_at == cursor.created_at, ScreenshotJob.id < after
                        ),
                    )
                )
            ids = list(
                session.scalars(
                    statement.order_by(
                        ScreenshotJob.created_at.desc(), ScreenshotJob.id.desc()
                    ).limit(21)
                )
            )
            return ScreenshotPage(
                items=[
                    ScreenshotResponse.model_validate(
                        service.get_capture(session, principal, group_id, job_id)
                    )
                    for job_id in ids[:20]
                ],
                next_cursor=ids[19] if len(ids) > 20 else None,
            )
    except service.ScreenshotError as error:
        raise _error(error) from error


@router.get(
    "/translations/{group_id}/screenshots/{job_id}",
    response_model=ScreenshotResponse,
    operation_id="getTranslationScreenshot",
)
def screenshot(
    group_id: UUID, job_id: UUID, principal: CurrentPrincipal, session: Db
) -> ScreenshotResponse:
    try:
        with session.begin():
            return ScreenshotResponse.model_validate(
                service.get_capture(session, principal, group_id, job_id)
            )
    except service.ScreenshotError as error:
        raise _error(error) from error


@router.delete(
    "/translations/{group_id}/screenshots/{job_id}",
    response_model=ScreenshotResponse,
    operation_id="cancelTranslationScreenshot",
)
def cancel(
    group_id: UUID, job_id: UUID, principal: CurrentPrincipal, session: Db
) -> ScreenshotResponse:
    try:
        with session.begin():
            row = service.get_capture(session, principal, group_id, job_id)
            if row.actor_id != principal.user_id:
                raise service.ScreenshotError("Screenshot cancellation denied", 403)
            if row.state in service.ACTIVE_STATES:
                row.state = "cancelled"
            return ScreenshotResponse.model_validate(row)
    except service.ScreenshotError as error:
        raise _error(error) from error


@router.get(
    "/translations/{group_id}/screenshots/{job_id}/image",
    operation_id="getTranslationScreenshotImage",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def screenshot_image(
    group_id: UUID, job_id: UUID, principal: CurrentPrincipal, session: Db
) -> Response:
    try:
        with session.begin():
            row = service.get_capture(session, principal, group_id, job_id)
            if row.state != "succeeded" or row.image is None:
                raise service.ScreenshotError("Screenshot image unavailable", 404)
            return Response(
                row.image,
                media_type="image/png",
                headers={
                    "Cache-Control": "private, no-store",
                    "X-Content-Type-Options": "nosniff",
                    "Content-Disposition": 'inline; filename="preview.png"',
                },
            )
    except service.ScreenshotError as error:
        raise _error(error) from error
