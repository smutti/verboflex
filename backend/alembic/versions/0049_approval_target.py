"""Retain verified target-branch presence for the current proposal version."""

import sqlalchemy as sa

from alembic import op

revision = "0049_approval_target"
down_revision = "0048_branch_mappings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("translation_proposals", sa.Column("target_branch", sa.String(255)))
    op.add_column("translation_proposals", sa.Column("target_commit_hash", sa.String(40)))
    # Existing approvals must be checked too; never infer integration from a PR state.
    op.execute("""UPDATE translation_proposals p SET target_branch=w.target_branch
        FROM review_activities a JOIN branch_jobs j ON j.activity_id=a.id
        JOIN branch_workflows w ON w.id=j.workflow_id
        WHERE a.proposal_id=p.id AND a.proposal_version=p.version
          AND p.state='approved' AND j.kind='commit'""")


def downgrade() -> None:
    op.drop_column("translation_proposals", "target_commit_hash")
    op.drop_column("translation_proposals", "target_branch")
