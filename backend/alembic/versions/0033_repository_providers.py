"""Provider-scoped repository identity; existing repositories remain Bitbucket."""

import sqlalchemy as sa

from alembic import op

revision = "0033_repository_providers"
down_revision = "0032_database_maintenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column("provider", sa.String(16), nullable=False, server_default="bitbucket"),
    )
    op.create_check_constraint(
        "provider_value", "repositories", "provider IN ('bitbucket', 'github')"
    )
    op.drop_constraint(op.f("ck_repositories_repository_slug_normalized"), "repositories", type_="check")
    op.create_check_constraint(
        "repository_slug_normalized",
        "repositories",
        "repository_slug ~ '^[a-z0-9][a-z0-9_.-]{0,99}$' "
        "AND (provider = 'github' OR repository_slug NOT LIKE '%.%')",
    )
    op.drop_constraint("uq_repositories_provider_identity", "repositories", type_="unique")
    op.create_unique_constraint(
        "uq_repositories_provider_identity",
        "repositories",
        ["provider", "workspace", "repository_slug"],
    )


def downgrade() -> None:
    # Refuse to erase provenance or merge equal identities from different providers.
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM repositories WHERE provider != 'bitbucket')")
    ):
        raise RuntimeError("Remove GitHub repositories before downgrading provider support")
    op.drop_constraint("uq_repositories_provider_identity", "repositories", type_="unique")
    op.create_unique_constraint(
        "uq_repositories_provider_identity", "repositories", ["workspace", "repository_slug"]
    )
    op.drop_constraint(op.f("ck_repositories_repository_slug_normalized"), "repositories", type_="check")
    op.create_check_constraint(
        "repository_slug_normalized",
        "repositories",
        "repository_slug ~ '^[a-z0-9][a-z0-9_-]{0,99}$'",
    )
    op.drop_constraint(op.f("ck_repositories_provider_value"), "repositories", type_="check")
    op.drop_column("repositories", "provider")
