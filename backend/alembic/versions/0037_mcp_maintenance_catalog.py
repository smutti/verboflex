"""Recognize the six OAuth foreign keys in the maintenance schema guard."""

import json

import sqlalchemy as sa

from alembic import op

revision = "0037_mcp_maintenance_catalog"
down_revision = "0036_mcp_oauth"
branch_labels = None
depends_on = None

FK_CATALOG_SQL = """SELECT coalesce(jsonb_agg(jsonb_build_array(
    conrelid::regclass::text, conname, pg_get_constraintdef(oid))
    ORDER BY conrelid::regclass::text, conname), '[]'::jsonb)::text
    FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace
    AND conrelid::regclass::text NOT LIKE 'maintenance_%'"""

OAUTH_FOREIGN_KEYS = [
    [
        "mcp_oauth_grants",
        "fk_mcp_oauth_grants_client_id_mcp_oauth_clients",
        "FOREIGN KEY (client_id) REFERENCES mcp_oauth_clients(id) ON DELETE CASCADE",
    ],
    [
        "mcp_oauth_grants",
        "fk_mcp_oauth_grants_user_id_users",
        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE",
    ],
    [
        "mcp_oauth_requests",
        "fk_mcp_oauth_requests_client_id_mcp_oauth_clients",
        "FOREIGN KEY (client_id) REFERENCES mcp_oauth_clients(id) ON DELETE CASCADE",
    ],
    [
        "mcp_oauth_requests",
        "fk_mcp_oauth_requests_grant_id_mcp_oauth_grants",
        "FOREIGN KEY (grant_id) REFERENCES mcp_oauth_grants(id) ON DELETE SET NULL",
    ],
    [
        "mcp_oauth_requests",
        "fk_mcp_oauth_requests_user_id_users",
        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE",
    ],
    [
        "mcp_oauth_tokens",
        "fk_mcp_oauth_tokens_grant_id_mcp_oauth_grants",
        "FOREIGN KEY (grant_id) REFERENCES mcp_oauth_grants(id) ON DELETE CASCADE",
    ],
]


def upgrade() -> None:
    connection = op.get_bind()
    installed = connection.scalar(
        sa.text("SELECT installed_definition FROM maintenance_schema WHERE name='foreign_keys'")
    )
    current = connection.scalar(sa.text(FK_CATALOG_SQL))
    # Never bless arbitrary schema drift just because a migration is running.
    if not installed or sorted(json.loads(current)) != sorted(
        json.loads(installed) + OAUTH_FOREIGN_KEYS
    ):
        raise ValueError("unexpected maintenance foreign key changes")
    connection.execute(
        sa.text(
            "UPDATE maintenance_schema SET installed_definition=:catalog WHERE name='foreign_keys'"
        ),
        {"catalog": current},
    )


def downgrade() -> None:
    connection = op.get_bind()
    installed = connection.scalar(
        sa.text("SELECT installed_definition FROM maintenance_schema WHERE name='foreign_keys'")
    )
    # Restore 0036's snapshot; its downgrade subsequently removes the OAuth tables.
    connection.execute(
        sa.text(
            "UPDATE maintenance_schema SET installed_definition="
            "CAST(CAST(:catalog AS jsonb) AS text) WHERE name='foreign_keys'"
        ),
        {
            "catalog": json.dumps(
                [row for row in json.loads(installed) if row not in OAUTH_FOREIGN_KEYS]
            )
        },
    )
