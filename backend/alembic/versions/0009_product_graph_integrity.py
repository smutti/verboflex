"""Enforce product graph ownership and active-revision immutability.

Revision ID: 0009_product_graph_integrity
Revises: 0008_bitbucket_client_credentials
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_product_graph_integrity"
down_revision: str | None = "0008_bitbucket_client_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LEGACY_OWNERSHIP_CHECK = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM products AS product
        JOIN product_revisions AS revision
          ON revision.id = product.active_revision_id
        WHERE revision.product_id <> product.id
    ) OR EXISTS (
        SELECT 1
        FROM products AS product
        JOIN product_revisions AS revision
          ON revision.id = product.candidate_revision_id
        WHERE revision.product_id <> product.id
    ) OR EXISTS (
        SELECT 1
        FROM preview_jobs AS job
        JOIN product_revisions AS revision
          ON revision.id = job.candidate_revision_id
        WHERE revision.product_id <> job.product_id
    ) OR EXISTS (
        SELECT 1
        FROM preview_jobs AS job
        JOIN product_repository_mappings AS mapping
          ON mapping.id = job.mapping_id
        WHERE mapping.revision_id <> job.candidate_revision_id
    ) THEN
        RAISE EXCEPTION 'legacy product graph ownership violation'
            USING ERRCODE = '23514';
    END IF;
END;
$$
"""


ACTIVE_GRAPH_GUARD = """
CREATE FUNCTION verboflex_guard_active_revision_child()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    old_revision_id uuid;
    new_revision_id uuid;
    guarded_revision record;
    revision_is_active boolean;
BEGIN
    IF TG_TABLE_NAME = 'product_revisions' THEN
        IF TG_OP <> 'INSERT' THEN
            old_revision_id := OLD.id;
        END IF;
        IF TG_OP <> 'DELETE' THEN
            new_revision_id := NEW.id;
        END IF;
    ELSIF TG_TABLE_NAME = 'product_repository_mappings' THEN
        IF TG_OP <> 'INSERT' THEN
            old_revision_id := OLD.revision_id;
        END IF;
        IF TG_OP <> 'DELETE' THEN
            new_revision_id := NEW.revision_id;
        END IF;
    ELSE
        IF TG_OP <> 'INSERT' THEN
            SELECT mapping.revision_id
              INTO old_revision_id
              FROM product_repository_mappings AS mapping
             WHERE mapping.id = OLD.mapping_id;
        END IF;
        IF TG_OP <> 'DELETE' THEN
            SELECT mapping.revision_id
              INTO new_revision_id
              FROM product_repository_mappings AS mapping
             WHERE mapping.id = NEW.mapping_id;
        END IF;
    END IF;

    FOR guarded_revision IN
        SELECT revision.id, revision.product_id, revision.is_published
          FROM product_revisions AS revision
         WHERE revision.id = old_revision_id
            OR revision.id = new_revision_id
         ORDER BY revision.id
         FOR SHARE
    LOOP
        SELECT product.active_revision_id = guarded_revision.id
          INTO revision_is_active
          FROM products AS product
         WHERE product.id = guarded_revision.product_id
         FOR SHARE;

        IF guarded_revision.is_published OR revision_is_active THEN
            RAISE EXCEPTION 'active product revision graph is immutable'
                USING ERRCODE = '55000';
        END IF;
    END LOOP;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$
"""


LEGACY_REVISION_GUARD = """
CREATE FUNCTION prevent_published_product_revision_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.is_published THEN
        RAISE EXCEPTION 'published product revision is immutable'
            USING ERRCODE = '55000';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    """Reject corrupt legacy rows before encoding the complete ownership graph."""
    op.execute(LEGACY_OWNERSHIP_CHECK)
    op.execute("DROP TRIGGER trg_product_revisions_immutable_published ON product_revisions")
    op.execute("DROP FUNCTION prevent_published_product_revision_mutation()")

    op.add_column(
        "product_revisions",
        sa.Column("display_name", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "product_revisions",
        sa.Column("name_key", sa.String(length=360), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE product_revisions AS revision "
            "SET display_name = product.display_name, name_key = product.name_key "
            "FROM products AS product WHERE product.id = revision.product_id"
        )
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM product_revisions
                WHERE display_name IS NULL OR name_key IS NULL
            ) THEN
                RAISE EXCEPTION 'product revision identity backfill incomplete'
                    USING ERRCODE = '23502';
            END IF;
        END;
        $$
        """
    )
    op.alter_column("product_revisions", "display_name", nullable=False)
    op.alter_column("product_revisions", "name_key", nullable=False)
    op.create_check_constraint(
        op.f("ck_product_revisions_display_name_length"),
        "product_revisions",
        "char_length(display_name) BETWEEN 1 AND 120",
    )
    op.create_check_constraint(
        op.f("ck_product_revisions_name_key_length"),
        "product_revisions",
        "char_length(name_key) BETWEEN 1 AND 360",
    )

    op.create_unique_constraint(
        "uq_product_revisions_product_id_id",
        "product_revisions",
        ["product_id", "id"],
    )
    op.create_unique_constraint(
        "uq_product_mappings_revision_id_id",
        "product_repository_mappings",
        ["revision_id", "id"],
    )

    op.drop_constraint(
        "fk_preview_jobs_mapping_id_product_repository_mappings",
        "preview_jobs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_preview_jobs_candidate_revision_id_product_revisions",
        "preview_jobs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_preview_jobs_product_id_products",
        "preview_jobs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_products_candidate_revision_id_product_revisions",
        "products",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_products_active_revision_id_product_revisions",
        "products",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "fk_products_active_owned_revision",
        "products",
        "product_revisions",
        ["id", "active_revision_id"],
        ["product_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_products_candidate_owned_revision",
        "products",
        "product_revisions",
        ["id", "candidate_revision_id"],
        ["product_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_preview_jobs_owned_revision",
        "preview_jobs",
        "product_revisions",
        ["product_id", "candidate_revision_id"],
        ["product_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_preview_jobs_owned_mapping",
        "preview_jobs",
        "product_repository_mappings",
        ["candidate_revision_id", "mapping_id"],
        ["revision_id", "id"],
        ondelete="CASCADE",
    )

    op.execute(ACTIVE_GRAPH_GUARD)
    for table_name, trigger_name in (
        ("product_revisions", "trg_guard_active_product_revisions"),
        ("product_repository_mappings", "trg_guard_active_product_mappings"),
        ("product_mapping_repository_sides", "trg_guard_active_mapping_sides"),
        ("product_mapping_allowed_targets", "trg_guard_active_mapping_targets"),
    ):
        op.execute(
            f"CREATE TRIGGER {trigger_name} "
            f"BEFORE INSERT OR UPDATE OR DELETE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION verboflex_guard_active_revision_child()"
        )


def downgrade() -> None:
    """Restore revision 0008 objects in reverse dependency order."""
    for table_name, trigger_name in (
        ("product_mapping_allowed_targets", "trg_guard_active_mapping_targets"),
        ("product_mapping_repository_sides", "trg_guard_active_mapping_sides"),
        ("product_repository_mappings", "trg_guard_active_product_mappings"),
        ("product_revisions", "trg_guard_active_product_revisions"),
    ):
        op.execute(f"DROP TRIGGER {trigger_name} ON {table_name}")
    op.execute("DROP FUNCTION verboflex_guard_active_revision_child()")
    op.execute(LEGACY_REVISION_GUARD)
    op.execute(
        "CREATE TRIGGER trg_product_revisions_immutable_published "
        "BEFORE UPDATE OR DELETE ON product_revisions "
        "FOR EACH ROW EXECUTE FUNCTION prevent_published_product_revision_mutation()"
    )

    op.drop_constraint("fk_preview_jobs_owned_mapping", "preview_jobs", type_="foreignkey")
    op.drop_constraint("fk_preview_jobs_owned_revision", "preview_jobs", type_="foreignkey")
    op.drop_constraint(
        "fk_products_candidate_owned_revision",
        "products",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_products_active_owned_revision",
        "products",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "fk_products_active_revision_id_product_revisions",
        "products",
        "product_revisions",
        ["active_revision_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_products_candidate_revision_id_product_revisions",
        "products",
        "product_revisions",
        ["candidate_revision_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_preview_jobs_product_id_products",
        "preview_jobs",
        "products",
        ["product_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_preview_jobs_candidate_revision_id_product_revisions",
        "preview_jobs",
        "product_revisions",
        ["candidate_revision_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_preview_jobs_mapping_id_product_repository_mappings",
        "preview_jobs",
        "product_repository_mappings",
        ["mapping_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "uq_product_mappings_revision_id_id",
        "product_repository_mappings",
        type_="unique",
    )
    op.drop_constraint(
        "uq_product_revisions_product_id_id",
        "product_revisions",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_product_revisions_name_key_length"),
        "product_revisions",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_product_revisions_display_name_length"),
        "product_revisions",
        type_="check",
    )
    op.drop_column("product_revisions", "name_key")
    op.drop_column("product_revisions", "display_name")
