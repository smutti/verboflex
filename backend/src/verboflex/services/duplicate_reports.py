"""Persist once under worker authority; paginate stored diagnostics without provider reads."""

import base64
import binascii
import json
from dataclasses import asdict
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import exists, insert, select
from sqlalchemy.orm import Session

from verboflex.localization.duplicate_diagnostics import MAX_DIAGNOSTIC_BYTES, DuplicateReport
from verboflex.models.duplicate_report import (
    DuplicateGroupRow,
    DuplicateOccurrenceRow,
    DuplicateReportRow,
)
from verboflex.schemas.duplicate_reports import (
    DuplicateGroupResponse,
    DuplicateOccurrenceResponse,
    DuplicateReportResponse,
    DuplicateSourceResponse,
)


def store_report(
    session: Session,
    *,
    report: DuplicateReport,
    sources: list[dict[str, str]],
    preview_job_id: UUID | None = None,
    execution_id: UUID | None = None,
) -> None:
    """Caller holds the exact running owner's lock in the same transaction."""
    owner = (
        DuplicateReportRow.preview_job_id == preview_job_id
        if preview_job_id
        else DuplicateReportRow.execution_id == execution_id
    )
    if session.scalar(select(DuplicateReportRow.id).where(owner)) is not None:
        return
    if (
        sum(len(group.occurrences) for group in report.groups) > 50_000
        or len(json.dumps([asdict(report), sources], ensure_ascii=True).encode())
        > MAX_DIAGNOSTIC_BYTES
    ):
        report = DuplicateReport(complete=False, issue_codes=("unsupported_structure",))
    report_id = uuid4()
    session.add(
        DuplicateReportRow(
            id=report_id,
            preview_job_id=preview_job_id,
            execution_id=execution_id,
            complete=report.complete,
            issue_codes=list(report.issue_codes),
            group_count=len(report.groups),
            repeated_occurrences=report.repeated_occurrences,
            sources=sources,
        )
    )
    session.flush()
    batch: list[dict[str, object]] = []
    for position, group in enumerate(report.groups):
        session.add(
            DuplicateGroupRow(
                report_id=report_id,
                position=position,
                identity_digest=group.id,
                repository_side=group.repository_side,
                layout_identity=group.layout_identity,
                language=group.language,
                key_preview=group.key_preview,
                key_length=group.key_length,
                occurrence_count=len(group.occurrences),
            )
        )
        for ordinal, occurrence in enumerate(group.occurrences):
            batch.append(
                dict(
                    report_id=report_id,
                    group_position=position,
                    position=ordinal,
                    path=occurrence.path,
                    resource_position=occurrence.position,
                )
            )
            if len(batch) == 500:
                session.execute(insert(DuplicateOccurrenceRow), batch)
                session.flush()
                batch.clear()
    if batch:
        session.execute(insert(DuplicateOccurrenceRow), batch)


def _cursor(binding: list[object], position: int) -> str:
    return (
        base64.urlsafe_b64encode(
            json.dumps([binding, position], separators=(",", ":"), ensure_ascii=True).encode()
        )
        .decode()
        .rstrip("=")
    )


def _position(cursor: str | None, binding: list[object]) -> int:
    if cursor is None:
        return -1
    try:
        if len(cursor) > 16384:
            raise ValueError
        value = json.loads(
            base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        )
        if (
            type(value) is not list
            or len(value) != 2
            or value[0] != binding
            or type(value[1]) is not int
            or not 0 <= value[1] <= 50000
            or _cursor(binding, value[1]) != cursor
        ):
            raise ValueError
        return value[1]
    except ValueError, TypeError, binascii.Error, UnicodeDecodeError:
        raise HTTPException(422, "Invalid duplicate report cursor") from None


def read_report(
    session: Session,
    *,
    row: DuplicateReportRow,
    execution: int,
    limit: int,
    language: str | None,
    file: str | None,
    group_id: str | None,
    cursor: str | None,
) -> DuplicateReportResponse:
    binding: list[object] = [str(row.id), execution, language, file, group_id]
    after = _position(cursor, binding)
    statement = select(DuplicateGroupRow).where(DuplicateGroupRow.report_id == row.id)
    if language is not None:
        statement = statement.where(DuplicateGroupRow.language == language)
    if file is not None:
        statement = statement.where(
            exists(
                select(DuplicateOccurrenceRow.position).where(
                    DuplicateOccurrenceRow.report_id == row.id,
                    DuplicateOccurrenceRow.group_position == DuplicateGroupRow.position,
                    DuplicateOccurrenceRow.path == file,
                )
            )
        )
    if group_id is not None:
        statement = statement.where(DuplicateGroupRow.identity_digest == group_id)
    else:
        statement = statement.where(DuplicateGroupRow.position > after)
    groups = list(session.scalars(statement.order_by(DuplicateGroupRow.position).limit(limit + 1)))
    if group_id is not None and not groups:
        raise HTTPException(404, "Duplicate group unavailable")
    items: list[DuplicateGroupResponse] = []
    encoded_size = 0
    more = len(groups) > limit
    for group in groups[:limit]:
        # At most 20 occurrences per group; all remaining positions are addressable
        # through the same authority-bound resource using group_id and its cursor.
        occurrence_after = after if group_id is not None else -1
        occurrences = list(
            session.scalars(
                select(DuplicateOccurrenceRow)
                .where(
                    DuplicateOccurrenceRow.report_id == row.id,
                    DuplicateOccurrenceRow.group_position == group.position,
                    DuplicateOccurrenceRow.position > occurrence_after,
                )
                .order_by(DuplicateOccurrenceRow.position)
                .limit(21)
            )
        )
        occurrence_binding: list[object] = [
            str(row.id),
            execution,
            language,
            file,
            group.identity_digest,
        ]
        item = DuplicateGroupResponse(
            id=group.identity_digest,
            repository_side=group.repository_side,
            language=group.language,
            key_preview=group.key_preview,
            key_length=group.key_length,
            occurrence_count=group.occurrence_count,
            occurrences=[
                DuplicateOccurrenceResponse(path=o.path, resource_position=o.resource_position)
                for o in occurrences[:20]
            ],
            next_occurrence_cursor=_cursor(occurrence_binding, occurrences[19].position)
            if len(occurrences) > 20
            else None,
        )
        size = len(item.model_dump_json().encode())
        if items and encoded_size + size > 512 * 1024:
            more = True
            break
        items.append(item)
        encoded_size += size
    next_cursor = (
        _cursor(binding, groups[len(items) - 1].position)
        if more and items and group_id is None
        else None
    )
    return DuplicateReportResponse(
        report_id=row.id,
        execution=execution,
        complete=row.complete,
        issue_codes=row.issue_codes,
        group_count=row.group_count,
        repeated_occurrences=row.repeated_occurrences,
        sources=[DuplicateSourceResponse.model_validate(source) for source in row.sources],
        items=items,
        next_cursor=next_cursor,
    )
