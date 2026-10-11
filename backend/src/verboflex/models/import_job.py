"""Durable logical imports, immutable executions, and source references."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from verboflex.db.base import Base


class ImportJob(Base):
    """One stable logical import owned by one published mapping."""

    __tablename__ = "import_jobs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued', 'running', 'current', 'import_failed')",
            name="state_value",
        ),
        CheckConstraint(
            "topology IN ('direct', 'separate')",
            name="topology_value",
        ),
        CheckConstraint("retry_count >= 0", name="retry_count_non_negative"),
        CheckConstraint(
            "(state IN ('queued', 'running', 'current') "
            "AND error_category IS NULL AND error_message IS NULL) OR "
            "(state = 'import_failed' AND error_category IS NOT NULL "
            "AND error_message IS NOT NULL)",
            name="state_error_payload",
        ),
        CheckConstraint(
            "state <> 'current' OR active_baseline_execution_id IS NOT NULL",
            name="current_requires_baseline",
        ),
        UniqueConstraint(
            "mapping_id",
            name="uq_import_jobs_mapping",
        ),
        UniqueConstraint(
            "id",
            "mapping_id",
            name="uq_import_jobs_id_mapping",
        ),
        ForeignKeyConstraint(
            ["product_id", "revision_id"],
            ["product_revisions.product_id", "product_revisions.id"],
            name="fk_import_jobs_owned_revision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["revision_id", "mapping_id"],
            ["product_repository_mappings.revision_id", "product_repository_mappings.id"],
            name="fk_import_jobs_owned_mapping",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["current_execution_id", "id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_import_jobs_current_execution",
            ondelete="NO ACTION",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["active_baseline_execution_id", "id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_import_jobs_active_baseline",
            ondelete="NO ACTION",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        Index(
            "ix_import_jobs_revision_mapping",
            "revision_id",
            "mapping_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    product_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    revision_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    mapping_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    topology: Mapped[str] = mapped_column(String(16), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    current_execution_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    active_baseline_execution_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    error_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(256), nullable=True)
    latest_execution_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ImportExecution(Base):
    """One immutable execution identity behind the stable logical import."""

    __tablename__ = "import_executions"
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed')",
            name="state_value",
        ),
        CheckConstraint("sequence > 0", name="positive_sequence"),
        CheckConstraint(
            "connection_generation >= 0",
            name="connection_generation_non_negative",
        ),
        CheckConstraint(
            "(state = 'queued' AND started_at IS NULL AND finished_at IS NULL) OR "
            "(state = 'running' AND started_at IS NOT NULL AND finished_at IS NULL) OR "
            "(state IN ('succeeded', 'failed') AND started_at IS NOT NULL "
            "AND finished_at IS NOT NULL)",
            name="state_timestamps",
        ),
        UniqueConstraint(
            "import_job_id",
            "sequence",
            name="uq_import_executions_job_sequence",
        ),
        UniqueConstraint(
            "id",
            "import_job_id",
            name="uq_import_executions_id_job",
        ),
        Index(
            "ix_import_executions_job_sequence",
            "import_job_id",
            "sequence",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    import_job_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("import_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    connection_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ImportSourceReference(Base):
    """One ordered content digest from an exact commit, never source bytes."""

    __tablename__ = "import_source_references"
    __table_args__ = (
        CheckConstraint("position >= 0", name="position_non_negative"),
        CheckConstraint(
            "repository_side IN ('direct', 'keys', 'translations')",
            name="repository_side_value",
        ),
        CheckConstraint(
            "char_length(source_branch) BETWEEN 1 AND 255",
            name="source_branch_length",
        ),
        CheckConstraint(
            "char_length(commit_hash) = 40 AND commit_hash ~ '^[0-9a-f]{40}$'",
            name="commit_hash_sha1",
        ),
        CheckConstraint(
            "char_length(path) BETWEEN 1 AND 4096",
            name="path_length",
        ),
        CheckConstraint("size_bytes >= 0", name="size_non_negative"),
        CheckConstraint(
            "char_length(sha256) = 64 AND sha256 ~ '^[0-9a-f]{64}$'",
            name="sha256_digest",
        ),
        UniqueConstraint(
            "execution_id",
            "repository_side",
            "path",
            name="uq_import_source_references_side_path",
        ),
        Index(
            "ix_import_source_references_execution_side_position",
            "execution_id",
            "repository_side",
            "position",
        ),
    )

    execution_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("import_executions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_side: Mapped[str] = mapped_column(String(16), nullable=False)
    repository_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    commit_hash: Mapped[str] = mapped_column(String(40), nullable=False)
    path: Mapped[str] = mapped_column(String(4096), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class ImportRewriteProposal(Base):
    """Complete mapping-scoped authority to replace one import baseline."""

    __tablename__ = "import_rewrite_proposals"
    __table_args__ = (
        CheckConstraint("revision_version > 0", name="positive_revision_version"),
        CheckConstraint(
            "connection_generation >= 0",
            name="connection_generation_non_negative",
        ),
        CheckConstraint(
            "topology IN ('direct', 'separate')",
            name="topology_value",
        ),
        CheckConstraint("complete", name="complete_authority"),
        CheckConstraint(
            "char_length(digest) = 64 AND digest ~ '^[0-9a-f]{64}$'",
            name="digest_sha256",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'superseded')",
            name="status_value",
        ),
        CheckConstraint(
            "(status = 'pending' AND resolved_at IS NULL AND confirmed_by IS NULL) OR "
            "(status = 'superseded' AND resolved_at IS NOT NULL "
            "AND confirmed_by IS NULL) OR "
            "(status = 'confirmed' AND resolved_at IS NOT NULL "
            "AND confirmed_by IS NOT NULL)",
            name="status_payload",
        ),
        CheckConstraint(
            "(topology = 'direct' "
            "AND direct_repository_id IS NOT NULL "
            "AND direct_old_commit_hash IS NOT NULL "
            "AND direct_new_commit_hash IS NOT NULL "
            "AND keys_repository_id IS NULL "
            "AND keys_old_commit_hash IS NULL "
            "AND keys_new_commit_hash IS NULL "
            "AND translations_repository_id IS NULL "
            "AND translations_old_commit_hash IS NULL "
            "AND translations_new_commit_hash IS NULL) OR "
            "(topology = 'separate' "
            "AND direct_repository_id IS NULL "
            "AND direct_old_commit_hash IS NULL "
            "AND direct_new_commit_hash IS NULL "
            "AND keys_repository_id IS NOT NULL "
            "AND keys_old_commit_hash IS NOT NULL "
            "AND keys_new_commit_hash IS NOT NULL "
            "AND translations_repository_id IS NOT NULL "
            "AND translations_old_commit_hash IS NOT NULL "
            "AND translations_new_commit_hash IS NOT NULL)",
            name="topology_commits",
        ),
        CheckConstraint(
            "(direct_old_commit_hash IS NULL OR "
            "(char_length(direct_old_commit_hash) = 40 "
            "AND direct_old_commit_hash ~ '^[0-9a-f]{40}$')) AND "
            "(direct_new_commit_hash IS NULL OR "
            "(char_length(direct_new_commit_hash) = 40 "
            "AND direct_new_commit_hash ~ '^[0-9a-f]{40}$')) AND "
            "(keys_old_commit_hash IS NULL OR "
            "(char_length(keys_old_commit_hash) = 40 "
            "AND keys_old_commit_hash ~ '^[0-9a-f]{40}$')) AND "
            "(keys_new_commit_hash IS NULL OR "
            "(char_length(keys_new_commit_hash) = 40 "
            "AND keys_new_commit_hash ~ '^[0-9a-f]{40}$')) AND "
            "(translations_old_commit_hash IS NULL OR "
            "(char_length(translations_old_commit_hash) = 40 "
            "AND translations_old_commit_hash ~ '^[0-9a-f]{40}$')) AND "
            "(translations_new_commit_hash IS NULL OR "
            "(char_length(translations_new_commit_hash) = 40 "
            "AND translations_new_commit_hash ~ '^[0-9a-f]{40}$'))",
            name="commit_hashes_sha1",
        ),
        ForeignKeyConstraint(
            ["product_id", "revision_id"],
            ["product_revisions.product_id", "product_revisions.id"],
            name="fk_import_rewrite_proposals_owned_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["revision_id", "mapping_id"],
            ["product_repository_mappings.revision_id", "product_repository_mappings.id"],
            name="fk_import_rewrite_proposals_owned_mapping",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["old_baseline_execution_id", "import_job_id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_import_rewrite_proposals_old_baseline",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["proposed_execution_id", "import_job_id"],
            ["import_executions.id", "import_executions.import_job_id"],
            name="fk_import_rewrite_proposals_proposed_execution",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_import_rewrite_proposals_pending_job",
            "import_job_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "ix_import_rewrite_proposals_mapping_status",
            "mapping_id",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    import_job_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("import_jobs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    revision_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    revision_version: Mapped[int] = mapped_column(Integer, nullable=False)
    mapping_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    topology: Mapped[str] = mapped_column(String(16), nullable=False)
    connection_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_execution_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    old_baseline_execution_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    direct_repository_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="RESTRICT"),
        nullable=True,
    )
    direct_old_commit_hash: Mapped[str | None] = mapped_column(String(40), nullable=True)
    direct_new_commit_hash: Mapped[str | None] = mapped_column(String(40), nullable=True)
    keys_repository_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="RESTRICT"),
        nullable=True,
    )
    keys_old_commit_hash: Mapped[str | None] = mapped_column(String(40), nullable=True)
    keys_new_commit_hash: Mapped[str | None] = mapped_column(String(40), nullable=True)
    translations_repository_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="RESTRICT"),
        nullable=True,
    )
    translations_old_commit_hash: Mapped[str | None] = mapped_column(String(40), nullable=True)
    translations_new_commit_hash: Mapped[str | None] = mapped_column(String(40), nullable=True)
    complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ImportRewriteDelta(Base):
    """One immutable ordered metadata-only row in a complete rewrite proposal."""

    __tablename__ = "import_rewrite_deltas"
    __table_args__ = (
        CheckConstraint("position >= 0", name="position_non_negative"),
        CheckConstraint(
            "repository_side IN ('direct', 'keys', 'translations')",
            name="repository_side_value",
        ),
        CheckConstraint(
            "change IN ('added', 'modified', 'removed')",
            name="change_value",
        ),
        CheckConstraint("char_length(path) BETWEEN 1 AND 4096", name="path_length"),
        UniqueConstraint(
            "proposal_id",
            "repository_side",
            "path",
            name="uq_import_rewrite_deltas_side_path",
        ),
    )

    proposal_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("import_rewrite_proposals.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_side: Mapped[str] = mapped_column(String(16), nullable=False)
    change: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(4096), nullable=False)
