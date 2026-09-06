"""Stable canonical localization identities, provenance, and staging rows."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from verboflex.db.base import Base

if TYPE_CHECKING:
    from verboflex.models.product_mapping import ProductRepositoryMapping
    from verboflex.models.translation_constraint import TranslationConstraint


class SelectorKind(StrEnum):
    """Version-one canonical selector discriminators persisted by imports."""

    SCALAR = "scalar"
    ANDROID_QUANTITY = "android_quantity"
    ANDROID_ARRAY_ITEM = "android_array_item"
    QT_NUMERUS = "qt_numerus"
    QT_LENGTH_VARIANT = "qt_length_variant"
    JSON_PATH = "json_path"


class ReviewState(StrEnum):
    """Closed v1 review workflow states."""

    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class EffectiveConstraintSource(StrEnum):
    """Authority used to materialize a value's effective maximum."""

    NONE = "none"
    BASE_DEFAULT = "base_default"
    LANGUAGE_OVERRIDE = "language_override"


class ParseIssueCode(StrEnum):
    """Bounded safe parser issue categories persisted for an execution."""

    MALFORMED_FILE = "malformed_file"
    AMBIGUOUS_STRUCTURE = "ambiguous_structure"
    UNSUPPORTED_STRUCTURE = "unsupported_structure"
    DUPLICATE_KEY = "duplicate_key"
    BASE_LANGUAGE_REQUIRED = "base_language_required"


def _enum_check(column: str, vocabulary: type[StrEnum]) -> str:
    values = ", ".join(f"'{member.value}'" for member in vocabulary)
    return f"{column} IN ({values})"


_SELECTOR_CHECK = _enum_check("selector_kind", SelectorKind)
_FORMAT_CHECK = "format IN ('android_xml', 'qt_ts', 'json', 'ios_strings')"
_SIDE_CHECK = "repository_side IN ('direct', 'keys', 'translations')"
_REVIEW_STATE_CHECK = _enum_check("review_state", ReviewState)
_EFFECTIVE_CONSTRAINT_SOURCE_CHECK = _enum_check(
    "effective_constraint_source", EffectiveConstraintSource
)
_ISSUE_CODE_CHECK = _enum_check("issue_code", ParseIssueCode)
_LANGUAGE_CHECK = "language ~ '^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?$'"
_DIGEST_CHECK = "char_length(selector_digest) = 64 AND selector_digest ~ '^[0-9a-f]{64}$'"
_DELETION_CHECK = (
    "(NOT is_deleted AND deleted_at IS NULL) OR (is_deleted AND deleted_at IS NOT NULL)"
)
_PROJECTION_CHECK = (
    "(effective_constraint_source = 'none' AND effective_max_chars IS NULL "
    "AND NOT is_over_limit) OR "
    "(effective_constraint_source IN ('base_default', 'language_override') "
    "AND effective_max_chars IS NOT NULL "
    "AND effective_max_chars BETWEEN 0 AND 1048576 "
    "AND is_over_limit = (grapheme_count > effective_max_chars))"
)


class LocalizationScope(Base):
    """Stable product plus semantic-mapping identity across revision clones."""

    __tablename__ = "localization_scopes"
    __table_args__ = (
        CheckConstraint(
            "char_length(mapping_identity_key) BETWEEN 1 AND 1200",
            name="mapping_identity_key_length",
        ),
        CheckConstraint("dataset_version >= 0", name="dataset_version_non_negative"),
        CheckConstraint(
            "(active_import_job_id IS NULL AND active_execution_id IS NULL "
            "AND dataset_version = 0) OR "
            "(active_import_job_id IS NOT NULL AND active_execution_id IS NOT NULL "
            "AND dataset_version > 0)",
            name="active_dataset_state",
        ),
        UniqueConstraint(
            "product_id",
            "mapping_identity_key",
            name="uq_localization_scopes_product_mapping_identity",
        ),
        UniqueConstraint(
            "id",
            "product_id",
            name="uq_localization_scopes_id_product",
        ),
        ForeignKeyConstraint(
            ["product_id", "current_revision_id"],
            ["product_revisions.product_id", "product_revisions.id"],
            name="fk_localization_scopes_owned_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["current_revision_id", "current_mapping_id", "mapping_identity_key"],
            [
                "product_repository_mappings.revision_id",
                "product_repository_mappings.id",
                "product_repository_mappings.identity_key",
            ],
            name="fk_localization_scopes_semantic_mapping",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["active_import_job_id", "current_mapping_id"],
            ["import_jobs.id", "import_jobs.mapping_id"],
            name="fk_localization_scopes_active_import_job",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["active_execution_id", "active_import_job_id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_localization_scopes_active_execution",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        Index(
            "ix_localization_scopes_active_execution",
            "active_execution_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    product_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    mapping_identity_key: Mapped[str] = mapped_column(String(1200), nullable=False)
    current_revision_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    current_mapping_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    active_import_job_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    active_execution_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    dataset_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    current_mapping: Mapped[ProductRepositoryMapping] = relationship(
        back_populates="localization_scopes",
        viewonly=True,
        lazy="selectin",
    )
    translation_keys: Mapped[list[TranslationKey]] = relationship(
        back_populates="scope",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TranslationKey.raw_key",
    )


class TranslationKey(Base):
    """Stable raw logical key independent of its current file locator."""

    __tablename__ = "translation_keys"
    __table_args__ = (
        CheckConstraint(
            "char_length(configured_branch) BETWEEN 1 AND 255",
            name="configured_branch_length",
        ),
        CheckConstraint(
            "char_length(raw_key) BETWEEN 1 AND 1048576",
            name="raw_key_length",
        ),
        CheckConstraint(_DELETION_CHECK, name="deletion_state"),
        CheckConstraint(
            "constraint_generation BETWEEN 0 AND 9007199254740991",
            name="constraint_generation_non_negative",
        ),
        UniqueConstraint(
            "scope_id",
            "repository_id",
            "configured_branch",
            "raw_key",
            name="uq_translation_keys_natural_identity",
        ),
        UniqueConstraint(
            "id",
            "scope_id",
            name="uq_translation_keys_id_scope",
        ),
        ForeignKeyConstraint(
            ["scope_id", "product_id"],
            ["localization_scopes.id", "localization_scopes.product_id"],
            name="fk_translation_keys_owned_scope",
            ondelete="CASCADE",
        ),
        Index(
            "ix_translation_keys_scope_deleted",
            "scope_id",
            "is_deleted",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    scope_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    repository_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    configured_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_key: Mapped[str] = mapped_column(Text, nullable=False)
    constraint_generation: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    scope: Mapped[LocalizationScope] = relationship(back_populates="translation_keys")
    values: Mapped[list[TranslationValue]] = relationship(
        back_populates="key",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TranslationValue.id",
    )
    constraints: Mapped[list[TranslationConstraint]] = relationship(
        back_populates="key",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TranslationConstraint.language",
    )


class TranslationValue(Base):
    """Individually addressable current value under one stable raw key."""

    __tablename__ = "translation_values"
    __table_args__ = (
        CheckConstraint(_LANGUAGE_CHECK, name="language_normalized"),
        CheckConstraint("selector_version = 1", name="selector_version_value"),
        CheckConstraint(_SELECTOR_CHECK, name="selector_kind_value"),
        CheckConstraint(_DIGEST_CHECK, name="selector_digest_sha256"),
        CheckConstraint(
            "octet_length(selector_bytes) BETWEEN 1 AND 1048576",
            name="selector_bytes_length",
        ),
        CheckConstraint(
            "source_text IS NULL OR char_length(source_text) <= 1048576",
            name="source_text_length",
        ),
        CheckConstraint(
            "translated_text IS NULL OR char_length(translated_text) <= 1048576",
            name="translated_text_length",
        ),
        CheckConstraint(
            "char_length(display_text) <= 1048576",
            name="display_text_length",
        ),
        CheckConstraint("jsonb_typeof(structure) = 'array'", name="structure_array"),
        CheckConstraint(_REVIEW_STATE_CHECK, name="review_state_value"),
        CheckConstraint(
            "grapheme_count >= 0",
            name="grapheme_count_non_negative",
        ),
        CheckConstraint(
            _EFFECTIVE_CONSTRAINT_SOURCE_CHECK,
            name="effective_constraint_source_value",
        ),
        CheckConstraint(
            _PROJECTION_CHECK,
            name="constraint_projection_consistent",
        ),
        CheckConstraint(_DELETION_CHECK, name="deletion_state"),
        UniqueConstraint(
            "translation_key_id",
            "language",
            "selector_version",
            "selector_digest",
            name="uq_translation_values_natural_identity",
        ),
        UniqueConstraint(
            "id",
            "translation_key_id",
            name="uq_translation_values_id_key",
        ),
        ForeignKeyConstraint(
            ["translation_key_id", "scope_id"],
            ["translation_keys.id", "translation_keys.scope_id"],
            name="fk_translation_values_owned_key",
            ondelete="CASCADE",
        ),
        Index(
            "ix_translation_values_scope_language_deleted",
            "scope_id",
            "language",
            "is_deleted",
        ),
        Index(
            "ix_translation_values_scope_constraint_filters",
            "scope_id",
            "language",
            "review_state",
            "is_deleted",
            "is_over_limit",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    scope_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    translation_key_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    selector_version: Mapped[int] = mapped_column(Integer, nullable=False)
    selector_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    selector_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    selector_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_text: Mapped[str] = mapped_column(Text, nullable=False)
    structure: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    review_state: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    grapheme_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    effective_max_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effective_constraint_source: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="none",
        server_default="none",
    )
    is_over_limit: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    key: Mapped[TranslationKey] = relationship(back_populates="values")
    revisions: Mapped[list[TranslationValueRevision]] = relationship(
        back_populates="value",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TranslationValueRevision.revision_number",
    )
    locator: Mapped[TranslationValueLocator | None] = relationship(
        back_populates="value",
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
        uselist=False,
    )


class TranslationValueRevision(Base):
    """Immutable versioned content and exact import provenance for one value."""

    __tablename__ = "translation_value_revisions"
    __table_args__ = (
        CheckConstraint("revision_number > 0", name="revision_number_positive"),
        CheckConstraint(
            "char_length(revision_digest) = 64 AND revision_digest ~ '^[0-9a-f]{64}$'",
            name="revision_digest_sha256",
        ),
        CheckConstraint(
            "char_length(source_commit_hash) = 40 AND source_commit_hash ~ '^[0-9a-f]{40}$'",
            name="source_commit_hash_sha1",
        ),
        CheckConstraint(
            "source_reference_position >= 0",
            name="source_reference_position_non_negative",
        ),
        CheckConstraint(
            "source_text IS NULL OR char_length(source_text) <= 1048576",
            name="source_text_length",
        ),
        CheckConstraint(
            "translated_text IS NULL OR char_length(translated_text) <= 1048576",
            name="translated_text_length",
        ),
        CheckConstraint(
            "char_length(display_text) <= 1048576",
            name="display_text_length",
        ),
        CheckConstraint("jsonb_typeof(structure) = 'array'", name="structure_array"),
        CheckConstraint(_REVIEW_STATE_CHECK, name="review_state_value"),
        CheckConstraint(_DELETION_CHECK, name="deletion_state"),
        CheckConstraint(
            "correlation_reference IS NULL OR char_length(correlation_reference) BETWEEN 1 AND 256",
            name="correlation_reference_length",
        ),
        UniqueConstraint(
            "value_id",
            "revision_number",
            name="uq_translation_value_revisions_value_number",
        ),
        UniqueConstraint(
            "value_id",
            "revision_digest",
            name="uq_translation_value_revisions_value_digest",
        ),
        ForeignKeyConstraint(
            ["value_id", "translation_key_id"],
            ["translation_values.id", "translation_values.translation_key_id"],
            name="fk_translation_value_revisions_owned_value",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["import_execution_id", "import_job_id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_translation_value_revisions_owned_execution",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["import_execution_id", "source_reference_position"],
            ["import_source_references.execution_id", "import_source_references.position"],
            name="fk_translation_value_revisions_source_reference",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_translation_value_revisions_execution",
            "import_execution_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    value_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    translation_key_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    import_job_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    import_execution_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    source_reference_position: Mapped[int] = mapped_column(Integer, nullable=False)
    source_commit_hash: Mapped[str] = mapped_column(String(40), nullable=False)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_text: Mapped[str] = mapped_column(Text, nullable=False)
    structure: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    review_state: Mapped[str] = mapped_column(String(16), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    correlation_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    value: Mapped[TranslationValue] = relationship(back_populates="revisions")


class TranslationValueLocator(Base):
    """Mutable current locator tied to immutable execution source provenance."""

    __tablename__ = "translation_value_locators"
    __table_args__ = (
        CheckConstraint("source_reference_position >= 0", name="source_position_non_negative"),
        CheckConstraint(_SIDE_CHECK, name="repository_side_value"),
        CheckConstraint(
            "char_length(configured_branch) BETWEEN 1 AND 255",
            name="configured_branch_length",
        ),
        CheckConstraint(
            "char_length(source_commit_hash) = 40 AND source_commit_hash ~ '^[0-9a-f]{40}$'",
            name="source_commit_hash_sha1",
        ),
        CheckConstraint(_FORMAT_CHECK, name="format_value"),
        CheckConstraint("char_length(path) BETWEEN 1 AND 4096", name="path_length"),
        CheckConstraint("position >= 0", name="position_non_negative"),
        CheckConstraint(
            "jsonb_typeof(structural_address) = 'array' "
            "AND jsonb_array_length(structural_address) BETWEEN 1 AND 128",
            name="structural_address_array",
        ),
        CheckConstraint(
            "line IS NULL OR line BETWEEN 1 AND 2147483647",
            name="line_coordinate",
        ),
        CheckConstraint(
            '"column" IS NULL OR "column" BETWEEN 1 AND 2147483647',
            name="column_coordinate",
        ),
        ForeignKeyConstraint(
            ["value_id", "translation_key_id"],
            ["translation_values.id", "translation_values.translation_key_id"],
            name="fk_translation_value_locators_owned_value",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["import_execution_id", "import_job_id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_translation_value_locators_owned_execution",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["import_execution_id", "source_reference_position"],
            ["import_source_references.execution_id", "import_source_references.position"],
            name="fk_translation_value_locators_source_reference",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_translation_value_locators_execution_path",
            "import_execution_id",
            "path",
        ),
    )

    value_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
    )
    translation_key_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    import_job_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    import_execution_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    source_reference_position: Mapped[int] = mapped_column(Integer, nullable=False)
    repository_side: Mapped[str] = mapped_column(String(16), nullable=False)
    repository_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    configured_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    source_commit_hash: Mapped[str] = mapped_column(String(40), nullable=False)
    format: Mapped[str] = mapped_column(String(24), nullable=False)
    path: Mapped[str] = mapped_column(String(4096), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    structural_address: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    value: Mapped[TranslationValue] = relationship(back_populates="locator")


class StagedTranslationValue(Base):
    """Immutable execution-owned parser output awaiting atomic activation."""

    __tablename__ = "staged_translation_values"
    __table_args__ = (
        CheckConstraint("position >= 0", name="position_non_negative"),
        CheckConstraint(
            "char_length(configured_branch) BETWEEN 1 AND 255",
            name="configured_branch_length",
        ),
        CheckConstraint(
            "char_length(raw_key) BETWEEN 1 AND 1048576",
            name="raw_key_length",
        ),
        CheckConstraint(_LANGUAGE_CHECK, name="language_normalized"),
        CheckConstraint("selector_version = 1", name="selector_version_value"),
        CheckConstraint(_SELECTOR_CHECK, name="selector_kind_value"),
        CheckConstraint(_DIGEST_CHECK, name="selector_digest_sha256"),
        CheckConstraint(
            "octet_length(selector_bytes) BETWEEN 1 AND 1048576",
            name="selector_bytes_length",
        ),
        CheckConstraint(
            "source_text IS NULL OR char_length(source_text) <= 1048576",
            name="source_text_length",
        ),
        CheckConstraint(
            "translated_text IS NULL OR char_length(translated_text) <= 1048576",
            name="translated_text_length",
        ),
        CheckConstraint(
            "char_length(display_text) <= 1048576",
            name="display_text_length",
        ),
        CheckConstraint("jsonb_typeof(structure) = 'array'", name="structure_array"),
        CheckConstraint(_SIDE_CHECK, name="repository_side_value"),
        CheckConstraint(
            "source_reference_position >= 0",
            name="source_reference_position_non_negative",
        ),
        CheckConstraint(_FORMAT_CHECK, name="format_value"),
        CheckConstraint("char_length(path) BETWEEN 1 AND 4096", name="path_length"),
        CheckConstraint("locator_position >= 0", name="locator_position_non_negative"),
        CheckConstraint(
            "jsonb_typeof(structural_address) = 'array' "
            "AND jsonb_array_length(structural_address) BETWEEN 1 AND 128",
            name="structural_address_array",
        ),
        CheckConstraint(
            "line IS NULL OR line BETWEEN 1 AND 2147483647",
            name="line_coordinate",
        ),
        CheckConstraint(
            '"column" IS NULL OR "column" BETWEEN 1 AND 2147483647',
            name="column_coordinate",
        ),
        CheckConstraint(
            "correlation_reference IS NULL OR char_length(correlation_reference) BETWEEN 1 AND 256",
            name="correlation_reference_length",
        ),
        UniqueConstraint(
            "import_execution_id",
            "repository_id",
            "configured_branch",
            "raw_key",
            "language",
            "selector_version",
            "selector_digest",
            name="uq_staged_translation_values_natural_identity",
        ),
        ForeignKeyConstraint(
            ["import_execution_id", "import_job_id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_staged_translation_values_owned_execution",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["import_execution_id", "source_reference_position"],
            ["import_source_references.execution_id", "import_source_references.position"],
            name="fk_staged_translation_values_source_reference",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["scope_id"],
            ["localization_scopes.id"],
            name="fk_staged_translation_values_scope",
            ondelete="CASCADE",
        ),
        Index(
            "ix_staged_translation_values_execution_position",
            "import_execution_id",
            "position",
        ),
    )

    import_execution_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_job_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    scope_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    repository_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    configured_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_key: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    selector_version: Mapped[int] = mapped_column(Integer, nullable=False)
    selector_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    selector_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    selector_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_text: Mapped[str] = mapped_column(Text, nullable=False)
    structure: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    repository_side: Mapped[str] = mapped_column(String(16), nullable=False)
    source_reference_position: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(24), nullable=False)
    path: Mapped[str] = mapped_column(String(4096), nullable=False)
    locator_position: Mapped[int] = mapped_column(Integer, nullable=False)
    structural_address: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correlation_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TranslationParseIssue(Base):
    """Bounded, safe, execution-owned parser diagnostic without source excerpts."""

    __tablename__ = "translation_parse_issues"
    __table_args__ = (
        CheckConstraint("position BETWEEN 0 AND 4", name="position_bounded"),
        CheckConstraint(_SIDE_CHECK, name="repository_side_value"),
        CheckConstraint(
            "char_length(path) BETWEEN 1 AND 4096 AND path !~ '(^/|(^|/)\\.\\.(/|$))'",
            name="safe_relative_path",
        ),
        CheckConstraint(_ISSUE_CODE_CHECK, name="issue_code_value"),
        CheckConstraint(
            "char_length(message) BETWEEN 1 AND 256",
            name="message_length",
        ),
        CheckConstraint(
            "line IS NULL OR line BETWEEN 1 AND 2147483647",
            name="line_coordinate",
        ),
        CheckConstraint(
            '"column" IS NULL OR "column" BETWEEN 1 AND 2147483647',
            name="column_coordinate",
        ),
        ForeignKeyConstraint(
            ["import_execution_id", "import_job_id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_translation_parse_issues_owned_execution",
            ondelete="CASCADE",
        ),
        Index(
            "ix_translation_parse_issues_execution_position",
            "import_execution_id",
            "position",
        ),
    )

    import_execution_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_job_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    repository_side: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(4096), nullable=False)
    issue_code: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(String(256), nullable=False)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
