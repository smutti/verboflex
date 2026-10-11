"""Bound natural-identity indexes without truncating canonical provider keys.

Revision ID: 0020_bounded_key_identities
Revises: 0019_unicode_search_indexes
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_bounded_key_identities"
down_revision: str | None = "0019_unicode_search_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# convert_to and textsend are STABLE in PostgreSQL 18, not usable in generated
# expressions. In a UTF8 database the immutable bytea input conversion preserves
# text bytes once every backslash has been escaped (including literal \\x/\\001).
DIGEST = "sha256(replace(raw_key, chr(92), chr(92)||chr(92))::bytea)"
IDENTITIES = (
    ("translation_keys", ["scope_id", "repository_id", "configured_branch"], []),
    (
        "staged_translation_values",
        ["import_execution_id", "repository_id", "configured_branch"],
        ["language", "selector_version", "selector_digest"],
    ),
)


def upgrade() -> None:
    if op.get_bind().scalar(sa.text("SHOW server_encoding")) != "UTF8":
        raise RuntimeError("canonical key identities require a UTF8 database")
    for table, prefix, suffix in IDENTITIES:
        op.add_column(
            table,
            sa.Column(
                "raw_key_digest",
                sa.LargeBinary(),
                sa.Computed(DIGEST, persisted=True),
                nullable=False,
            ),
        )
        op.drop_constraint(f"uq_{table}_natural_identity", table, type_="unique")
        op.create_unique_constraint(
            f"uq_{table}_natural_identity", table, [*prefix, "raw_key_digest", *suffix]
        )


def downgrade() -> None:
    # Recreating the old index can fail for long live keys. Transactional DDL
    # then rolls back, preserving the working schema rather than deleting keys.
    for table, prefix, suffix in reversed(IDENTITIES):
        op.drop_constraint(f"uq_{table}_natural_identity", table, type_="unique")
        op.create_unique_constraint(
            f"uq_{table}_natural_identity", table, [*prefix, "raw_key", *suffix]
        )
        op.drop_column(table, "raw_key_digest")
