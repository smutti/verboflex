"""Freeze explicit submission batches, destination claims and external-effect evidence.

Revision ID: 0031_change_sets
Revises: 0030_submission_reviews
"""

# ruff: noqa: E501

import sqlalchemy as sa

from alembic import op

revision = "0031_change_sets"
down_revision = "0030_submission_reviews"
branch_labels = None
depends_on = None

# Frozen DDL: no imports from evolving application model definitions.
DDL = (
    """CREATE TABLE submission_batches (
    id UUID NOT NULL,
    product_id UUID NOT NULL,
    revision_id UUID NOT NULL,
    actor_id UUID NOT NULL,
    actor_token_version INTEGER NOT NULL,
    review_id UUID NOT NULL,
    review_attempt INTEGER NOT NULL,
    request_key UUID NOT NULL,
    request_digest VARCHAR(64) NOT NULL,
    content_digest VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_submission_batches PRIMARY KEY (id),
    CONSTRAINT uq_submission_batch_key UNIQUE (actor_id, product_id, request_key),
    CONSTRAINT uq_submission_batch_review UNIQUE (review_id),
    CONSTRAINT fk_submission_batches_product_id_product_revisions FOREIGN KEY(product_id, revision_id) REFERENCES product_revisions (product_id, id) ON DELETE RESTRICT,
    CONSTRAINT ck_submission_batches_attempt_positive CHECK (review_attempt >= 1),
    CONSTRAINT ck_submission_batches_request_digest CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_submission_batches_content_digest CHECK (content_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT fk_submission_batches_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_submission_batches_review_id_submission_reviews FOREIGN KEY(review_id) REFERENCES submission_reviews (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE change_sets (
    id UUID NOT NULL,
    batch_id UUID NOT NULL,
    repository_id UUID NOT NULL,
    provider_repository_id UUID NOT NULL,
    workspace VARCHAR(100) NOT NULL,
    repository_slug VARCHAR(100) NOT NULL,
    target_branch VARCHAR(255) NOT NULL,
    target_head VARCHAR(40) NOT NULL,
    source_branch VARCHAR(255) NOT NULL,
    manifest_digest VARCHAR(64) NOT NULL,
    original_proof_digest VARCHAR(64) NOT NULL,
    original_prepared_payload BYTEA NOT NULL,
    proposal_count INTEGER NOT NULL,
    value_count INTEGER NOT NULL,
    file_count INTEGER NOT NULL,
    status VARCHAR(24) NOT NULL,
    stage VARCHAR(16) NOT NULL,
    attempt INTEGER NOT NULL,
    execution_fence INTEGER NOT NULL,
    owner_id UUID,
    lease_expires_at TIMESTAMP WITH TIME ZONE,
    dispatch_pending BOOLEAN NOT NULL,
    dispatch_count INTEGER NOT NULL,
    last_dispatched_at TIMESTAMP WITH TIME ZONE,
    current_proof_sequence INTEGER NOT NULL,
    branch_commit VARCHAR(40),
    commit_hash VARCHAR(40),
    pr_id BIGINT,
    pr_url VARCHAR(4096),
    pr_state VARCHAR(16),
    pr_target_commit VARCHAR(40),
    error_code VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    finished_at TIMESTAMP WITH TIME ZONE,
    claims_released_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT pk_change_sets PRIMARY KEY (id),
    CONSTRAINT uq_change_set_group UNIQUE (batch_id, repository_id, target_branch),
    CONSTRAINT uq_change_set_destination UNIQUE (id, repository_id, provider_repository_id, target_branch),
    CONSTRAINT ck_change_sets_status_value CHECK (status IN ('queued','running','reconciling','blocked','failed','succeeded','needs_attention','resolved')),
    CONSTRAINT ck_change_sets_stage_value CHECK (stage IN ('branch','commit','pull_request','complete')),
    CONSTRAINT ck_change_sets_positive_counters CHECK (attempt >= 1 AND execution_fence >= 1 AND current_proof_sequence >= 1),
    CONSTRAINT ck_change_sets_dispatch_count CHECK (dispatch_count >= 0),
    CONSTRAINT ck_change_sets_digests CHECK (manifest_digest ~ '^[0-9a-f]{64}$' AND original_proof_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_change_sets_target_head CHECK (target_head ~ '^[0-9a-f]{40}$'),
    CONSTRAINT ck_change_sets_source_branch CHECK (source_branch = 'verboflex/change-set-' || id::text),
    CONSTRAINT ck_change_sets_original_proof_digest CHECK (original_proof_digest = encode(sha256(original_prepared_payload),'hex')),
    CONSTRAINT ck_change_sets_payload_bound CHECK (octet_length(original_prepared_payload) <= 134217728),
    CONSTRAINT ck_change_sets_counts CHECK (proposal_count BETWEEN 1 AND 100 AND value_count BETWEEN 1 AND 5000 AND file_count BETWEEN 1 AND 500),
    CONSTRAINT fk_change_sets_batch_id_submission_batches FOREIGN KEY(batch_id) REFERENCES submission_batches (id) ON DELETE RESTRICT,
    CONSTRAINT fk_change_sets_repository_id_repositories FOREIGN KEY(repository_id) REFERENCES repositories (id) ON DELETE RESTRICT
)""",
    """CREATE INDEX ix_change_sets_dispatch ON change_sets (dispatch_pending, created_at)""",
    """CREATE INDEX ix_change_sets_lease ON change_sets (lease_expires_at)""",
    """CREATE TABLE change_set_items (
    change_set_id UUID NOT NULL,
    proposal_id UUID NOT NULL,
    proposal_version BIGINT NOT NULL,
    repository_id UUID NOT NULL,
    provider_repository_id UUID NOT NULL,
    target_branch VARCHAR(255) NOT NULL,
    key_id UUID NOT NULL,
    language VARCHAR(64) NOT NULL,
    members JSONB NOT NULL,
    CONSTRAINT pk_change_set_items PRIMARY KEY (change_set_id, proposal_id),
    CONSTRAINT fk_change_set_items_change_set_id_change_sets FOREIGN KEY(change_set_id, repository_id, provider_repository_id, target_branch) REFERENCES change_sets (id, repository_id, provider_repository_id, target_branch) ON DELETE RESTRICT,
    CONSTRAINT uq_change_set_proposal_claim UNIQUE (proposal_id, proposal_version, provider_repository_id, target_branch),
    CONSTRAINT ck_change_set_items_version_range CHECK (proposal_version BETWEEN 1 AND 9007199254740991),
    CONSTRAINT ck_change_set_items_members_bound CHECK (jsonb_typeof(members) = 'array' AND jsonb_array_length(members) BETWEEN 1 AND 5000 AND octet_length(members::text) <= 134217728)
)""",
    """CREATE TABLE change_set_files (
    id UUID NOT NULL,
    change_set_id UUID NOT NULL,
    repository_id UUID NOT NULL,
    provider_repository_id UUID NOT NULL,
    target_branch VARCHAR(255) NOT NULL,
    path TEXT NOT NULL,
    path_digest BYTEA GENERATED ALWAYS AS (sha256(replace(path, chr(92), chr(92)||chr(92))::bytea)) STORED NOT NULL,
    original_bytes BYTEA NOT NULL,
    content BYTEA NOT NULL,
    before_sha256 VARCHAR(64) NOT NULL,
    after_sha256 VARCHAR(64) NOT NULL,
    attributes JSONB NOT NULL,
    active_claim BOOLEAN NOT NULL,
    CONSTRAINT pk_change_set_files PRIMARY KEY (id),
    CONSTRAINT fk_change_set_files_change_set_id_change_sets FOREIGN KEY(change_set_id, repository_id, provider_repository_id, target_branch) REFERENCES change_sets (id, repository_id, provider_repository_id, target_branch) ON DELETE RESTRICT,
    CONSTRAINT uq_change_set_file_path UNIQUE (change_set_id, path_digest),
    CONSTRAINT ck_change_set_files_path_bound CHECK (char_length(path) BETWEEN 1 AND 4096),
    CONSTRAINT ck_change_set_files_bytes_bound CHECK (octet_length(original_bytes) <= 1048576 AND octet_length(content) <= 1048576),
    CONSTRAINT ck_change_set_files_bytes_hashes CHECK (before_sha256 = encode(sha256(original_bytes),'hex') AND after_sha256 = encode(sha256(content),'hex')),
    CONSTRAINT ck_change_set_files_attributes CHECK (attributes IN ('[]'::jsonb, '["binary"]'::jsonb))
)""",
    """CREATE UNIQUE INDEX uq_change_set_active_file ON change_set_files (provider_repository_id, target_branch, path_digest) WHERE active_claim""",
    """CREATE TABLE change_set_proofs (
    change_set_id UUID NOT NULL,
    sequence INTEGER NOT NULL,
    connection_generation INTEGER NOT NULL,
    proof_digest VARCHAR(64) NOT NULL,
    prepared_payload BYTEA NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_change_set_proofs PRIMARY KEY (change_set_id, sequence),
    CONSTRAINT ck_change_set_proofs_positive_counters CHECK (sequence >= 1 AND connection_generation >= 1),
    CONSTRAINT ck_change_set_proofs_payload_bound CHECK (octet_length(prepared_payload) <= 134217728),
    CONSTRAINT ck_change_set_proofs_proof_digest CHECK (proof_digest = encode(sha256(prepared_payload),'hex')),
    CONSTRAINT fk_change_set_proofs_change_set_id_change_sets FOREIGN KEY(change_set_id) REFERENCES change_sets (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE change_set_events (
    id UUID NOT NULL,
    change_set_id UUID NOT NULL,
    attempt INTEGER NOT NULL,
    execution_fence INTEGER NOT NULL,
    proof_sequence INTEGER NOT NULL,
    event_kind VARCHAR(24) NOT NULL,
    step VARCHAR(16) NOT NULL,
    outcome VARCHAR(16) NOT NULL,
    request_digest VARCHAR(64) NOT NULL,
    receipt JSONB NOT NULL,
    provider_status INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_change_set_events PRIMARY KEY (id),
    CONSTRAINT fk_change_set_events_change_set_id_change_set_proofs FOREIGN KEY(change_set_id, proof_sequence) REFERENCES change_set_proofs (change_set_id, sequence) ON DELETE RESTRICT,
    CONSTRAINT ck_change_set_events_event_kind CHECK (event_kind IN ('send_intent','observation','reauthorization','finalization')),
    CONSTRAINT ck_change_set_events_step CHECK (step IN ('branch','commit','pull_request','authority')),
    CONSTRAINT ck_change_set_events_outcome CHECK (outcome IN ('intent','verified','not_sent','unknown','conflict')),
    CONSTRAINT ck_change_set_events_positive_counters CHECK (attempt >= 1 AND execution_fence >= 1),
    CONSTRAINT ck_change_set_events_request_digest CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_change_set_events_receipt_bound CHECK (jsonb_typeof(receipt) = 'object' AND octet_length(receipt::text) <= 65536),
    CONSTRAINT ck_change_set_events_provider_status CHECK (provider_status IS NULL OR provider_status BETWEEN 100 AND 599)
)""",
    """CREATE INDEX ix_change_set_events_history ON change_set_events (change_set_id, created_at, id)""",
    """CREATE UNIQUE INDEX uq_change_set_send_intent ON change_set_events (change_set_id, attempt, step) WHERE event_kind = 'send_intent'""",
    """CREATE FUNCTION verboflex_guard_submission_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'submission evidence is immutable'; END IF;
  IF TG_TABLE_NAME = 'change_sets' THEN
    IF ROW(NEW.id,NEW.batch_id,NEW.repository_id,NEW.provider_repository_id,NEW.workspace,NEW.repository_slug,NEW.target_branch,NEW.target_head,NEW.source_branch,NEW.manifest_digest,NEW.original_proof_digest,NEW.original_prepared_payload,NEW.proposal_count,NEW.value_count,NEW.file_count,NEW.created_at) IS DISTINCT FROM ROW(OLD.id,OLD.batch_id,OLD.repository_id,OLD.provider_repository_id,OLD.workspace,OLD.repository_slug,OLD.target_branch,OLD.target_head,OLD.source_branch,OLD.manifest_digest,OLD.original_proof_digest,OLD.original_prepared_payload,OLD.proposal_count,OLD.value_count,OLD.file_count,OLD.created_at) THEN
      RAISE EXCEPTION 'submission snapshot is immutable';
    END IF;
    IF NEW.attempt < OLD.attempt OR NEW.execution_fence < OLD.execution_fence OR NEW.current_proof_sequence < OLD.current_proof_sequence THEN
      RAISE EXCEPTION 'submission fence cannot regress';
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME = 'change_set_files' THEN
    IF ROW(NEW.id,NEW.change_set_id,NEW.repository_id,NEW.provider_repository_id,NEW.target_branch,NEW.path,NEW.original_bytes,NEW.content,NEW.before_sha256,NEW.after_sha256,NEW.attributes) IS DISTINCT FROM ROW(OLD.id,OLD.change_set_id,OLD.repository_id,OLD.provider_repository_id,OLD.target_branch,OLD.path,OLD.original_bytes,OLD.content,OLD.before_sha256,OLD.after_sha256,OLD.attributes) OR (NOT OLD.active_claim AND NEW.active_claim) THEN
      RAISE EXCEPTION 'submission file is immutable';
    END IF;
    IF OLD.active_claim AND NOT NEW.active_claim AND NOT EXISTS (
      SELECT 1 FROM change_sets WHERE id = OLD.change_set_id AND claims_released_at IS NOT NULL
      AND (status = 'resolved' OR pr_state IN ('MERGED','DECLINED','SUPERSEDED'))
    ) THEN RAISE EXCEPTION 'submission destination claim is unresolved'; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'submission evidence is immutable';
END $$""",
    """CREATE FUNCTION verboflex_guard_accepted_review() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.accepted_at IS NOT NULL THEN RAISE EXCEPTION 'accepted review is immutable'; END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  IF NEW.accepted_at IS NOT NULL AND (OLD.state <> 'ready' OR NEW.state <> 'ready' OR
    NEW.prepared_payload IS DISTINCT FROM OLD.prepared_payload OR NEW.selection IS DISTINCT FROM OLD.selection OR
    NEW.input_digest IS DISTINCT FROM OLD.input_digest OR NEW.actor_id IS DISTINCT FROM OLD.actor_id OR
    NEW.actor_token_version IS DISTINCT FROM OLD.actor_token_version OR NEW.product_id IS DISTINCT FROM OLD.product_id OR
    NEW.revision_id IS DISTINCT FROM OLD.revision_id OR NEW.attempt IS DISTINCT FROM OLD.attempt) THEN
    RAISE EXCEPTION 'accepted review authority changed';
  END IF;
  RETURN NEW;
END $$""",
)


def upgrade() -> None:
    if op.get_bind().scalar(sa.text("SHOW server_encoding")) != "UTF8":
        raise RuntimeError("submission path identities require a UTF8 database")
    op.add_column("submission_reviews", sa.Column("accepted_at", sa.DateTime(timezone=True)))
    for statement in DDL:
        op.execute(statement)
    for table in (
        "submission_batches",
        "change_sets",
        "change_set_items",
        "change_set_files",
        "change_set_proofs",
        "change_set_events",
    ):
        op.execute(
            f"CREATE TRIGGER {table}_frozen BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION verboflex_guard_submission_frozen()"
        )
    op.execute(
        "CREATE TRIGGER submission_reviews_accepted BEFORE UPDATE OR DELETE ON submission_reviews "
        "FOR EACH ROW EXECUTE FUNCTION verboflex_guard_accepted_review()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER submission_reviews_accepted ON submission_reviews")
    op.execute("DROP FUNCTION verboflex_guard_accepted_review()")
    for table in (
        "change_set_events",
        "change_set_proofs",
        "change_set_files",
        "change_set_items",
        "change_sets",
        "submission_batches",
    ):
        op.drop_table(table)
    op.execute("DROP FUNCTION verboflex_guard_submission_frozen()")
    op.drop_column("submission_reviews", "accepted_at")
