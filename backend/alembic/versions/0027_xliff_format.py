"""Permit canonical XLIFF values without weakening existing format checks."""

import sqlalchemy as sa

from alembic import op

revision = "0027_xliff_format"
down_revision = "0026_duplicate_quarantine_layout"
branch_labels = None
depends_on = None

_OLD_FORMATS = "format IN ('android_xml', 'qt_ts', 'json', 'ios_strings')"
_NEW_FORMATS = "format IN ('android_xml', 'qt_ts', 'json', 'ios_strings', 'xliff')"
_CONSTRAINTS = (
    ("staged_translation_values", "ck_staged_translation_values_format_value"),
    ("translation_value_locators", "ck_translation_value_locators_format_value"),
)


def _replace_constraints(expression: str) -> None:
    for table, constraint in _CONSTRAINTS:
        op.drop_constraint(op.f(constraint), table, type_="check")
        op.create_check_constraint(op.f(constraint), table, expression)


def upgrade() -> None:
    _replace_constraints(_NEW_FORMATS)


def downgrade() -> None:
    connection = op.get_bind()
    for table, _constraint in _CONSTRAINTS:
        exists = connection.execute(
            sa.text(f"SELECT EXISTS (SELECT 1 FROM {table} WHERE format = 'xliff')")
        ).scalar_one()
        if exists:
            raise RuntimeError("cannot downgrade while XLIFF rows exist")
    _replace_constraints(_OLD_FORMATS)
