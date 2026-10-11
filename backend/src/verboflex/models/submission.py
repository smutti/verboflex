"""Durable reviews, frozen change sets, and append-only provider evidence."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from verboflex.db.base import Base


class SubmissionReview(Base):
    __tablename__ = "submission_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "revision_id"],
            ["product_revisions.product_id", "product_revisions.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("state IN ('queued','running','ready','failed')", name="state_value"),
        CheckConstraint("attempt >= 1", name="attempt_positive"),
        CheckConstraint("octet_length(prepared_payload) <= 134217728", name="payload_bound"),
        CheckConstraint("(state = 'ready') = (prepared_payload IS NOT NULL)", name="ready_payload"),
        CheckConstraint(
            "(state IN ('ready','failed')) = (finished_at IS NOT NULL)", name="terminal_time"
        ),
        Index(
            "ix_submission_reviews_actor_product_digest", "actor_id", "product_id", "input_digest"
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    actor_token_version: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    revision_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    selection: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    input_digest: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16), default="queued")
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    error_code: Mapped[str | None] = mapped_column(String(64))
    prepared_payload: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SubmissionBatch(Base):
    __tablename__ = "submission_batches"
    __table_args__ = (
        UniqueConstraint("actor_id", "product_id", "request_key", name="uq_submission_batch_key"),
        UniqueConstraint("review_id", name="uq_submission_batch_review"),
        ForeignKeyConstraint(
            ["product_id", "revision_id"],
            ["product_revisions.product_id", "product_revisions.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("review_attempt >= 1", name="attempt_positive"),
        CheckConstraint("request_digest ~ '^[0-9a-f]{64}$'", name="request_digest"),
        CheckConstraint("content_digest ~ '^[0-9a-f]{64}$'", name="content_digest"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    revision_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    actor_token_version: Mapped[int] = mapped_column(Integer)
    review_id: Mapped[UUID] = mapped_column(
        ForeignKey("submission_reviews.id", ondelete="RESTRICT")
    )
    review_attempt: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    request_digest: Mapped[str] = mapped_column(String(64))
    content_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChangeSet(Base):
    __tablename__ = "change_sets"
    __table_args__ = (
        UniqueConstraint("batch_id", "repository_id", "target_branch", name="uq_change_set_group"),
        UniqueConstraint(
            "id",
            "repository_id",
            "provider_repository_id",
            "target_branch",
            name="uq_change_set_destination",
        ),
        CheckConstraint(
            "status IN ('queued','running','reconciling','blocked','failed','succeeded',"
            "'needs_attention','resolved')",
            name="status_value",
        ),
        CheckConstraint(
            "stage IN ('branch','commit','pull_request','complete')", name="stage_value"
        ),
        CheckConstraint(
            "attempt >= 1 AND execution_fence >= 1 AND current_proof_sequence >= 1",
            name="positive_counters",
        ),
        CheckConstraint("dispatch_count >= 0", name="dispatch_count"),
        CheckConstraint(
            "manifest_digest ~ '^[0-9a-f]{64}$' AND original_proof_digest ~ '^[0-9a-f]{64}$'",
            name="digests",
        ),
        CheckConstraint("target_head ~ '^[0-9a-f]{40}$'", name="target_head"),
        CheckConstraint(
            "source_branch = 'verboflex/change-set-' || id::text", name="source_branch"
        ),
        CheckConstraint(
            "original_proof_digest = encode(sha256(original_prepared_payload),'hex')",
            name="original_proof_digest",
        ),
        CheckConstraint(
            "octet_length(original_prepared_payload) <= 134217728", name="payload_bound"
        ),
        CheckConstraint(
            "proposal_count BETWEEN 1 AND 100 AND value_count BETWEEN 1 AND 5000 "
            "AND file_count BETWEEN 1 AND 500",
            name="counts",
        ),
        Index("ix_change_sets_dispatch", "dispatch_pending", "created_at"),
        Index("ix_change_sets_lease", "lease_expires_at"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    batch_id: Mapped[UUID] = mapped_column(ForeignKey("submission_batches.id", ondelete="RESTRICT"))
    repository_id: Mapped[UUID] = mapped_column(ForeignKey("repositories.id", ondelete="RESTRICT"))
    provider_repository_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    workspace: Mapped[str] = mapped_column(String(100))
    repository_slug: Mapped[str] = mapped_column(String(100))
    target_branch: Mapped[str] = mapped_column(String(255))
    target_head: Mapped[str] = mapped_column(String(40))
    source_branch: Mapped[str] = mapped_column(String(255))
    manifest_digest: Mapped[str] = mapped_column(String(64))
    original_proof_digest: Mapped[str] = mapped_column(String(64))
    original_prepared_payload: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    proposal_count: Mapped[int] = mapped_column(Integer)
    value_count: Mapped[int] = mapped_column(Integer)
    file_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    stage: Mapped[str] = mapped_column(String(16), default="branch")
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    execution_fence: Mapped[int] = mapped_column(Integer, default=1)
    owner_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatch_pending: Mapped[bool] = mapped_column(Boolean, default=True)
    dispatch_count: Mapped[int] = mapped_column(Integer, default=0)
    last_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_proof_sequence: Mapped[int] = mapped_column(Integer, default=1)
    branch_commit: Mapped[str | None] = mapped_column(String(40))
    commit_hash: Mapped[str | None] = mapped_column(String(40))
    pr_id: Mapped[int | None] = mapped_column(BigInteger)
    pr_url: Mapped[str | None] = mapped_column(String(4096))
    pr_state: Mapped[str | None] = mapped_column(String(16))
    pr_target_commit: Mapped[str | None] = mapped_column(String(40))
    pr_tracking: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claims_released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChangeSetItem(Base):
    __tablename__ = "change_set_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["change_set_id", "repository_id", "provider_repository_id", "target_branch"],
            [
                "change_sets.id",
                "change_sets.repository_id",
                "change_sets.provider_repository_id",
                "change_sets.target_branch",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "proposal_id",
            "proposal_version",
            "provider_repository_id",
            "target_branch",
            name="uq_change_set_proposal_claim",
        ),
        CheckConstraint("proposal_version BETWEEN 1 AND 9007199254740991", name="version_range"),
        CheckConstraint(
            "jsonb_typeof(members) = 'array' AND jsonb_array_length(members) BETWEEN 1 AND 5000 "
            "AND octet_length(members::text) <= 134217728",
            name="members_bound",
        ),
    )
    change_set_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    proposal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    proposal_version: Mapped[int] = mapped_column(BigInteger)
    repository_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    provider_repository_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    target_branch: Mapped[str] = mapped_column(String(255))
    key_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    language: Mapped[str] = mapped_column(String(64))
    members: Mapped[list[dict[str, object]]] = mapped_column(JSONB, deferred=True)


PATH_DIGEST = "sha256(replace(path, chr(92), chr(92)||chr(92))::bytea)"


class ChangeSetFile(Base):
    __tablename__ = "change_set_files"
    __table_args__ = (
        ForeignKeyConstraint(
            ["change_set_id", "repository_id", "provider_repository_id", "target_branch"],
            [
                "change_sets.id",
                "change_sets.repository_id",
                "change_sets.provider_repository_id",
                "change_sets.target_branch",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("change_set_id", "path_digest", name="uq_change_set_file_path"),
        Index(
            "uq_change_set_active_file",
            "provider_repository_id",
            "target_branch",
            "path_digest",
            unique=True,
            postgresql_where=text("active_claim"),
        ),
        CheckConstraint("char_length(path) BETWEEN 1 AND 4096", name="path_bound"),
        CheckConstraint(
            "octet_length(original_bytes) <= 1048576 AND octet_length(content) <= 1048576",
            name="bytes_bound",
        ),
        CheckConstraint(
            "before_sha256 = encode(sha256(original_bytes),'hex') "
            "AND after_sha256 = encode(sha256(content),'hex')",
            name="bytes_hashes",
        ),
        CheckConstraint("attributes IN ('[]'::jsonb, '[\"binary\"]'::jsonb)", name="attributes"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    change_set_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    repository_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    provider_repository_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    target_branch: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(Text)
    path_digest: Mapped[bytes] = mapped_column(LargeBinary, Computed(PATH_DIGEST, persisted=True))
    original_bytes: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    before_sha256: Mapped[str] = mapped_column(String(64))
    after_sha256: Mapped[str] = mapped_column(String(64))
    attributes: Mapped[list[str]] = mapped_column(JSONB)
    active_claim: Mapped[bool] = mapped_column(Boolean, default=True)


class ChangeSetProof(Base):
    __tablename__ = "change_set_proofs"
    __table_args__ = (
        CheckConstraint("sequence >= 1 AND connection_generation >= 1", name="positive_counters"),
        CheckConstraint("octet_length(prepared_payload) <= 134217728", name="payload_bound"),
        CheckConstraint(
            "proof_digest = encode(sha256(prepared_payload),'hex')", name="proof_digest"
        ),
    )
    change_set_id: Mapped[UUID] = mapped_column(
        ForeignKey("change_sets.id", ondelete="RESTRICT"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    connection_generation: Mapped[int] = mapped_column(Integer)
    proof_digest: Mapped[str] = mapped_column(String(64))
    prepared_payload: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChangeSetEvent(Base):
    __tablename__ = "change_set_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["change_set_id", "proof_sequence"],
            ["change_set_proofs.change_set_id", "change_set_proofs.sequence"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "event_kind IN ('send_intent','observation','reauthorization',"
            "'finalization','pr_status')",
            name="event_kind",
        ),
        CheckConstraint("step IN ('branch','commit','pull_request','authority')", name="step"),
        CheckConstraint(
            "outcome IN ('intent','verified','not_sent','unknown','conflict')", name="outcome"
        ),
        CheckConstraint("attempt >= 1 AND execution_fence >= 1", name="positive_counters"),
        CheckConstraint("request_digest ~ '^[0-9a-f]{64}$'", name="request_digest"),
        CheckConstraint(
            "jsonb_typeof(receipt) = 'object' AND octet_length(receipt::text) <= 65536",
            name="receipt_bound",
        ),
        CheckConstraint(
            "provider_status IS NULL OR provider_status BETWEEN 100 AND 599", name="provider_status"
        ),
        Index(
            "uq_change_set_send_intent",
            "change_set_id",
            "attempt",
            "step",
            unique=True,
            postgresql_where=text("event_kind = 'send_intent'"),
        ),
        Index("ix_change_set_events_history", "change_set_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    change_set_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    attempt: Mapped[int] = mapped_column(Integer)
    execution_fence: Mapped[int] = mapped_column(Integer)
    proof_sequence: Mapped[int] = mapped_column(Integer)
    event_kind: Mapped[str] = mapped_column(String(24))
    step: Mapped[str] = mapped_column(String(16))
    outcome: Mapped[str] = mapped_column(String(16))
    request_digest: Mapped[str] = mapped_column(String(64))
    receipt: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    provider_status: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
