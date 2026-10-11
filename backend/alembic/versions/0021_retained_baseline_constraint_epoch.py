"""Permit constraint epoch increments on an authentic retained dataset.

Revision ID: 0021_retained_constraint_epoch
Revises: 0020_bounded_key_identities
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0021_retained_constraint_epoch"
down_revision: str | None = "0020_bounded_key_identities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Keep revision 0016's activation predicate intact, including on downgrade.
ORIGINAL_SCOPE_ACTIVATION_GUARD = """
CREATE OR REPLACE FUNCTION verboflex_guard_localization_scope_activation()
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


RETAINED_EPOCH_GUARD = """
    -- An epoch-only constraint change does not activate the refresh candidate.
    -- Compare the complete row except these two mutable metadata fields so a
    -- future authority column cannot silently inherit this exception.
    IF TG_OP = 'UPDATE'
       AND NEW.dataset_version::bigint = OLD.dataset_version::bigint + 1
       AND (to_jsonb(NEW) - 'dataset_version' - 'updated_at')
           = (to_jsonb(OLD) - 'dataset_version' - 'updated_at')
       AND EXISTS (
        SELECT 1
        FROM import_executions AS execution
        JOIN import_jobs AS job
          ON job.id = execution.import_job_id
         AND job.id = NEW.active_import_job_id
         AND job.active_baseline_execution_id = execution.id
         AND job.product_id = NEW.product_id
         AND job.revision_id = NEW.current_revision_id
        JOIN import_executions AS current_execution
          ON current_execution.id = job.current_execution_id
         AND current_execution.import_job_id = job.id
         AND current_execution.sequence >= execution.sequence
         AND (job.state, current_execution.state) IN (
             ('queued', 'queued'), ('running', 'running'),
             ('import_failed', 'failed'), ('current', 'succeeded')
         )
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
        RETURN NEW;
    END IF;

"""


def upgrade() -> None:
    op.execute(
        ORIGINAL_SCOPE_ACTIVATION_GUARD.replace(
            "    IF NOT EXISTS (", RETAINED_EPOCH_GUARD + "    IF NOT EXISTS (", 1
        )
    )


def downgrade() -> None:
    op.execute(ORIGINAL_SCOPE_ACTIVATION_GUARD)
