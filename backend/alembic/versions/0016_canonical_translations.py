"""Create stable canonical translation identity and provenance.

Revision ID: 0016_canonical_translations
Revises: 0015_mapping_base_language
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0016_canonical_translations"
down_revision: str | None = "0015_mapping_base_language"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SELECTOR_CHECK = (
    "selector_kind IN ('scalar', 'android_quantity', 'android_array_item', "
    "'qt_numerus', 'qt_length_variant', 'json_path')"
)
FORMAT_CHECK = "format IN ('android_xml', 'qt_ts', 'json', 'ios_strings')"
SIDE_CHECK = "repository_side IN ('direct', 'keys', 'translations')"
REVIEW_STATE_CHECK = "review_state IN ('draft', 'approved', 'rejected')"
EFFECTIVE_CONSTRAINT_SOURCE_CHECK = (
    "effective_constraint_source IN ('none', 'base_default', 'language_override')"
)
ISSUE_CODE_CHECK = (
    "issue_code IN ('malformed_file', 'ambiguous_structure', "
    "'unsupported_structure', 'duplicate_key', 'base_language_required')"
)
LANGUAGE_CHECK = "language ~ '^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?$'"
DIGEST_CHECK = "char_length(selector_digest) = 64 AND selector_digest ~ '^[0-9a-f]{64}$'"
DELETION_CHECK = (
    "(NOT is_deleted AND deleted_at IS NULL) OR (is_deleted AND deleted_at IS NOT NULL)"
)
PROJECTION_CHECK = (
    "(effective_constraint_source = 'none' AND effective_max_chars IS NULL "
    "AND NOT is_over_limit) OR "
    "(effective_constraint_source IN ('base_default', 'language_override') "
    "AND effective_max_chars IS NOT NULL "
    "AND effective_max_chars BETWEEN 0 AND 1048576 "
    "AND is_over_limit = (grapheme_count > effective_max_chars))"
)


IMMUTABLE_VALUE_REVISION_GUARD = """
CREATE FUNCTION verboflex_guard_translation_value_revision_immutable()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'translation value revision is immutable'
        USING ERRCODE = '55000';
END;
$$
"""


SCOPE_ACTIVATION_GUARD = """
CREATE FUNCTION verboflex_guard_localization_scope_activation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.active_execution_id IS NULL THEN
        RETURN NEW;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM import_executions AS execution
        JOIN import_jobs AS job
          ON job.id = execution.import_job_id
         AND job.id = NEW.active_import_job_id
         AND job.current_execution_id = execution.id
         AND job.active_baseline_execution_id = execution.id
         AND job.state = 'current'
        JOIN product_repository_mappings AS mapping
          ON mapping.id = job.mapping_id
         AND mapping.id = NEW.current_mapping_id
         AND mapping.revision_id = NEW.current_revision_id
         AND mapping.identity_key = NEW.mapping_identity_key
         AND mapping.base_language IS NOT NULL
        JOIN product_revisions AS revision
          ON revision.id = mapping.revision_id
         AND revision.product_id = NEW.product_id
        WHERE execution.id = NEW.active_execution_id
          AND execution.state = 'succeeded'
    ) THEN
        RAISE EXCEPTION 'localization scope activation authority violation'
            USING ERRCODE = '23503';
    END IF;

    RETURN NEW;
END;
$$
"""


VALUE_PROVENANCE_GUARD = """
CREATE FUNCTION verboflex_guard_translation_value_provenance()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_TABLE_NAME = 'translation_value_revisions' THEN
        IF NOT EXISTS (
            SELECT 1
            FROM import_source_references AS source
            WHERE source.execution_id = NEW.import_execution_id
              AND source.position = NEW.source_reference_position
              AND source.commit_hash = NEW.source_commit_hash
        ) THEN
            RAISE EXCEPTION 'translation value revision provenance violation'
                USING ERRCODE = '23503';
        END IF;
        RETURN NEW;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM import_source_references AS source
        WHERE source.execution_id = NEW.import_execution_id
          AND source.position = NEW.source_reference_position
          AND source.repository_side = NEW.repository_side
          AND source.repository_id = NEW.repository_id
          AND source.source_branch = NEW.configured_branch
          AND source.commit_hash = NEW.source_commit_hash
          AND source.path = NEW.path
    ) THEN
        RAISE EXCEPTION 'translation value locator provenance violation'
            USING ERRCODE = '23503';
    END IF;

    RETURN NEW;
END;
$$
"""


STAGING_GUARD = """
CREATE FUNCTION verboflex_guard_canonical_staging()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    execution_state text;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        RAISE EXCEPTION 'canonical staging row is immutable'
            USING ERRCODE = '55000';
    END IF;

    SELECT state INTO execution_state
    FROM import_executions
    WHERE id = NEW.import_execution_id
      AND import_job_id = NEW.import_job_id
    FOR UPDATE;

    IF execution_state IS DISTINCT FROM 'running' THEN
        RAISE EXCEPTION 'staging requires running import execution'
            USING ERRCODE = '55000';
    END IF;

    IF TG_TABLE_NAME = 'translation_parse_issues' THEN
        IF NOT EXISTS (
            SELECT 1
            FROM import_jobs AS job
            JOIN product_repository_mappings AS mapping
              ON mapping.id = job.mapping_id
             AND mapping.base_language IS NOT NULL
            JOIN product_mapping_repository_sides AS side
              ON side.mapping_id = mapping.id
             AND side.role = NEW.repository_side
            WHERE job.id = NEW.import_job_id
        ) THEN
            RAISE EXCEPTION 'translation parse issue ownership violation'
                USING ERRCODE = '23503';
        END IF;
        RETURN NEW;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM import_jobs AS job
        JOIN product_repository_mappings AS mapping
          ON mapping.id = job.mapping_id
         AND mapping.base_language IS NOT NULL
        JOIN product_revisions AS revision
          ON revision.id = mapping.revision_id
         AND revision.product_id = job.product_id
        JOIN localization_scopes AS scope
          ON scope.id = NEW.scope_id
         AND scope.product_id = job.product_id
         AND scope.mapping_identity_key = mapping.identity_key
        JOIN product_mapping_repository_sides AS side
          ON side.mapping_id = mapping.id
         AND side.role = NEW.repository_side
         AND side.repository_id = NEW.repository_id
         AND side.source_branch = NEW.configured_branch
        JOIN import_source_references AS source
          ON source.execution_id = NEW.import_execution_id
         AND source.position = NEW.source_reference_position
         AND source.repository_side = NEW.repository_side
         AND source.repository_id = NEW.repository_id
         AND source.source_branch = NEW.configured_branch
         AND source.path = NEW.path
        WHERE job.id = NEW.import_job_id
    ) THEN
        RAISE EXCEPTION 'staged translation ownership violation'
            USING ERRCODE = '23503';
    END IF;

    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    """Create the stable canonical persistence and staging contract."""
    op.create_unique_constraint(
        "uq_product_mappings_revision_id_identity",
        "product_repository_mappings",
        ["revision_id", "id", "identity_key"],
    )
    op.create_unique_constraint(
        "uq_import_jobs_id_mapping",
        "import_jobs",
        ["id", "mapping_id"],
    )

    op.create_table(
        "localization_scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mapping_identity_key", sa.String(length=1200), nullable=False),
        sa.Column("current_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_mapping_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("active_import_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("active_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dataset_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(mapping_identity_key) BETWEEN 1 AND 1200",
            name=op.f("ck_localization_scopes_mapping_identity_key_length"),
        ),
        sa.CheckConstraint(
            "dataset_version >= 0",
            name=op.f("ck_localization_scopes_dataset_version_non_negative"),
        ),
        sa.CheckConstraint(
            "(active_import_job_id IS NULL AND active_execution_id IS NULL "
            "AND dataset_version = 0) OR "
            "(active_import_job_id IS NOT NULL AND active_execution_id IS NOT NULL "
            "AND dataset_version > 0)",
            name=op.f("ck_localization_scopes_active_dataset_state"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_localization_scopes_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id", "current_revision_id"],
            ["product_revisions.product_id", "product_revisions.id"],
            name="fk_localization_scopes_owned_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["current_revision_id", "current_mapping_id", "mapping_identity_key"],
            [
                "product_repository_mappings.revision_id",
                "product_repository_mappings.id",
                "product_repository_mappings.identity_key",
            ],
            name="fk_localization_scopes_semantic_mapping",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["active_import_job_id", "current_mapping_id"],
            ["import_jobs.id", "import_jobs.mapping_id"],
            name="fk_localization_scopes_active_import_job",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["active_execution_id", "active_import_job_id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_localization_scopes_active_execution",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_localization_scopes")),
        sa.UniqueConstraint(
            "product_id",
            "mapping_identity_key",
            name="uq_localization_scopes_product_mapping_identity",
        ),
        sa.UniqueConstraint(
            "id",
            "product_id",
            name="uq_localization_scopes_id_product",
        ),
    )
    op.create_index(
        "ix_localization_scopes_active_execution",
        "localization_scopes",
        ["active_execution_id"],
    )

    op.create_table(
        "translation_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configured_branch", sa.String(length=255), nullable=False),
        sa.Column("raw_key", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(configured_branch) BETWEEN 1 AND 255",
            name=op.f("ck_translation_keys_configured_branch_length"),
        ),
        sa.CheckConstraint(
            "char_length(raw_key) BETWEEN 1 AND 1048576",
            name=op.f("ck_translation_keys_raw_key_length"),
        ),
        sa.CheckConstraint(
            DELETION_CHECK,
            name=op.f("ck_translation_keys_deletion_state"),
        ),
        sa.ForeignKeyConstraint(
            ["scope_id", "product_id"],
            ["localization_scopes.id", "localization_scopes.product_id"],
            name="fk_translation_keys_owned_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_translation_keys_repository_id_repositories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_translation_keys")),
        sa.UniqueConstraint(
            "scope_id",
            "repository_id",
            "configured_branch",
            "raw_key",
            name="uq_translation_keys_natural_identity",
        ),
        sa.UniqueConstraint("id", "scope_id", name="uq_translation_keys_id_scope"),
    )
    op.create_index(
        "ix_translation_keys_scope_deleted",
        "translation_keys",
        ["scope_id", "is_deleted"],
    )

    op.create_table(
        "translation_constraints",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("translation_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=False),
        sa.Column("max_chars", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            LANGUAGE_CHECK,
            name=op.f("ck_translation_constraints_language_normalized"),
        ),
        sa.CheckConstraint(
            "max_chars BETWEEN 0 AND 1048576",
            name=op.f("ck_translation_constraints_max_chars_bound"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_translation_constraints_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["translation_key_id", "scope_id"],
            ["translation_keys.id", "translation_keys.scope_id"],
            name="fk_translation_constraints_owned_key",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_translation_constraints_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_translation_constraints_updated_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_translation_constraints")),
        sa.UniqueConstraint(
            "translation_key_id",
            "language",
            name="uq_translation_constraints_key_language",
        ),
    )
    op.create_index(
        "ix_translation_constraints_scope_language",
        "translation_constraints",
        ["scope_id", "language"],
    )

    op.create_table(
        "translation_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("translation_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=False),
        sa.Column("selector_version", sa.Integer(), nullable=False),
        sa.Column("selector_kind", sa.String(length=32), nullable=False),
        sa.Column("selector_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("selector_digest", sa.String(length=64), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("translated_text", sa.Text(), nullable=True),
        sa.Column("display_text", sa.Text(), nullable=False),
        sa.Column("structure", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("review_state", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("grapheme_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("effective_max_chars", sa.Integer(), nullable=True),
        sa.Column(
            "effective_constraint_source",
            sa.String(length=24),
            server_default="none",
            nullable=False,
        ),
        sa.Column("is_over_limit", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(LANGUAGE_CHECK, name=op.f("ck_translation_values_language_normalized")),
        sa.CheckConstraint(
            "selector_version = 1",
            name=op.f("ck_translation_values_selector_version_value"),
        ),
        sa.CheckConstraint(SELECTOR_CHECK, name=op.f("ck_translation_values_selector_kind_value")),
        sa.CheckConstraint(DIGEST_CHECK, name=op.f("ck_translation_values_selector_digest_sha256")),
        sa.CheckConstraint(
            "octet_length(selector_bytes) BETWEEN 1 AND 1048576",
            name=op.f("ck_translation_values_selector_bytes_length"),
        ),
        sa.CheckConstraint(
            "source_text IS NULL OR char_length(source_text) <= 1048576",
            name=op.f("ck_translation_values_source_text_length"),
        ),
        sa.CheckConstraint(
            "translated_text IS NULL OR char_length(translated_text) <= 1048576",
            name=op.f("ck_translation_values_translated_text_length"),
        ),
        sa.CheckConstraint(
            "char_length(display_text) <= 1048576",
            name=op.f("ck_translation_values_display_text_length"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(structure) = 'array'",
            name=op.f("ck_translation_values_structure_array"),
        ),
        sa.CheckConstraint(
            REVIEW_STATE_CHECK,
            name=op.f("ck_translation_values_review_state_value"),
        ),
        sa.CheckConstraint(
            "grapheme_count >= 0",
            name=op.f("ck_translation_values_grapheme_count_non_negative"),
        ),
        sa.CheckConstraint(
            EFFECTIVE_CONSTRAINT_SOURCE_CHECK,
            name=op.f("ck_translation_values_effective_constraint_source_value"),
        ),
        sa.CheckConstraint(
            PROJECTION_CHECK,
            name=op.f("ck_translation_values_constraint_projection_consistent"),
        ),
        sa.CheckConstraint(DELETION_CHECK, name=op.f("ck_translation_values_deletion_state")),
        sa.ForeignKeyConstraint(
            ["translation_key_id", "scope_id"],
            ["translation_keys.id", "translation_keys.scope_id"],
            name="fk_translation_values_owned_key",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_translation_values")),
        sa.UniqueConstraint(
            "translation_key_id",
            "language",
            "selector_version",
            "selector_digest",
            name="uq_translation_values_natural_identity",
        ),
        sa.UniqueConstraint(
            "id",
            "translation_key_id",
            name="uq_translation_values_id_key",
        ),
    )
    op.create_index(
        "ix_translation_values_scope_language_deleted",
        "translation_values",
        ["scope_id", "language", "is_deleted"],
    )
    op.create_index(
        "ix_translation_values_scope_constraint_filters",
        "translation_values",
        ["scope_id", "language", "review_state", "is_deleted", "is_over_limit"],
    )

    op.create_table(
        "translation_value_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("value_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("translation_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("revision_digest", sa.String(length=64), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_reference_position", sa.Integer(), nullable=False),
        sa.Column("source_commit_hash", sa.String(length=40), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("translated_text", sa.Text(), nullable=True),
        sa.Column("display_text", sa.Text(), nullable=False),
        sa.Column("structure", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("review_state", sa.String(length=16), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_reference", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revision_number > 0",
            name=op.f("ck_translation_value_revisions_revision_number_positive"),
        ),
        sa.CheckConstraint(
            "char_length(revision_digest) = 64 AND revision_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_translation_value_revisions_revision_digest_sha256"),
        ),
        sa.CheckConstraint(
            "char_length(source_commit_hash) = 40 AND source_commit_hash ~ '^[0-9a-f]{40}$'",
            name=op.f("ck_translation_value_revisions_source_commit_hash_sha1"),
        ),
        sa.CheckConstraint(
            "source_reference_position >= 0",
            name=op.f("ck_translation_value_revisions_source_reference_position_non_negative"),
        ),
        sa.CheckConstraint(
            "source_text IS NULL OR char_length(source_text) <= 1048576",
            name=op.f("ck_translation_value_revisions_source_text_length"),
        ),
        sa.CheckConstraint(
            "translated_text IS NULL OR char_length(translated_text) <= 1048576",
            name=op.f("ck_translation_value_revisions_translated_text_length"),
        ),
        sa.CheckConstraint(
            "char_length(display_text) <= 1048576",
            name=op.f("ck_translation_value_revisions_display_text_length"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(structure) = 'array'",
            name=op.f("ck_translation_value_revisions_structure_array"),
        ),
        sa.CheckConstraint(
            REVIEW_STATE_CHECK,
            name=op.f("ck_translation_value_revisions_review_state_value"),
        ),
        sa.CheckConstraint(
            DELETION_CHECK,
            name=op.f("ck_translation_value_revisions_deletion_state"),
        ),
        sa.CheckConstraint(
            "correlation_reference IS NULL OR char_length(correlation_reference) BETWEEN 1 AND 256",
            name=op.f("ck_translation_value_revisions_correlation_reference_length"),
        ),
        sa.ForeignKeyConstraint(
            ["value_id", "translation_key_id"],
            ["translation_values.id", "translation_values.translation_key_id"],
            name="fk_translation_value_revisions_owned_value",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["import_execution_id", "import_job_id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_translation_value_revisions_owned_execution",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["import_execution_id", "source_reference_position"],
            ["import_source_references.execution_id", "import_source_references.position"],
            name="fk_translation_value_revisions_source_reference",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_translation_value_revisions")),
        sa.UniqueConstraint(
            "value_id",
            "revision_number",
            name="uq_translation_value_revisions_value_number",
        ),
        sa.UniqueConstraint(
            "value_id",
            "revision_digest",
            name="uq_translation_value_revisions_value_digest",
        ),
    )
    op.create_index(
        "ix_translation_value_revisions_execution",
        "translation_value_revisions",
        ["import_execution_id"],
    )

    op.create_table(
        "translation_value_locators",
        sa.Column("value_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("translation_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_reference_position", sa.Integer(), nullable=False),
        sa.Column("repository_side", sa.String(length=16), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configured_branch", sa.String(length=255), nullable=False),
        sa.Column("source_commit_hash", sa.String(length=40), nullable=False),
        sa.Column("format", sa.String(length=24), nullable=False),
        sa.Column("path", sa.String(length=4096), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("structural_address", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("line", sa.Integer(), nullable=True),
        sa.Column("column", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_reference_position >= 0",
            name=op.f("ck_translation_value_locators_source_position_non_negative"),
        ),
        sa.CheckConstraint(
            SIDE_CHECK,
            name=op.f("ck_translation_value_locators_repository_side_value"),
        ),
        sa.CheckConstraint(
            "char_length(configured_branch) BETWEEN 1 AND 255",
            name=op.f("ck_translation_value_locators_configured_branch_length"),
        ),
        sa.CheckConstraint(
            "char_length(source_commit_hash) = 40 AND source_commit_hash ~ '^[0-9a-f]{40}$'",
            name=op.f("ck_translation_value_locators_source_commit_hash_sha1"),
        ),
        sa.CheckConstraint(FORMAT_CHECK, name=op.f("ck_translation_value_locators_format_value")),
        sa.CheckConstraint(
            "char_length(path) BETWEEN 1 AND 4096",
            name=op.f("ck_translation_value_locators_path_length"),
        ),
        sa.CheckConstraint(
            "position >= 0",
            name=op.f("ck_translation_value_locators_position_non_negative"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(structural_address) = 'array' "
            "AND jsonb_array_length(structural_address) BETWEEN 1 AND 128",
            name=op.f("ck_translation_value_locators_structural_address_array"),
        ),
        sa.CheckConstraint(
            "line IS NULL OR line BETWEEN 1 AND 2147483647",
            name=op.f("ck_translation_value_locators_line_coordinate"),
        ),
        sa.CheckConstraint(
            '"column" IS NULL OR "column" BETWEEN 1 AND 2147483647',
            name=op.f("ck_translation_value_locators_column_coordinate"),
        ),
        sa.ForeignKeyConstraint(
            ["value_id", "translation_key_id"],
            ["translation_values.id", "translation_values.translation_key_id"],
            name="fk_translation_value_locators_owned_value",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["import_execution_id", "import_job_id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_translation_value_locators_owned_execution",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["import_execution_id", "source_reference_position"],
            ["import_source_references.execution_id", "import_source_references.position"],
            name="fk_translation_value_locators_source_reference",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_translation_value_locators_repository_id_repositories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("value_id", name=op.f("pk_translation_value_locators")),
    )
    op.create_index(
        "ix_translation_value_locators_execution_path",
        "translation_value_locators",
        ["import_execution_id", "path"],
    )

    op.create_table(
        "staged_translation_values",
        sa.Column("import_execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configured_branch", sa.String(length=255), nullable=False),
        sa.Column("raw_key", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=False),
        sa.Column("selector_version", sa.Integer(), nullable=False),
        sa.Column("selector_kind", sa.String(length=32), nullable=False),
        sa.Column("selector_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("selector_digest", sa.String(length=64), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("translated_text", sa.Text(), nullable=True),
        sa.Column("display_text", sa.Text(), nullable=False),
        sa.Column("structure", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("repository_side", sa.String(length=16), nullable=False),
        sa.Column("source_reference_position", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(length=24), nullable=False),
        sa.Column("path", sa.String(length=4096), nullable=False),
        sa.Column("locator_position", sa.Integer(), nullable=False),
        sa.Column("structural_address", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("line", sa.Integer(), nullable=True),
        sa.Column("column", sa.Integer(), nullable=True),
        sa.Column("correlation_reference", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position >= 0",
            name=op.f("ck_staged_translation_values_position_non_negative"),
        ),
        sa.CheckConstraint(
            "char_length(configured_branch) BETWEEN 1 AND 255",
            name=op.f("ck_staged_translation_values_configured_branch_length"),
        ),
        sa.CheckConstraint(
            "char_length(raw_key) BETWEEN 1 AND 1048576",
            name=op.f("ck_staged_translation_values_raw_key_length"),
        ),
        sa.CheckConstraint(
            LANGUAGE_CHECK,
            name=op.f("ck_staged_translation_values_language_normalized"),
        ),
        sa.CheckConstraint(
            "selector_version = 1",
            name=op.f("ck_staged_translation_values_selector_version_value"),
        ),
        sa.CheckConstraint(
            SELECTOR_CHECK,
            name=op.f("ck_staged_translation_values_selector_kind_value"),
        ),
        sa.CheckConstraint(
            DIGEST_CHECK,
            name=op.f("ck_staged_translation_values_selector_digest_sha256"),
        ),
        sa.CheckConstraint(
            "octet_length(selector_bytes) BETWEEN 1 AND 1048576",
            name=op.f("ck_staged_translation_values_selector_bytes_length"),
        ),
        sa.CheckConstraint(
            "source_text IS NULL OR char_length(source_text) <= 1048576",
            name=op.f("ck_staged_translation_values_source_text_length"),
        ),
        sa.CheckConstraint(
            "translated_text IS NULL OR char_length(translated_text) <= 1048576",
            name=op.f("ck_staged_translation_values_translated_text_length"),
        ),
        sa.CheckConstraint(
            "char_length(display_text) <= 1048576",
            name=op.f("ck_staged_translation_values_display_text_length"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(structure) = 'array'",
            name=op.f("ck_staged_translation_values_structure_array"),
        ),
        sa.CheckConstraint(
            SIDE_CHECK,
            name=op.f("ck_staged_translation_values_repository_side_value"),
        ),
        sa.CheckConstraint(
            "source_reference_position >= 0",
            name=op.f("ck_staged_translation_values_source_reference_position_non_negative"),
        ),
        sa.CheckConstraint(
            FORMAT_CHECK,
            name=op.f("ck_staged_translation_values_format_value"),
        ),
        sa.CheckConstraint(
            "char_length(path) BETWEEN 1 AND 4096",
            name=op.f("ck_staged_translation_values_path_length"),
        ),
        sa.CheckConstraint(
            "locator_position >= 0",
            name=op.f("ck_staged_translation_values_locator_position_non_negative"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(structural_address) = 'array' "
            "AND jsonb_array_length(structural_address) BETWEEN 1 AND 128",
            name=op.f("ck_staged_translation_values_structural_address_array"),
        ),
        sa.CheckConstraint(
            "line IS NULL OR line BETWEEN 1 AND 2147483647",
            name=op.f("ck_staged_translation_values_line_coordinate"),
        ),
        sa.CheckConstraint(
            '"column" IS NULL OR "column" BETWEEN 1 AND 2147483647',
            name=op.f("ck_staged_translation_values_column_coordinate"),
        ),
        sa.CheckConstraint(
            "correlation_reference IS NULL OR char_length(correlation_reference) BETWEEN 1 AND 256",
            name=op.f("ck_staged_translation_values_correlation_reference_length"),
        ),
        sa.ForeignKeyConstraint(
            ["import_execution_id", "import_job_id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_staged_translation_values_owned_execution",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["import_execution_id", "source_reference_position"],
            ["import_source_references.execution_id", "import_source_references.position"],
            name="fk_staged_translation_values_source_reference",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scope_id"],
            ["localization_scopes.id"],
            name="fk_staged_translation_values_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_staged_translation_values_repository_id_repositories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "import_execution_id",
            "position",
            name=op.f("pk_staged_translation_values"),
        ),
        sa.UniqueConstraint(
            "import_execution_id",
            "repository_id",
            "configured_branch",
            "raw_key",
            "language",
            "selector_version",
            "selector_digest",
            name="uq_staged_translation_values_natural_identity",
        ),
    )
    op.create_index(
        "ix_staged_translation_values_execution_position",
        "staged_translation_values",
        ["import_execution_id", "position"],
    )

    op.create_table(
        "translation_parse_issues",
        sa.Column("import_execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_side", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=4096), nullable=False),
        sa.Column("issue_code", sa.String(length=32), nullable=False),
        sa.Column("message", sa.String(length=256), nullable=False),
        sa.Column("line", sa.Integer(), nullable=True),
        sa.Column("column", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position BETWEEN 0 AND 4",
            name=op.f("ck_translation_parse_issues_position_bounded"),
        ),
        sa.CheckConstraint(
            SIDE_CHECK,
            name=op.f("ck_translation_parse_issues_repository_side_value"),
        ),
        sa.CheckConstraint(
            "char_length(path) BETWEEN 1 AND 4096 AND path !~ '(^/|(^|/)\\.\\.(/|$))'",
            name=op.f("ck_translation_parse_issues_safe_relative_path"),
        ),
        sa.CheckConstraint(
            ISSUE_CODE_CHECK,
            name=op.f("ck_translation_parse_issues_issue_code_value"),
        ),
        sa.CheckConstraint(
            "char_length(message) BETWEEN 1 AND 256",
            name=op.f("ck_translation_parse_issues_message_length"),
        ),
        sa.CheckConstraint(
            "line IS NULL OR line BETWEEN 1 AND 2147483647",
            name=op.f("ck_translation_parse_issues_line_coordinate"),
        ),
        sa.CheckConstraint(
            '"column" IS NULL OR "column" BETWEEN 1 AND 2147483647',
            name=op.f("ck_translation_parse_issues_column_coordinate"),
        ),
        sa.ForeignKeyConstraint(
            ["import_execution_id", "import_job_id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_translation_parse_issues_owned_execution",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "import_execution_id",
            "position",
            name=op.f("pk_translation_parse_issues"),
        ),
    )
    op.create_index(
        "ix_translation_parse_issues_execution_position",
        "translation_parse_issues",
        ["import_execution_id", "position"],
    )

    op.execute(IMMUTABLE_VALUE_REVISION_GUARD)
    op.execute(
        "CREATE TRIGGER trg_translation_value_revisions_immutable "
        "BEFORE UPDATE OR DELETE ON translation_value_revisions "
        "FOR EACH ROW EXECUTE FUNCTION "
        "verboflex_guard_translation_value_revision_immutable()"
    )
    op.execute(SCOPE_ACTIVATION_GUARD)
    op.execute(
        "CREATE TRIGGER trg_localization_scopes_activation_guard "
        "BEFORE INSERT OR UPDATE ON localization_scopes "
        "FOR EACH ROW EXECUTE FUNCTION verboflex_guard_localization_scope_activation()"
    )
    op.execute(VALUE_PROVENANCE_GUARD)
    op.execute(
        "CREATE TRIGGER trg_translation_value_revisions_provenance "
        "BEFORE INSERT ON translation_value_revisions "
        "FOR EACH ROW EXECUTE FUNCTION verboflex_guard_translation_value_provenance()"
    )
    op.execute(
        "CREATE TRIGGER trg_translation_value_locators_provenance "
        "BEFORE INSERT OR UPDATE ON translation_value_locators "
        "FOR EACH ROW EXECUTE FUNCTION verboflex_guard_translation_value_provenance()"
    )
    op.execute(STAGING_GUARD)
    op.execute(
        "CREATE TRIGGER trg_staged_translation_values_guard "
        "BEFORE INSERT OR UPDATE OR DELETE ON staged_translation_values "
        "FOR EACH ROW EXECUTE FUNCTION verboflex_guard_canonical_staging()"
    )
    op.execute(
        "CREATE TRIGGER trg_translation_parse_issues_guard "
        "BEFORE INSERT OR UPDATE OR DELETE ON translation_parse_issues "
        "FOR EACH ROW EXECUTE FUNCTION verboflex_guard_canonical_staging()"
    )


def downgrade() -> None:
    """Remove only the canonical persistence contract owned by this revision."""
    op.execute("DROP TRIGGER trg_translation_parse_issues_guard ON translation_parse_issues")
    op.execute("DROP TRIGGER trg_staged_translation_values_guard ON staged_translation_values")
    op.execute("DROP FUNCTION verboflex_guard_canonical_staging()")
    op.execute(
        "DROP TRIGGER trg_translation_value_locators_provenance ON translation_value_locators"
    )
    op.execute(
        "DROP TRIGGER trg_translation_value_revisions_provenance ON translation_value_revisions"
    )
    op.execute("DROP FUNCTION verboflex_guard_translation_value_provenance()")
    op.execute("DROP TRIGGER trg_localization_scopes_activation_guard ON localization_scopes")
    op.execute("DROP FUNCTION verboflex_guard_localization_scope_activation()")
    op.execute(
        "DROP TRIGGER trg_translation_value_revisions_immutable ON translation_value_revisions"
    )
    op.execute("DROP FUNCTION verboflex_guard_translation_value_revision_immutable()")

    op.drop_index(
        "ix_translation_parse_issues_execution_position",
        table_name="translation_parse_issues",
    )
    op.drop_table("translation_parse_issues")
    op.drop_index(
        "ix_staged_translation_values_execution_position",
        table_name="staged_translation_values",
    )
    op.drop_table("staged_translation_values")
    op.drop_index(
        "ix_translation_value_locators_execution_path",
        table_name="translation_value_locators",
    )
    op.drop_table("translation_value_locators")
    op.drop_index(
        "ix_translation_value_revisions_execution",
        table_name="translation_value_revisions",
    )
    op.drop_table("translation_value_revisions")
    op.drop_index(
        "ix_translation_values_scope_constraint_filters",
        table_name="translation_values",
    )
    op.drop_index(
        "ix_translation_values_scope_language_deleted",
        table_name="translation_values",
    )
    op.drop_table("translation_values")
    op.drop_index(
        "ix_translation_constraints_scope_language",
        table_name="translation_constraints",
    )
    op.drop_table("translation_constraints")
    op.drop_index(
        "ix_translation_keys_scope_deleted",
        table_name="translation_keys",
    )
    op.drop_table("translation_keys")
    op.drop_index(
        "ix_localization_scopes_active_execution",
        table_name="localization_scopes",
    )
    op.drop_table("localization_scopes")

    op.drop_constraint(
        "uq_import_jobs_id_mapping",
        "import_jobs",
        type_="unique",
    )
    op.drop_constraint(
        "uq_product_mappings_revision_id_identity",
        "product_repository_mappings",
        type_="unique",
    )
