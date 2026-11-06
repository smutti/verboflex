"""Authorized preview from imported HTML; no repository I/O or active content."""

import re
from html import escape
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from verboflex.auth.principal import CurrentPrincipal
from verboflex.auth.translation_access import (
    TranslationGroupAccessMode,
    TranslationGroupAccessUnavailable,
    TranslationGroupActionDenied,
    resolve_translation_group_access,
)
from verboflex.db.session import get_db_session
from verboflex.localization.html_preview import passive_html_preview
from verboflex.localization.writing.core import WritebackRejected
from verboflex.models.import_job import ImportExecution
from verboflex.models.translation import TranslationValue, TranslationValueLocator
from verboflex.services.branch_workflow import BranchWorkflowError
from verboflex.services.html_editor import (
    HtmlEditorDocument,
    HtmlEditorUnavailable,
    HtmlTemplateCatalog,
    editor_document,
    list_templates,
)
from verboflex.services.html_languages import (
    CreateHtmlLanguage,
    discard_language_job,
    queue_language,
)
from verboflex.services.submission_reviews import (
    SubmissionReviewDenied,
    SubmissionReviewUnavailable,
)

router = APIRouter(
    tags=["html-templates"],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Permission denied"},
        404: {"description": "Resource unavailable"},
        409: {"description": "Source or operation changed"},
    },
)
Db = Annotated[Session, Depends(get_db_session, use_cache=False)]


@router.get(
    "/products/{product_id}/html-templates",
    response_model=HtmlTemplateCatalog,
    operation_id="listHtmlTemplates",
)
def list_html_templates(
    product_id: UUID, principal: CurrentPrincipal, session: Db, after: UUID | None = None
) -> HtmlTemplateCatalog:
    try:
        return list_templates(
            session, product_id=product_id, actor_id=principal.user_id, after=after
        )
    except HtmlEditorUnavailable:
        raise HTTPException(404, "Product unavailable") from None


@router.get(
    "/translations/{translation_group_id}/html-editor",
    response_model=HtmlEditorDocument,
    operation_id="getHtmlEditorDocument",
)
def get_editor_document(
    translation_group_id: UUID, principal: CurrentPrincipal, session: Db
) -> HtmlEditorDocument:
    try:
        access = resolve_translation_group_access(
            session,
            principal=principal,
            translation_group_id=translation_group_id,
            mode=TranslationGroupAccessMode.READ,
        )
        if access.group.is_deleted or len(access.group.values) != 1:
            raise HtmlEditorUnavailable
        return editor_document(
            session,
            group_id=translation_group_id,
            product_id=access.product_id,
            language=access.group.language,
        )
    except HtmlEditorUnavailable, TranslationGroupAccessUnavailable, TranslationGroupActionDenied:
        raise HTTPException(404, "HTML editor unavailable") from None


class HtmlTemplatePreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document: Annotated[str, Field(max_length=2_097_152)]
    marker: str
    path: str
    missing_images: Annotated[int, Field(ge=0)] = 0


@router.get(
    "/translations/{translation_group_id}/html-preview",
    response_model=HtmlTemplatePreviewResponse,
    operation_id="getHtmlTemplatePreview",
)
def get_preview(
    translation_group_id: UUID,
    principal: CurrentPrincipal,
    session: Db,
) -> HtmlTemplatePreviewResponse:
    try:
        access = resolve_translation_group_access(
            session,
            principal=principal,
            translation_group_id=translation_group_id,
            mode=TranslationGroupAccessMode.READ,
        )
    except TranslationGroupAccessUnavailable, TranslationGroupActionDenied:
        raise HTTPException(404, "Translation unavailable") from None
    if len(access.group.values) != 1:
        raise HTTPException(404, "HTML preview unavailable")
    anchor = session.get(TranslationValueLocator, access.group.values[0].id)
    if anchor is None or anchor.format != "html":
        raise HTTPException(404, "HTML preview unavailable")
    rows = session.execute(
        select(TranslationValue, TranslationValueLocator)
        .join(TranslationValueLocator, TranslationValueLocator.value_id == TranslationValue.id)
        .where(
            TranslationValueLocator.import_execution_id == anchor.import_execution_id,
            TranslationValueLocator.repository_id == anchor.repository_id,
            TranslationValueLocator.repository_side == anchor.repository_side,
            TranslationValueLocator.path == anchor.path,
            TranslationValue.is_deleted.is_(False),
        )
        .order_by(TranslationValueLocator.position)
        .limit(5001)
    ).all()
    skeleton = None
    for value, _ in rows:
        for node in value.structure:
            if isinstance(node, dict) and node.get("kind") == "html:document":
                for field in node.get("fields", []):
                    if isinstance(field, dict) and field.get("name") == "skeleton":
                        skeleton = field.get("value")
    if not isinstance(skeleton, str) or len(rows) > 5000:
        raise HTTPException(404, "Reimport this template to enable its preview")
    texts = {
        str(locator.position): escape(
            value.translated_text if value.translated_text is not None else value.source_text or "",
            quote=False,
        )
        for value, locator in rows
    }
    marker = "<!--VERBOFLEX-SELECTED-TEXT-->"
    texts[str(anchor.position)] = marker
    document = re.sub(
        r"<!--VERBOFLEX-TEXT:(\d+)-->",
        lambda match: texts.get(match[1], ""),
        skeleton,
    )
    execution = session.get(ImportExecution, anchor.import_execution_id)
    images = (
        (execution.html_preview_images or {}).get(anchor.repository_side, {}) if execution else {}
    )
    preview = passive_html_preview(document, template_path=anchor.path, images=images)
    return HtmlTemplatePreviewResponse(
        document=preview.document,
        marker=marker,
        path=anchor.path,
        missing_images=preview.missing_images,
    )


class HtmlLanguageJobResponse(BaseModel):
    id: UUID
    state: str


@router.post(
    "/products/{product_id}/html-languages",
    response_model=HtmlLanguageJobResponse,
    operation_id="createHtmlLanguage",
    status_code=202,
)
def create_language(
    product_id: UUID, body: CreateHtmlLanguage, principal: CurrentPrincipal, session: Db
) -> HtmlLanguageJobResponse:
    try:
        with session.begin():
            job = queue_language(
                session, product_id=product_id, actor_id=principal.user_id, body=body
            )
            return HtmlLanguageJobResponse(id=job.id, state=job.state)
    except SubmissionReviewUnavailable:
        raise HTTPException(404, "Product unavailable") from None
    except SubmissionReviewDenied:
        raise HTTPException(403, "Action not permitted") from None
    except (BranchWorkflowError, WritebackRejected) as error:
        raise HTTPException(409, str(error)) from None


@router.delete(
    "/products/{product_id}/html-languages/{job_id}",
    response_model=HtmlLanguageJobResponse,
    operation_id="discardHtmlLanguage",
)
def discard_language(
    product_id: UUID, job_id: UUID, principal: CurrentPrincipal, session: Db
) -> HtmlLanguageJobResponse:
    try:
        with session.begin():
            discard_language_job(
                session, product_id=product_id, actor_id=principal.user_id, job_id=job_id
            )
        return HtmlLanguageJobResponse(id=job_id, state="declined")
    except SubmissionReviewUnavailable:
        raise HTTPException(404, "Product unavailable") from None
    except SubmissionReviewDenied:
        raise HTTPException(403, "Action not permitted") from None
    except BranchWorkflowError as error:
        raise HTTPException(409, str(error)) from None
