"""Require source references to be inserted while their execution is running.

Revision ID: 0014_import_source_reference_insert_guard
Revises: 0013_import_rewrite_proposals
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014_import_source_reference_insert_guard"
down_revision: str | None = "0013_import_rewrite_proposals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RUNNING_IMPORT_SOURCE_REFERENCE_GUARD = """
CREATE OR REPLACE FUNCTION verboflex_guard_import_source_reference()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    execution_state text;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT state INTO execution_state
        FROM import_executions
        WHERE id = NEW.execution_id
        FOR UPDATE;

        IF execution_state IN ('succeeded', 'failed') THEN
            RAISE EXCEPTION 'terminal import source reference is immutable'
                USING ERRCODE = '55000';
        END IF;
        IF execution_state IS DISTINCT FROM 'running' THEN
            RAISE EXCEPTION 'import source reference insert requires running execution'
                USING ERRCODE = '55000';
        END IF;
    ELSE
        IF TG_OP = 'UPDATE'
           AND NEW.execution_id IS DISTINCT FROM OLD.execution_id THEN
            RAISE EXCEPTION 'import source reference execution identity is immutable'
                USING ERRCODE = '55000';
        END IF;

        SELECT state INTO execution_state
        FROM import_executions
        WHERE id = OLD.execution_id
        FOR UPDATE;

        IF execution_state IN ('succeeded', 'failed') THEN
            RAISE EXCEPTION 'terminal import source reference is immutable'
                USING ERRCODE = '55000';
        END IF;
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM import_executions AS execution
        JOIN import_jobs AS job ON job.id = execution.import_job_id
        JOIN product_mapping_repository_sides AS side
          ON side.mapping_id = job.mapping_id
         AND side.role = NEW.repository_side
         AND side.repository_id = NEW.repository_id
         AND side.source_branch = NEW.source_branch
        WHERE execution.id = NEW.execution_id
    ) THEN
        RAISE EXCEPTION 'import source reference ownership violation'
            USING ERRCODE = '23503';
    END IF;

    RETURN NEW;
END;
$$
"""


LEGACY_IMPORT_SOURCE_REFERENCE_GUARD = """
CREATE OR REPLACE FUNCTION verboflex_guard_import_source_reference()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    execution_state text;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        SELECT state INTO execution_state
        FROM import_executions
        WHERE id = OLD.execution_id;

        IF execution_state IN ('succeeded', 'failed') THEN
            RAISE EXCEPTION 'terminal import source reference is immutable'
                USING ERRCODE = '55000';
        END IF;
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM import_executions AS execution
        JOIN import_jobs AS job ON job.id = execution.import_job_id
        JOIN product_mapping_repository_sides AS side
          ON side.mapping_id = job.mapping_id
         AND side.role = NEW.repository_side
         AND side.repository_id = NEW.repository_id
         AND side.source_branch = NEW.source_branch
        WHERE execution.id = NEW.execution_id
    ) THEN
        RAISE EXCEPTION 'import source reference ownership violation'
            USING ERRCODE = '23503';
    END IF;

    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    """Serialize source reference inserts with execution finalization."""
    op.execute(RUNNING_IMPORT_SOURCE_REFERENCE_GUARD)


def downgrade() -> None:
    """Restore the original source-reference guard."""
    op.execute(LEGACY_IMPORT_SOURCE_REFERENCE_GUARD)
