"""Current mapped-file authority for explicit, versioned structural proposals."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from verboflex.audit.ledger import record_audit
from verboflex.auth.product_access import product_roles
from verboflex.localization.graphemes import grapheme_count
from verboflex.localization.importing.android_xml import _confirmed_language
from verboflex.localization.importing.core import (
    CanonicalParserInput,
    CanonicalSelector,
    canonical_selector_bytes,
)
from verboflex.localization.plural_forms import plural_forms
from verboflex.localization.preview.core import (
    PreviewLayoutCandidate,
    extract_preview_locale_path,
    normalize_preview_locale,
)
from verboflex.localization.writing.core import SourceFileAuthority, WritebackRejected, WriteInsert
from verboflex.models.authoring import AuthoringRequest
from verboflex.models.import_job import ImportExecution
from verboflex.models.product import Product
from verboflex.models.repository import Repository
from verboflex.models.translation import (
    LocalizationScope,
    TranslationKey,
    TranslationValue,
    TranslationValueLocator,
)
from verboflex.models.translation_constraint import TranslationConstraint
from verboflex.schemas.authoring import (
    AuthoringDestination,
    AuthoringDestinations,
    AuthoringInput,
    AuthoringPage,
    AuthoringResponse,
)
from verboflex.services.import_jobs import confirmed_file_parser_input
from verboflex.services.translation_constraints import (
    project_effective_constraint,
    recompute_translation_constraints,
)
from verboflex.services.writeback_authority import CapturedMapping, _capture_mapping


class AuthoringError(ValueError):
    def __init__(self, detail: str, status: int = 422) -> None:
        super().__init__(detail)
        self.status = status


def _product(session: Session, product_id: UUID, actor_id: UUID, action: str) -> Product:
    product = session.scalar(
        select(Product).where(Product.id == product_id).with_for_update(read=action == "read")
    )
    if (
        product is None
        or not product.is_active
        or product.deleted_at is not None
        or product.active_revision_id is None
    ):
        raise AuthoringError("Product unavailable", 404)
    allowed = {"admin", "product_manager_reviewer", "translator", "viewer"}
    if action == "write":
        allowed.remove("viewer")
    if action == "review":
        allowed = {"admin", "product_manager_reviewer"}
    if not allowed.intersection(product_roles(session, actor_id, product_id)):
        raise AuthoringError("Authoring action denied", 403)
    return product


def _scope(session: Session, product: Product, scope_id: UUID) -> LocalizationScope:
    scope = session.scalar(
        select(LocalizationScope)
        .where(
            LocalizationScope.id == scope_id,
            LocalizationScope.product_id == product.id,
            LocalizationScope.current_revision_id == product.active_revision_id,
        )
        .with_for_update()
    )
    if scope is None or scope.active_execution_id is None:
        raise AuthoringError("Translation source unavailable", 404)
    return scope


def _mapping(
    session: Session, scope: LocalizationScope
) -> tuple[CapturedMapping, tuple[PreviewLayoutCandidate, ...]]:
    try:
        return _capture_mapping(
            session, scope, reference_limit=500, byte_limit=20971520, require_write_provider=False
        )
    except WritebackRejected:
        raise AuthoringError("Refresh the translation source before adding keys", 409) from None


def file_languages(parser: CanonicalParserInput, scope: LocalizationScope) -> list[str]:
    if parser.format == "android_xml":
        try:
            return [_confirmed_language(parser)]
        except ValueError:
            return []
    if parser.format == "ios_strings":
        values = [p[:-6] for p in parser.path.split("/") if p.endswith(".lproj")]
        return [
            value
            for p in values
            if (value := normalize_preview_locale(parser.base_language if p == "Base" else p))
        ]
    if parser.format == "json" and parser.layout_identity.startswith("json:locale-rooted:"):
        return sorted(scope.language_counts)[:500]
    suffix = ".ts" if parser.format == "qt_ts" else ".json"
    found = extract_preview_locale_path(
        parser.path, suffix=suffix, allow_prefixed_stem=parser.format == "qt_ts"
    )
    return [found[0]] if found else []


def destinations(session: Session, *, product_id: UUID, actor_id: UUID) -> AuthoringDestinations:
    product = _product(session, product_id, actor_id, "read")
    scopes = session.scalars(
        select(LocalizationScope)
        .where(
            LocalizationScope.product_id == product.id,
            LocalizationScope.current_revision_id == product.active_revision_id,
            LocalizationScope.active_execution_id.is_not(None),
        )
        .order_by(LocalizationScope.id)
        .limit(101)
    ).all()
    result = []
    for scope in scopes[:100]:
        try:
            mapping, layouts = _mapping(session, scope)
        except AuthoringError:
            continue
        for ref in mapping.source_references:
            if ref.repository_side == "keys":
                continue
            parser = confirmed_file_parser_input(
                layouts,
                repository_side=ref.repository_side,
                path=ref.path,
                content=b"",
                base_language=mapping.base_language,
            )
            if parser is None or parser.format == "xliff":
                continue
            repository = session.get(Repository, ref.repository_id)
            assert repository is not None
            result.append(
                AuthoringDestination(
                    scope_id=scope.id,
                    execution_id=mapping.execution_id,
                    file_position=ref.source_reference_position,
                    path=ref.path,
                    format=parser.format,
                    repository=f"{repository.workspace}/{repository.repository_slug}",
                    provider=repository.provider,
                    repository_side=ref.repository_side,
                    base_language=mapping.base_language,
                    languages=file_languages(parser, scope),
                    topology=mapping.topology,
                )
            )
            if len(result) == 500:
                return AuthoringDestinations(items=result, truncated=True)
    return AuthoringDestinations(items=result, truncated=len(scopes) > 100)


def resolve_file(
    session: Session, scope: LocalizationScope, data: AuthoringInput
) -> tuple[CapturedMapping, SourceFileAuthority, CanonicalParserInput]:
    mapping, layouts = _mapping(session, scope)
    if mapping.execution_id != data.execution_id:
        raise AuthoringError("Source changed. Refresh and review the destination", 409)
    refs = [
        ref
        for ref in mapping.source_references
        if ref.source_reference_position == data.file_position
    ]
    if len(refs) != 1 or refs[0].repository_side == "keys":
        raise AuthoringError("Destination unavailable", 404)
    ref = refs[0]
    if mapping.topology == "separate" and data.parent_key_id is None:
        from verboflex.localization.code_keys.catalog import CodeKeyCatalog

        execution = session.get_one(ImportExecution, scope.active_execution_id)
        catalog = execution.code_catalog
        if (
            catalog is None
            or data.key not in CodeKeyCatalog.model_validate(catalog["catalog"]).keys
        ):
            raise AuthoringError("Create the source key in the keys repository, then refresh")
    parser = confirmed_file_parser_input(
        layouts,
        repository_side=ref.repository_side,
        path=ref.path,
        content=b"",
        base_language=mapping.base_language,
    )
    if (
        parser is None
        or parser.format not in {"android_xml", "json", "qt_ts", "ios_strings"}
        or data.language not in file_languages(parser, scope)
    ):
        raise AuthoringError("Language does not match the selected file")
    return mapping, ref, parser


def operations(data: AuthoringInput, format: str) -> tuple[WriteInsert, ...]:
    values = []
    for form in data.forms:
        if format == "json":
            if data.kind != "text":
                raise AuthoringError("Choose a configured plural format")
            selector = CanonicalSelector("json_path", (("parents", tuple(data.parents)),))
        elif format == "qt_ts":
            fields: list[tuple[str, str | int]] = [("identity_kind", data.identity_kind)]
            if not data.context or not data.source_text:
                raise AuthoringError("Source text and context are required")
            if data.identity_kind == "source":
                if data.key != data.source_text:
                    raise AuthoringError("This Qt key must match its source text")
                fields.append(("context", data.context))
                if data.disambiguation:
                    fields.append(("disambiguation", data.disambiguation))
            if data.kind == "plural":
                if form.form not in {"0", "1", "2", "3", "4", "5"}:
                    raise AuthoringError("Invalid Qt plural form")
                fields.append(("form_index", int(form.form)))
            selector = CanonicalSelector(
                "qt_numerus" if data.kind == "plural" else "scalar", tuple(fields)
            )
        elif format == "android_xml" and data.kind == "plural":
            if form.form not in {"zero", "one", "two", "few", "many", "other"}:
                raise AuthoringError("Invalid Android plural form")
            selector = CanonicalSelector("android_quantity", (("quantity", form.form),))
        elif format in {"android_xml", "ios_strings"} and data.kind == "text":
            selector = CanonicalSelector("scalar", ())
        else:
            raise AuthoringError("Plural authoring is unavailable for this format")
        if format == "android_xml":
            import re

            if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_.]*", data.key):
                raise AuthoringError("Invalid Android resource name")
        values.append(
            WriteInsert(
                data.key, data.language, selector, form.text, data.source_text, data.context
            )
        )
    return tuple(values)


def _existing(
    session: Session,
    scope: LocalizationScope,
    ref: SourceFileAuthority,
    data: AuthoringInput,
    ops: tuple[WriteInsert, ...],
) -> None:
    key = session.scalar(
        select(TranslationKey).where(
            TranslationKey.scope_id == scope.id,
            TranslationKey.repository_id == ref.repository_id,
            TranslationKey.configured_branch == ref.configured_branch,
            TranslationKey.raw_key_digest == hashlib.sha256(data.key.encode()).digest(),
            TranslationKey.raw_key == data.key,
            TranslationKey.is_deleted.is_(False),
        )
    )
    if data.parent_key_id is not None:
        parent = session.get(TranslationKey, data.parent_key_id)
        if (
            parent is None
            or parent.scope_id != scope.id
            or parent.raw_key != data.key
            or parent.repository_id != ref.repository_id
            or parent.configured_branch != ref.configured_branch
            or parent.is_deleted
        ):
            raise AuthoringError("Original key unavailable", 404)
    if key is not None:
        if data.parent_key_id is None:
            raise AuthoringError("Key already exists. Add a language or edit it", 409)
        selectors = {hashlib.sha256(canonical_selector_bytes(o.selector)).hexdigest() for o in ops}
        found = session.scalar(
            select(TranslationValue.id)
            .where(
                TranslationValue.translation_key_id == key.id,
                TranslationValue.language == data.language,
                TranslationValue.selector_digest.in_(selectors),
                TranslationValue.is_deleted.is_(False),
            )
            .limit(1)
        )
        if found is not None:
            raise AuthoringError("Translation already exists. Refresh and edit it", 409)


def response(row: AuthoringRequest, scope: LocalizationScope) -> AuthoringResponse:
    data = AuthoringInput.model_validate(row.payload["input"])
    return AuthoringResponse(
        id=row.id,
        version=row.version,
        state=cast(Literal["draft", "approved", "rejected"], row.state),
        input=data.model_copy(update={"expected_version": row.version}),
        path=str(row.payload["path"]),
        format=str(row.payload["format"]),
        source_changed=data.execution_id != scope.active_execution_id,
        updated_at=row.updated_at,
    )


def save(
    session: Session, *, product_id: UUID, actor_id: UUID, request_id: UUID, data: AuthoringInput
) -> AuthoringResponse:
    product = _product(session, product_id, actor_id, "write")
    scope = _scope(session, product, data.scope_id)
    _, ref, parser = resolve_file(session, scope, data)
    ops = operations(data, parser.format)
    _existing(session, scope, ref, data, ops)
    # Family identity includes the destination and selector shape, never proposed text.
    identity = hashlib.sha256(
        json.dumps(
            [
                str(scope.id),
                str(data.parent_key_id),
                ref.path,
                data.key,
                data.language,
                data.context,
                data.disambiguation,
                data.identity_kind,
                data.parents,
            ],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    row = session.get(AuthoringRequest, request_id, with_for_update=True)
    payload: dict[str, object] = {
        "input": data.model_dump(mode="json", exclude={"expected_version"}),
        "path": ref.path,
        "sha256": ref.sha256,
        "repository_id": str(ref.repository_id),
        "configured_branch": ref.configured_branch,
        "format": parser.format,
    }
    if row is not None:
        if row.scope_id != scope.id or row.identity_digest != identity:
            raise AuthoringError("Authoring request unavailable", 404)
        if row.version != data.expected_version:
            if (
                row.version == data.expected_version + 1
                and row.payload == payload
                and row.updated_by == actor_id
                and row.state == "draft"
            ):
                return response(row, scope)
            raise AuthoringError("This draft changed. Reload before saving", 409)
        row.version += 1
        row.state, row.payload, row.updated_by = "draft", payload, actor_id
        row.updated_at = datetime.now(UTC)
    else:
        from verboflex.models.review import TranslationProposal

        if session.get(TranslationProposal, request_id) is not None:
            raise AuthoringError("Request identifier is already in use", 409)
        if data.expected_version != 0:
            raise AuthoringError("Draft no longer exists", 409)
        duplicate = session.scalar(
            select(AuthoringRequest.id).where(
                AuthoringRequest.scope_id == scope.id, AuthoringRequest.identity_digest == identity
            )
        )
        if duplicate:
            raise AuthoringError("A draft already exists for this key and language", 409)
        row = AuthoringRequest(
            id=request_id,
            scope_id=scope.id,
            parent_key_id=data.parent_key_id,
            raw_key=data.key,
            language=data.language,
            identity_digest=identity,
            version=1,
            state="draft",
            payload=payload,
            created_by=actor_id,
            updated_by=actor_id,
        )
        session.add(row)
    record_audit(session, actor_id=actor_id, action="authoring.saved", entity_id=row.id)
    session.flush()
    return response(row, scope)


def list_requests(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    after: UUID | None = None,
    query: str = "",
) -> AuthoringPage:
    product = _product(session, product_id, actor_id, "read")
    statement = (
        select(AuthoringRequest, LocalizationScope)
        .join(LocalizationScope)
        .where(
            LocalizationScope.product_id == product.id,
            LocalizationScope.current_revision_id == product.active_revision_id,
        )
    )
    if after is not None:
        statement = statement.where(AuthoringRequest.id > after)
    if query:
        statement = statement.where(AuthoringRequest.raw_key.icontains(query, autoescape=True))
    rows = session.execute(statement.order_by(AuthoringRequest.id).limit(51)).all()
    return AuthoringPage(
        items=[response(row, scope) for row, scope in rows[:50]],
        next_after=rows[49][0].id if len(rows) > 50 else None,
    )


def transition(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    request_id: UUID,
    expected_version: int,
    state: str | None,
) -> AuthoringResponse | None:
    product = _product(
        session, product_id, actor_id, "write" if state is None or state == "draft" else "review"
    )
    row = session.get(AuthoringRequest, request_id)
    if row is None:
        raise AuthoringError("Draft unavailable", 404)
    scope = _scope(session, product, row.scope_id)
    if row.version != expected_version:
        raise AuthoringError("This draft changed. Reload before continuing", 409)
    if state is not None and row.state == state:
        raise AuthoringError("This draft is already in the requested state", 409)
    if state is None:
        record_audit(session, actor_id=actor_id, action="authoring.deleted", entity_id=row.id)
        session.delete(row)
        session.flush()
        return None
    if state == "approved":
        data = AuthoringInput.model_validate(row.payload["input"])
        _, ref, parser = resolve_file(session, scope, data)
        ops = operations(data, parser.format)
        _existing(session, scope, ref, data, ops)
        validate_complete(session, scope, data, parser.format)
        if any(not op.replacement_text.strip() for op in ops):
            raise AuthoringError("Complete the translation before approving")
        if data.max_chars is not None and any(
            grapheme_count(op.replacement_text) > data.max_chars for op in ops
        ):
            raise AuthoringError("Translation exceeds its character limit")
    row.version += 1
    row.state, row.updated_by, row.updated_at = state, actor_id, datetime.now(UTC)
    record_audit(
        session,
        actor_id=actor_id,
        action="authoring.reopened" if state == "draft" else f"authoring.{state}",
        entity_id=row.id,
    )
    session.flush()
    if state == "approved":
        from verboflex.localization.writing.core import WritebackRejected
        from verboflex.services.branch_workflow import (
            BranchWorkflowError,
            new_authoring_activity,
            queue_approval,
        )

        try:
            queue_approval(
                session,
                product_id=product_id,
                actor_id=actor_id,
                proposal_id=row.id,
                version=row.version,
                activity_id=new_authoring_activity(row.id, row.version),
                label=f"{data.key} ({data.language})",
            )
        except (BranchWorkflowError, WritebackRejected) as error:
            raise AuthoringError(str(error), 409) from error
    return response(row, scope)


def reconcile_authoring(session: Session, scope_id: UUID) -> None:
    """Only a successful import can consume additions; never infer a draft deletion."""
    last = UUID(int=0)
    while True:
        rows = session.scalars(
            select(AuthoringRequest)
            .where(AuthoringRequest.scope_id == scope_id, AuthoringRequest.id > last)
            .order_by(AuthoringRequest.id)
            .limit(100)
        ).all()
        if not rows:
            return
        for row in rows:
            last = row.id
            data = AuthoringInput.model_validate(row.payload["input"])
            ops = operations(data, str(row.payload["format"]))
            keys = select(TranslationKey.id).where(
                TranslationKey.scope_id == scope_id,
                TranslationKey.repository_id == UUID(str(row.payload["repository_id"])),
                TranslationKey.configured_branch == str(row.payload["configured_branch"]),
                TranslationKey.raw_key_digest == hashlib.sha256(data.key.encode()).digest(),
                TranslationKey.raw_key == data.key,
                TranslationKey.is_deleted.is_(False),
            )
            values = session.execute(
                select(TranslationValue.selector_digest, TranslationValue.display_text)
                .join(
                    TranslationValueLocator, TranslationValueLocator.value_id == TranslationValue.id
                )
                .where(
                    TranslationValueLocator.path == str(row.payload["path"]),
                    TranslationValue.translation_key_id.in_(keys),
                    TranslationValue.language == data.language,
                    TranslationValue.is_deleted.is_(False),
                )
            ).all()
            actual: dict[str, str] = {digest: text for digest, text in values}
            expected = {
                hashlib.sha256(
                    canonical_selector_bytes(op.selector)
                ).hexdigest(): op.replacement_text
                for op in ops
            }
            if all(actual.get(key) == text for key, text in expected.items()):
                key_id = session.scalar(keys)
                if data.max_chars is not None and key_id is not None and row.state == "approved":
                    existing = session.scalar(
                        select(TranslationConstraint).where(
                            TranslationConstraint.translation_key_id == key_id,
                            TranslationConstraint.language == data.language,
                        )
                    )
                    if existing is None:
                        session.add(
                            TranslationConstraint(
                                scope_id=scope_id,
                                translation_key_id=key_id,
                                language=data.language,
                                max_chars=data.max_chars,
                                created_by=row.created_by,
                                updated_by=row.updated_by,
                            )
                        )
                        session.flush()
                        key_row = session.get(TranslationKey, key_id)
                        assert key_row is not None
                        key_row.constraint_generation += 1
                        recompute_translation_constraints(
                            session, scope_id=scope_id, raw_key=data.key
                        )
                session.delete(row)
        session.flush()


def validate_complete(
    session: Session, scope: LocalizationScope, data: AuthoringInput, format: str
) -> None:
    if data.kind == "plural":
        try:
            required = {form for form, _ in plural_forms(format, data.language)}
        except ValueError as error:
            raise AuthoringError(str(error)) from error
        existing_forms: set[str] = set()
        field = "quantity" if format == "android_xml" else "form_index"
        expected_selector = json.loads(
            canonical_selector_bytes(operations(data, format)[0].selector)
        )
        expected_fields = {k: v for k, v in expected_selector["fields"].items() if k != field}
        if data.parent_key_id:
            for selector in session.scalars(
                select(TranslationValue.selector_bytes).where(
                    TranslationValue.translation_key_id == data.parent_key_id,
                    TranslationValue.language == data.language,
                    TranslationValue.is_deleted.is_(False),
                )
            ):
                actual_selector = json.loads(selector)
                fields = actual_selector["fields"]
                if (
                    actual_selector["kind"] == expected_selector["kind"]
                    and {k: v for k, v in fields.items() if k != field} == expected_fields
                    and field in fields
                ):
                    existing_forms.add(str(fields[field]))
        if not required <= ({f.form for f in data.forms} | existing_forms):
            raise AuthoringError("Complete all plural forms before approving")
        if format == "qt_ts" and {f.form for f in data.forms} - required:
            raise AuthoringError("Unexpected Qt plural form")
    if format == "qt_ts":
        from verboflex.localization.placeholders import compatible_arguments

        if any(
            not compatible_arguments(data.source_text, form.text, format) for form in data.forms
        ):
            raise AuthoringError("Translation placeholders do not match the source")
    from verboflex.models.product_mapping import ProductRepositoryMapping

    base_language = session.scalar(
        select(ProductRepositoryMapping.base_language).where(
            ProductRepositoryMapping.id == scope.current_mapping_id
        )
    )
    if base_language is None:
        raise AuthoringError("Translation source unavailable", 409)
    rules = (
        session.scalars(
            select(TranslationConstraint).where(
                TranslationConstraint.translation_key_id == data.parent_key_id,
                TranslationConstraint.language.in_({data.language, base_language}),
            )
        ).all()
        if data.parent_key_id
        else []
    )
    by_language = {rule.language: rule for rule in rules}
    maximum = project_effective_constraint(
        language=data.language,
        base_language=base_language,
        explicit_constraint=by_language.get(data.language),
        base_constraint=by_language.get(base_language),
    ).maximum
    if maximum is not None and any(grapheme_count(f.text) > maximum for f in data.forms):
        raise AuthoringError("Translation exceeds its character limit")
