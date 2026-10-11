"""Create the durable review workspace and discussion schema.

Revision ID: 0028_review_workspace
Revises: 0027_xliff_format
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0028_review_workspace"
down_revision: str | None = "0027_xliff_format"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LANGUAGE_CHECK = "language ~ '^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?$'"
REVIEW_STATE_CHECK = "state IN ('draft', 'approved', 'rejected')"
ACTIVITY_KIND_CHECK = "kind IN ('proposal_saved', 'state_changed')"
NOTIFICATION_KIND_CHECK = "kind IN ('mention')"
VERSION_RANGE = "BETWEEN 0 AND 9007199254740991"


IMMUTABLE_REVIEW_EVIDENCE_GUARD = """
CREATE FUNCTION verboflex_guard_review_evidence_immutable()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'review evidence is append-only'
        USING ERRCODE = '55000';
END;
$$
"""


PROPOSAL_VALUE_IDENTITY_GUARD = """
CREATE FUNCTION verboflex_guard_translation_proposal_value_identity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM translation_values AS imported
        WHERE imported.id = NEW.translation_value_id
          AND imported.translation_key_id = NEW.translation_key_id
          AND imported.language = NEW.language
          AND imported.selector_version = NEW.selector_version
          AND imported.selector_digest = NEW.selector_digest
    ) THEN
        RAISE EXCEPTION 'proposal value imported identity mismatch'
            USING ERRCODE = '23503';
    END IF;
    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    """Add separate pending, evidence, discussion, and recipient authorities."""
    op.create_table(
        "translation_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("translation_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("state", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column(
            "reconciliation_required",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
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
            name=op.f("ck_translation_proposals_language_normalized"),
        ),
        sa.CheckConstraint(
            f"version {VERSION_RANGE}",
            name=op.f("ck_translation_proposals_version_range"),
        ),
        sa.CheckConstraint(
            REVIEW_STATE_CHECK,
            name=op.f("ck_translation_proposals_state_value"),
        ),
        sa.CheckConstraint(
            "NOT reconciliation_required OR state = 'draft'",
            name=op.f("ck_translation_proposals_reconciliation_requires_draft"),
        ),
        sa.ForeignKeyConstraint(
            ["translation_key_id", "scope_id"],
            ["translation_keys.id", "translation_keys.scope_id"],
            name="fk_translation_proposals_owned_key",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_translation_proposals_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_translation_proposals_updated_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_translation_proposals")),
        sa.UniqueConstraint(
            "translation_key_id",
            "language",
            name="uq_translation_proposals_key_language",
        ),
        sa.UniqueConstraint(
            "id",
            "translation_key_id",
            "language",
            name="uq_translation_proposals_owned_identity",
        ),
    )
    op.create_index(
        "ix_translation_proposals_scope_language_state",
        "translation_proposals",
        ["scope_id", "language", "state"],
    )

    op.create_table(
        "translation_proposal_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("translation_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=False),
        sa.Column("translation_value_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("selector_version", sa.Integer(), nullable=False),
        sa.Column("selector_digest", sa.String(length=64), nullable=False),
        sa.Column("basis_revision_number", sa.Integer(), nullable=False),
        sa.Column("basis_digest", sa.String(length=64), nullable=False),
        sa.Column("proposed_text", sa.Text(), nullable=False),
        sa.Column("grapheme_count", sa.Integer(), nullable=False),
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
            name=op.f("ck_translation_proposal_values_language_normalized"),
        ),
        sa.CheckConstraint(
            "selector_version = 1",
            name=op.f("ck_translation_proposal_values_selector_version_value"),
        ),
        sa.CheckConstraint(
            "char_length(selector_digest) = 64 AND selector_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_translation_proposal_values_selector_digest_sha256"),
        ),
        sa.CheckConstraint(
            "basis_revision_number >= 0",
            name=op.f("ck_translation_proposal_values_basis_revision_non_negative"),
        ),
        sa.CheckConstraint(
            "char_length(basis_digest) = 64 AND basis_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_translation_proposal_values_basis_digest_sha256"),
        ),
        sa.CheckConstraint(
            "char_length(proposed_text) <= 1048576",
            name=op.f("ck_translation_proposal_values_proposed_text_length"),
        ),
        sa.CheckConstraint(
            "grapheme_count BETWEEN 0 AND 1048576",
            name=op.f("ck_translation_proposal_values_grapheme_count_range"),
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id", "translation_key_id", "language"],
            [
                "translation_proposals.id",
                "translation_proposals.translation_key_id",
                "translation_proposals.language",
            ],
            name="fk_translation_proposal_values_owned_proposal",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["translation_value_id", "translation_key_id"],
            ["translation_values.id", "translation_values.translation_key_id"],
            name="fk_translation_proposal_values_imported_value",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_translation_proposal_values")),
        sa.UniqueConstraint(
            "proposal_id",
            "selector_version",
            "selector_digest",
            name="uq_translation_proposal_values_proposal_selector",
        ),
    )
    op.create_index(
        "ix_translation_proposal_values_imported_value",
        "translation_proposal_values",
        ["translation_value_id"],
    )

    op.create_table(
        "translation_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("translation_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
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
            name=op.f("ck_translation_comments_language_normalized"),
        ),
        sa.CheckConstraint(
            f"current_version {VERSION_RANGE} AND current_version > 0",
            name=op.f("ck_translation_comments_current_version_range"),
        ),
        sa.CheckConstraint(
            "(deleted_at IS NULL AND deleted_by IS NULL) OR "
            "(deleted_at IS NOT NULL AND deleted_by IS NOT NULL)",
            name=op.f("ck_translation_comments_deletion_metadata_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["translation_key_id", "scope_id"],
            ["translation_keys.id", "translation_keys.scope_id"],
            name="fk_translation_comments_owned_key",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_translation_comments_author_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"],
            ["users.id"],
            name=op.f("fk_translation_comments_deleted_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_translation_comments")),
        sa.UniqueConstraint(
            "id",
            "translation_key_id",
            "language",
            name="uq_translation_comments_owned_identity",
        ),
    )
    op.create_index(
        "ix_translation_comments_key_language_created",
        "translation_comments",
        ["translation_key_id", "language", "created_at", "id"],
    )

    op.create_table(
        "translation_comment_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("comment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("translation_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"version_number {VERSION_RANGE} AND version_number > 0",
            name=op.f("ck_translation_comment_versions_version_number_range"),
        ),
        sa.CheckConstraint(
            "char_length(body) BETWEEN 1 AND 65536 AND body ~ '[^[:space:]]'",
            name=op.f("ck_translation_comment_versions_body_nonblank_length"),
        ),
        sa.ForeignKeyConstraint(
            ["comment_id", "translation_key_id", "language"],
            [
                "translation_comments.id",
                "translation_comments.translation_key_id",
                "translation_comments.language",
            ],
            name="fk_translation_comment_versions_owned_comment",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_translation_comment_versions_author_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_translation_comment_versions")),
        sa.UniqueConstraint(
            "comment_id",
            "version_number",
            name="uq_translation_comment_versions_comment_number",
        ),
        sa.UniqueConstraint(
            "id",
            "comment_id",
            name="uq_translation_comment_versions_owned_identity",
        ),
    )
    op.create_index(
        "ix_translation_comment_versions_comment_created",
        "translation_comment_versions",
        ["comment_id", "created_at", "id"],
    )

    op.create_table(
        "translation_comment_mentions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("comment_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mentioned_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_utf16", sa.Integer(), nullable=False),
        sa.Column("end_utf16", sa.Integer(), nullable=False),
        sa.Column("display_text", sa.String(length=201), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "start_utf16 >= 0 AND end_utf16 > start_utf16 AND end_utf16 <= 131072",
            name=op.f("ck_translation_comment_mentions_utf16_range"),
        ),
        sa.CheckConstraint(
            "char_length(display_text) BETWEEN 2 AND 201",
            name=op.f("ck_translation_comment_mentions_display_text_length"),
        ),
        sa.ForeignKeyConstraint(
            ["comment_version_id"],
            ["translation_comment_versions.id"],
            name="fk_translation_comment_mentions_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["mentioned_user_id"],
            ["users.id"],
            name=op.f("fk_translation_comment_mentions_mentioned_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_translation_comment_mentions")),
        sa.UniqueConstraint(
            "comment_version_id",
            "start_utf16",
            "end_utf16",
            name="uq_translation_comment_mentions_version_range",
        ),
    )
    op.create_index(
        "ix_translation_comment_mentions_user",
        "translation_comment_mentions",
        ["mentioned_user_id", "comment_version_id"],
    )

    op.create_table(
        "review_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("translation_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("proposal_version", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.String(length=16), nullable=True),
        sa.Column("to_state", sa.String(length=16), nullable=True),
        sa.Column(
            "before_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "after_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("comment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            LANGUAGE_CHECK,
            name=op.f("ck_review_activities_language_normalized"),
        ),
        sa.CheckConstraint(
            ACTIVITY_KIND_CHECK,
            name=op.f("ck_review_activities_kind_value"),
        ),
        sa.CheckConstraint(
            f"proposal_version {VERSION_RANGE}",
            name=op.f("ck_review_activities_proposal_version_range"),
        ),
        sa.CheckConstraint(
            "from_state IS NULL OR from_state IN ('draft', 'approved', 'rejected')",
            name=op.f("ck_review_activities_from_state_value"),
        ),
        sa.CheckConstraint(
            "to_state IS NULL OR to_state IN ('draft', 'approved', 'rejected')",
            name=op.f("ck_review_activities_to_state_value"),
        ),
        sa.CheckConstraint(
            "reason IS NULL OR char_length(reason) <= 4096",
            name=op.f("ck_review_activities_reason_length"),
        ),
        sa.CheckConstraint(
            "before_values IS NULL OR jsonb_typeof(before_values) = 'array'",
            name=op.f("ck_review_activities_before_values_array"),
        ),
        sa.CheckConstraint(
            "after_values IS NULL OR jsonb_typeof(after_values) = 'array'",
            name=op.f("ck_review_activities_after_values_array"),
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id", "translation_key_id", "language"],
            [
                "translation_proposals.id",
                "translation_proposals.translation_key_id",
                "translation_proposals.language",
            ],
            name="fk_review_activities_owned_proposal",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["comment_id"],
            ["translation_comments.id"],
            name=op.f("fk_review_activities_comment_id_translation_comments"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_review_activities_actor_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_activities")),
    )
    op.create_index(
        "ix_review_activities_proposal_created",
        "review_activities",
        ["proposal_id", "created_at", "id"],
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "originating_comment_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=24), server_default="mention", nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            NOTIFICATION_KIND_CHECK,
            name=op.f("ck_notifications_kind_value"),
        ),
        sa.CheckConstraint(
            "recipient_user_id <> actor_user_id",
            name=op.f("ck_notifications_actor_is_not_recipient"),
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"],
            ["users.id"],
            name="fk_notifications_recipient",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_notifications_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["originating_comment_id"],
            ["translation_comments.id"],
            name="fk_notifications_originating_comment",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint(
            "recipient_user_id",
            "originating_comment_id",
            "kind",
            name="uq_notifications_recipient_comment_kind",
        ),
    )
    op.create_index(
        "ix_notifications_recipient_unread_created",
        "notifications",
        ["recipient_user_id", "created_at", "id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )
    op.create_index(
        "ix_notifications_recipient_created",
        "notifications",
        ["recipient_user_id", "created_at", "id"],
    )

    op.execute(PROPOSAL_VALUE_IDENTITY_GUARD)
    op.execute(
        "CREATE TRIGGER trg_translation_proposal_values_imported_identity "
        "BEFORE INSERT OR UPDATE ON translation_proposal_values "
        "FOR EACH ROW EXECUTE FUNCTION "
        "verboflex_guard_translation_proposal_value_identity()"
    )
    op.execute(IMMUTABLE_REVIEW_EVIDENCE_GUARD)
    for table_name, trigger_name in (
        ("review_activities", "trg_review_activities_append_only"),
        (
            "translation_comment_versions",
            "trg_translation_comment_versions_immutable",
        ),
        (
            "translation_comment_mentions",
            "trg_translation_comment_mentions_immutable",
        ),
    ):
        op.execute(
            f"CREATE TRIGGER {trigger_name} "
            f"BEFORE UPDATE OR DELETE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION "
            "verboflex_guard_review_evidence_immutable()"
        )


def downgrade() -> None:
    """Remove only Phase 5 review authorities in dependency-safe order."""
    for table_name, trigger_name in (
        (
            "translation_comment_mentions",
            "trg_translation_comment_mentions_immutable",
        ),
        (
            "translation_comment_versions",
            "trg_translation_comment_versions_immutable",
        ),
        ("review_activities", "trg_review_activities_append_only"),
    ):
        op.execute(f"DROP TRIGGER {trigger_name} ON {table_name}")
    op.execute("DROP FUNCTION verboflex_guard_review_evidence_immutable()")
    op.execute(
        "DROP TRIGGER trg_translation_proposal_values_imported_identity "
        "ON translation_proposal_values"
    )
    op.execute("DROP FUNCTION verboflex_guard_translation_proposal_value_identity()")

    op.drop_index("ix_notifications_recipient_created", table_name="notifications")
    op.drop_index(
        "ix_notifications_recipient_unread_created",
        table_name="notifications",
    )
    op.drop_table("notifications")
    op.drop_index(
        "ix_review_activities_proposal_created",
        table_name="review_activities",
    )
    op.drop_table("review_activities")
    op.drop_index(
        "ix_translation_comment_mentions_user",
        table_name="translation_comment_mentions",
    )
    op.drop_table("translation_comment_mentions")
    op.drop_index(
        "ix_translation_comment_versions_comment_created",
        table_name="translation_comment_versions",
    )
    op.drop_table("translation_comment_versions")
    op.drop_index(
        "ix_translation_comments_key_language_created",
        table_name="translation_comments",
    )
    op.drop_table("translation_comments")
    op.drop_index(
        "ix_translation_proposal_values_imported_value",
        table_name="translation_proposal_values",
    )
    op.drop_table("translation_proposal_values")
    op.drop_index(
        "ix_translation_proposals_scope_language_state",
        table_name="translation_proposals",
    )
    op.drop_table("translation_proposals")
