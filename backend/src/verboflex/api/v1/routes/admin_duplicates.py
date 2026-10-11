"""Admin-only stored diagnostic reads, fenced by exact job/execution ownership."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from verboflex.api.v1.routes.admin_previews import RESPONSES, AdminPrincipal, AdminSession
from verboflex.models.duplicate_report import DuplicateReportRow
from verboflex.models.import_job import ImportExecution, ImportJob
from verboflex.models.preview_job import PreviewJob
from verboflex.models.product import Product
from verboflex.schemas.duplicate_reports import DuplicateReportResponse
from verboflex.services.duplicate_reports import read_report

router = APIRouter(tags=["admin-duplicates"])
Limit = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query(max_length=16384)]
Language = Annotated[str | None, Query(max_length=64)]
File = Annotated[str | None, Query(max_length=4096)]
Group = Annotated[str | None, Query(pattern="^[a-f0-9]{64}$")]


@router.get(
    "/admin/preview-jobs/{job_id}/duplicates",
    operation_id="get_admin_preview_duplicates",
    response_model=DuplicateReportResponse,
    responses=RESPONSES,
)
def preview_duplicates(
    job_id: UUID,
    _principal: AdminPrincipal,
    session: AdminSession,
    limit: Limit = 50,
    cursor: Cursor = None,
    language: Language = None,
    file: File = None,
    group_id: Group = None,
) -> DuplicateReportResponse:
    job = session.get(PreviewJob, job_id)
    product = session.get(Product, job.product_id) if job is not None else None
    if job is None or product is None or product.deleted_at is not None:
        raise HTTPException(404, "Preview unavailable")
    if job.state in {"queued", "running"}:
        raise HTTPException(409, "Duplicate report is not finished")
    row = session.scalar(
        select(DuplicateReportRow).where(DuplicateReportRow.preview_job_id == job_id)
    )
    if row is None:
        raise HTTPException(404, "Duplicate report unavailable")
    return read_report(
        session,
        row=row,
        execution=job.attempt,
        limit=limit,
        cursor=cursor,
        language=language,
        file=file,
        group_id=group_id,
    )


@router.get(
    "/admin/products/{product_id}/imports/{import_id}/duplicates",
    operation_id="get_admin_import_duplicates",
    response_model=DuplicateReportResponse,
    responses=RESPONSES,
)
def import_duplicates(
    product_id: UUID,
    import_id: UUID,
    execution: Annotated[int, Query(ge=1)],
    _principal: AdminPrincipal,
    session: AdminSession,
    limit: Limit = 50,
    cursor: Cursor = None,
    language: Language = None,
    file: File = None,
    group_id: Group = None,
) -> DuplicateReportResponse:
    owner = session.scalar(
        select(ImportExecution)
        .join(ImportJob, ImportJob.id == ImportExecution.import_job_id)
        .join(Product, Product.id == ImportJob.product_id)
        .where(
            ImportJob.product_id == product_id,
            Product.deleted_at.is_(None),
            ImportJob.id == import_id,
            ImportExecution.sequence == execution,
        )
    )
    if owner is None:
        raise HTTPException(404, "Import execution unavailable")
    if owner.state in {"queued", "running"}:
        raise HTTPException(409, "Duplicate report is not finished")
    row = session.scalar(
        select(DuplicateReportRow).where(DuplicateReportRow.execution_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Duplicate report unavailable")
    return read_report(
        session,
        row=row,
        execution=execution,
        limit=limit,
        cursor=cursor,
        language=language,
        file=file,
        group_id=group_id,
    )
