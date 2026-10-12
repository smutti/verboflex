"""Explicit product membership, delegated administration and durable team evidence."""

import json
import sqlalchemy as sa
from alembic import op

revision = "0044_product_membership"
down_revision = "0043_product_workspace_coverage"
branch_labels = None
depends_on = None

FK_CATALOG_SQL = """SELECT coalesce(jsonb_agg(jsonb_build_array(
    conrelid::regclass::text, conname, pg_get_constraintdef(oid))
    ORDER BY conrelid::regclass::text, conname), '[]'::jsonb)::text
    FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace
    AND conrelid::regclass::text NOT LIKE 'maintenance_%'"""
ADDED_FKS = [
    [
        "product_members",
        "fk_product_members_user_id_users",
        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE",
    ],
    [
        "product_members",
        "fk_product_members_product_id_products",
        "FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE",
    ],
]


def _catalog(upgrade: bool) -> None:
    connection = op.get_bind()
    installed = connection.scalar(
        sa.text("SELECT installed_definition FROM maintenance_schema WHERE name='foreign_keys'")
    )
    current = connection.scalar(sa.text(FK_CATALOG_SQL))
    expected = json.loads(installed)
    expected = (
        expected + ADDED_FKS if upgrade else [row for row in expected if row not in ADDED_FKS]
    )
    if sorted(json.loads(current)) != sorted(expected):
        raise ValueError("unexpected maintenance foreign key changes")
    connection.execute(
        sa.text(
            "UPDATE maintenance_schema SET installed_definition=:catalog WHERE name='foreign_keys'"
        ),
        {"catalog": current},
    )


def _maintenance_memberships(upgrade: bool) -> None:
    """Extend the frozen deletion allowlist and exact-row ownership resolver."""
    changes = (
        (
            "verboflex_maintenance_authorize",
            "NEW.table_name NOT IN (",
            "NEW.table_name NOT IN ('product_members',",
        ),
        (
            "verboflex_maintenance_row_owner",
            "BEGIN CASE tab ",
            "BEGIN CASE tab "
            "WHEN 'product_members' THEN SELECT t.product_id INTO result FROM product_members t "
            "WHERE t.product_id=(row_key->>'product_id')::uuid "
            "AND t.user_id=(row_key->>'user_id')::uuid; ",
        ),
    )
    connection = op.get_bind()
    for name, before, after in changes:
        installed, current = connection.execute(
            sa.text(
                "SELECT installed_definition, pg_get_functiondef(to_regproc(:name)) "
                "FROM maintenance_schema WHERE name=:name"
            ),
            {"name": name},
        ).one()
        old, new = (before, after) if upgrade else (after, before)
        if current != installed or current.count(old) != 1:
            raise ValueError("unexpected maintenance membership guard definition")
        op.execute(current.replace(old, new, 1))
        connection.execute(
            sa.text(
                "UPDATE maintenance_schema SET installed_definition="
                "pg_get_functiondef(to_regproc(:name)) WHERE name=:name"
            ),
            {"name": name},
        )


def upgrade() -> None:
    op.add_column(
        "submission_reviews", sa.Column("membership_version", sa.String(80), nullable=True)
    )
    op.execute(
        "\nCREATE TABLE product_members (\n\tproduct_id UUID NOT NULL, \n\tuser_id UUID NOT NULL, \n\trole VARCHAR(32) NOT NULL, \n\tactive BOOLEAN DEFAULT 'true' NOT NULL, \n\tversion UUID NOT NULL, \n\tCONSTRAINT pk_product_members PRIMARY KEY (product_id, user_id), \n\tCONSTRAINT ck_product_members_role CHECK (role IN ('viewer','translator','product_manager_reviewer','product_owner')), \n\tCONSTRAINT fk_product_members_product_id_products FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_product_members_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("CREATE INDEX ix_product_members_user ON product_members (user_id, product_id)")
    op.execute(
        "\nCREATE TABLE product_team_events (\n\tid UUID NOT NULL, \n\tactor_id UUID NOT NULL, \n\tproduct_id UUID NOT NULL, \n\tsubject_id UUID NOT NULL, \n\taction VARCHAR(32) NOT NULL, \n\tprevious_role VARCHAR(32), \n\trole VARCHAR(32), \n\toccurred_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, \n\tCONSTRAINT pk_product_team_events PRIMARY KEY (id)\n)\n\n"
    )
    op.execute(
        "CREATE INDEX ix_product_team_events_product ON product_team_events (product_id, occurred_at)"
    )
    # Preserve current access without introducing global operational grants.
    op.execute("""INSERT INTO product_members(product_id,user_id,role,active,version)
        SELECT p.id,u.id, CASE WHEN EXISTS(SELECT 1 FROM user_roles ur JOIN roles r ON r.id=ur.role_id WHERE ur.user_id=u.id AND r.name IN ('admin','product_manager_reviewer')) THEN 'product_manager_reviewer'
          WHEN EXISTS(SELECT 1 FROM user_roles ur JOIN roles r ON r.id=ur.role_id WHERE ur.user_id=u.id AND r.name='translator') THEN 'translator' ELSE 'viewer' END, true, gen_random_uuid()
        FROM users u CROSS JOIN products p WHERE p.deleted_at IS NULL""")
    _catalog(True)
    _maintenance_memberships(True)


def downgrade() -> None:
    # Refuse loss of team decisions or a rollback that broadens delegated access.
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM product_team_events)")):
        raise ValueError("product membership has activity; restore a reviewed backup to downgrade")
    _maintenance_memberships(False)
    op.drop_column("submission_reviews", "membership_version")
    op.drop_table("product_members")
    op.drop_table("product_team_events")
    _catalog(False)
