"""Manifest-bound maintenance. All output and audit records exclude application content."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from verboflex.core.config import Settings
from verboflex.db.base import Base

MAINTENANCE_LOCK = 0x56464D41494E54
SessionFactory = Callable[[], Session]

# Closed ownership graph: expressions use only the fixed table alias t.
KEY_OWNER = "(SELECT product_id FROM translation_keys WHERE id=t.translation_key_id)"
EXEC_OWNER = (
    "(SELECT j.product_id FROM import_executions e JOIN import_jobs j "
    "ON j.id=e.import_job_id WHERE e.id=t.import_execution_id)"
)
REPORT_OWNER = (
    "(SELECT coalesce(j.product_id,p.product_id) FROM duplicate_reports d "
    "LEFT JOIN import_executions e ON e.id=d.execution_id "
    "LEFT JOIN import_jobs j ON j.id=e.import_job_id "
    "LEFT JOIN preview_jobs p ON p.id=d.preview_job_id WHERE d.id=t.report_id)"
)
OWNERS = {
    "source_fallback_texts": "t.product_id",
    "source_fallback_policies": "t.product_id",
    "product_members": "t.product_id",
    "notifications": "(SELECT k.product_id FROM translation_comments c JOIN translation_keys k "
    "ON k.id=c.translation_key_id WHERE c.id=t.originating_comment_id)",
    "translation_comment_mentions": "(SELECT k.product_id FROM translation_comment_versions v "
    "JOIN translation_comments c ON c.id=v.comment_id JOIN translation_keys k "
    "ON k.id=c.translation_key_id WHERE v.id=t.comment_version_id)",
    "translation_comment_versions": "(SELECT k.product_id FROM translation_comments c "
    "JOIN translation_keys k ON k.id=c.translation_key_id WHERE c.id=t.comment_id)",
    "review_activities": "(SELECT k.product_id FROM translation_proposals p "
    "JOIN translation_keys k ON k.id=p.translation_key_id WHERE p.id=t.proposal_id)",
    "translation_proposal_values": KEY_OWNER,
    "translation_comments": KEY_OWNER,
    "translation_proposals": KEY_OWNER,
    "translation_constraints": KEY_OWNER,
    "translation_value_locators": KEY_OWNER,
    "translation_value_revisions": KEY_OWNER,
    "translation_values": KEY_OWNER,
    "translation_keys": "t.product_id",
    "localization_scopes": "t.product_id",
    "staged_translation_values": EXEC_OWNER,
    "translation_parse_issues": EXEC_OWNER,
    "duplicate_occurrences": REPORT_OWNER,
    "duplicate_groups": REPORT_OWNER,
    "duplicate_reports": "coalesce((SELECT j.product_id FROM import_executions e "
    "JOIN import_jobs j ON j.id=e.import_job_id WHERE e.id=t.execution_id), "
    "(SELECT product_id FROM preview_jobs WHERE id=t.preview_job_id))",
    "import_rewrite_deltas": "(SELECT product_id FROM import_rewrite_proposals "
    "WHERE id=t.proposal_id)",
    "import_rewrite_proposals": "t.product_id",
    "import_source_references": EXEC_OWNER.replace("t.import_execution_id", "t.execution_id"),
    "import_executions": "(SELECT product_id FROM import_jobs WHERE id=t.import_job_id)",
    "import_jobs": "t.product_id",
    "active_revision_revalidation_confirmations": "t.product_id",
    "preview_jobs": "t.product_id",
    "product_mapping_repository_sides": "(SELECT r.product_id FROM product_repository_mappings m "
    "JOIN product_revisions r ON r.id=m.revision_id WHERE m.id=t.mapping_id)",
    "product_mapping_allowed_targets": "(SELECT r.product_id FROM product_repository_mappings m "
    "JOIN product_revisions r ON r.id=m.revision_id WHERE m.id=t.mapping_id)",
    "product_repository_mappings": (
        "(SELECT product_id FROM product_revisions WHERE id=t.revision_id)"
    ),
    "product_revisions": "t.product_id",
    "products": "t.id",
}
TRIGGER_CATALOG_SQL = """SELECT coalesce(jsonb_agg(jsonb_build_array(
    tgrelid::regclass::text, tgname, pg_get_triggerdef(oid))
    ORDER BY tgrelid::regclass::text, tgname), '[]'::jsonb)::text
    FROM pg_trigger WHERE NOT tgisinternal AND tgrelid IN
    (SELECT oid FROM pg_class WHERE relnamespace='public'::regnamespace)"""

FK_CATALOG_SQL = """SELECT coalesce(jsonb_agg(jsonb_build_array(
    conrelid::regclass::text, conname, pg_get_constraintdef(oid))
    ORDER BY conrelid::regclass::text, conname), '[]'::jsonb)::text
    FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace
    AND conrelid::regclass::text NOT LIKE 'maintenance_%'"""

# Children precede parents. Only the two documented FK cycles are deleted together.
DELETE_GROUPS = (
    ("source_fallback_texts",),
    ("source_fallback_policies",),
    ("product_members",),
    ("notifications",),
    ("translation_comment_mentions",),
    ("translation_comment_versions",),
    ("review_activities",),
    ("translation_proposal_values",),
    ("translation_comments",),
    ("translation_proposals",),
    ("translation_constraints",),
    ("translation_value_locators",),
    ("translation_value_revisions",),
    ("staged_translation_values",),
    ("translation_values",),
    ("translation_keys",),
    ("translation_parse_issues",),
    ("duplicate_occurrences",),
    ("duplicate_groups",),
    ("duplicate_reports",),
    ("localization_scopes",),
    ("import_rewrite_deltas",),
    ("import_rewrite_proposals",),
    ("import_source_references",),
    ("active_revision_revalidation_confirmations",),
    ("product_mapping_repository_sides",),
    ("product_mapping_allowed_targets",),
    ("import_jobs", "import_executions"),
    ("product_repository_mappings", "preview_jobs"),
    ("product_revisions",),
    ("products",),
)


class ClosedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MaintenancePolicy(ClosedRecord):
    enabled: bool = True
    temporary_retention_days: int = Field(default=7, ge=1, le=3650)
    deleted_product_retention_days: int | None = Field(default=None, ge=1, le=3650)
    batch_rows: int = Field(default=1000, ge=1, le=10000)
    max_rows_per_run: int = Field(default=10000, ge=1, le=100000)
    max_run_seconds: int = Field(default=45, ge=1, le=240)
    lock_timeout_ms: int = Field(default=1000, ge=1, le=5000)
    statement_timeout_ms: int = Field(default=5000, ge=1, le=10000)

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls.model_validate(
            {name: getattr(settings, "maintenance_" + name) for name in cls.model_fields}
        )

    @model_validator(mode="after")
    def limits(self) -> Self:
        if self.batch_rows > self.max_rows_per_run:
            raise ValueError("batch exceeds run budget")
        if self.lock_timeout_ms > self.statement_timeout_ms:
            raise ValueError("lock timeout exceeds statement timeout")
        if self.statement_timeout_ms > self.max_run_seconds * 1000:
            raise ValueError("statement timeout exceeds run budget")
        return self


class MaintenanceTarget(ClosedRecord):
    kind: Literal["staging", "product"]
    id: UUID
    product_id: UUID
    identity: str = Field(pattern="^[0-9a-f]{64}$")
    counts: dict[str, int]

    @model_validator(mode="after")
    def exact_scope(self) -> Self:
        expected = {"staged_translation_values"} if self.kind == "staging" else set(OWNERS)
        if set(self.counts) != expected or any(value < 0 for value in self.counts.values()):
            raise ValueError("invalid manifest table counts")
        if self.kind == "product" and (self.id != self.product_id or self.counts["products"] != 1):
            raise ValueError("invalid product identity")
        return self


class MaintenanceExclusion(ClosedRecord):
    id: UUID
    reason: Literal[
        "not_deleted",
        "missing",
        "inflight",
        "pending_rewrite",
        "recent",
        "submission_evidence",
        "busy",
        "changed",
        "oversized_cycle",
    ]


class MaintenanceManifest(ClosedRecord):
    version: Literal[1] = 1
    origin: Literal["operator", "scheduled"] = "operator"
    database_identity: str = Field(pattern="^[0-9a-f]{64}$")
    schema_revision: str = Field(min_length=1, max_length=128)
    created_at: AwareDatetime
    temporary_cutoff: AwareDatetime
    product_cutoff: AwareDatetime | None = None
    policy: MaintenancePolicy
    targets: tuple[MaintenanceTarget, ...]
    exclusions: tuple[MaintenanceExclusion, ...]
    digest: str = ""

    @model_validator(mode="after")
    def exact_cutoffs(self) -> Self:
        if self.temporary_cutoff != self.created_at - timedelta(
            days=self.policy.temporary_retention_days
        ):
            raise ValueError("invalid temporary cutoff")
        expected_product_cutoff = (
            self.created_at - timedelta(days=self.policy.deleted_product_retention_days)
            if self.origin == "scheduled" and self.policy.deleted_product_retention_days
            else None
        )
        if self.product_cutoff != expected_product_cutoff or len(self.targets) > 1100:
            raise ValueError("invalid product cutoff or target budget")
        identities = [(target.kind, target.id) for target in self.targets]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate manifest target")
        products = {target.id for target in self.targets if target.kind == "product"}
        if any(t.product_id in products for t in self.targets if t.kind == "staging"):
            raise ValueError("overlapping manifest targets")
        if self.origin == "scheduled" and products and self.product_cutoff is None:
            raise ValueError("automatic product purge disabled")
        return self

    def calculated_digest(self) -> str:
        return _digest(self.model_dump(mode="json", exclude={"digest"}))


class MaintenanceSummary(ClosedRecord):
    digest: str
    status: Literal["complete", "partial", "failed", "skipped"]
    deleted_rows: int = 0
    counts: dict[str, int] = Field(default_factory=dict)
    remaining_rows: int = 0
    reason: str | None = None


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _database_identity(session: Session) -> str:
    try:
        row = session.execute(
            text(
                "SELECT system_identifier::text, "
                "current_database(), oid::text FROM pg_catalog.pg_database "
                "CROSS JOIN pg_catalog.pg_control_system() "
                "WHERE datname=current_database()"
            )
        ).one_or_none()
    except DBAPIError:
        raise ValueError("database_identity_unavailable") from None
    if row is None or any(not isinstance(value, str) or not value for value in row):
        raise ValueError("database_identity_unavailable")
    return _digest(tuple(row))


def _revision(session: Session) -> str:
    return str(session.scalar(text("SELECT version_num FROM alembic_version")))


def _protection_reason_sql(product: str, *, submission_evidence: bool = False) -> str:
    """Use the same protection predicates in discovery and the locked batch rechecks.

    `product` is an internal SQL expression, never caller input.
    """
    cases = []
    if submission_evidence:
        cases.append(
            f"WHEN EXISTS (SELECT 1 FROM submission_reviews WHERE product_id={product} "
            f"UNION ALL SELECT 1 FROM submission_batches WHERE product_id={product}) "
            "THEN 'submission_evidence'"
        )
    for reason, query in (
        (
            "inflight",
            "SELECT 1 FROM import_jobs WHERE product_id=:id AND state IN ('queued','running') "
            "UNION ALL SELECT 1 FROM preview_jobs WHERE product_id=:id "
            "AND state IN ('queued','running') "
            "UNION ALL SELECT 1 FROM import_executions blocked_e "
            "JOIN import_jobs blocked_j ON blocked_j.id=blocked_e.import_job_id "
            "WHERE blocked_j.product_id=:id AND blocked_e.state IN ('queued','running') "
            "UNION ALL SELECT 1 FROM submission_reviews WHERE product_id=:id "
            "AND state IN ('queued','running') "
            "UNION ALL SELECT 1 FROM change_sets c JOIN submission_batches b ON b.id=c.batch_id "
            "WHERE b.product_id=:id AND c.status IN ('queued','running','reconciling')",
        ),
        (
            "pending_rewrite",
            "SELECT 1 FROM import_rewrite_proposals WHERE product_id=:id AND status='pending'",
        ),
    ):
        cases.append(f"WHEN EXISTS ({query.replace(':id', product)}) THEN '{reason}'")
    return "CASE " + " ".join(cases) + " END"


def _blocked(session: Session, product_id: UUID) -> str | None:
    reason = session.scalar(text("SELECT " + _protection_reason_sql(":id")), {"id": product_id})
    return str(reason) if reason is not None else None


def _product_identity(
    session: Session, product_id: UUID
) -> tuple[str, datetime | None, bool] | None:
    row = session.execute(
        text("SELECT deleted_at, deleted_by, updated_at, is_active FROM products WHERE id=:id"),
        {"id": product_id},
    ).first()
    if row is None:
        return None
    return _digest([str(value) for value in row]), row.deleted_at, row.is_active


def _product_exclusion(session: Session, product_id: UUID) -> str | None:
    identity = _product_identity(session, product_id)
    if identity is None:
        return "missing"
    if identity[1] is None or identity[2]:
        return "not_deleted"
    reason = session.scalar(
        text("SELECT " + _protection_reason_sql(":id", submission_evidence=True)),
        {"id": product_id},
    )
    return str(reason) if reason is not None else None


def _product_counts(session: Session, product_id: UUID) -> dict[str, int]:
    counts = {}
    for table, owner in OWNERS.items():
        joins = ""
        predicate = owner
        # Counts can join unique parent identities once instead of resolving the
        # same owner in a correlated subquery for every historical child row.
        # Keep OWNERS unchanged: row selection/deletion authority still uses it.
        if owner == KEY_OWNER:
            joins = " JOIN translation_keys k ON k.id=t.translation_key_id"
            predicate = "k.product_id"
        elif owner == EXEC_OWNER or table == "import_source_references":
            execution = (
                "execution_id" if table == "import_source_references" else "import_execution_id"
            )
            joins = (
                f" JOIN import_executions e ON e.id=t.{execution}"
                " JOIN import_jobs j ON j.id=e.import_job_id"
            )
            predicate = "j.product_id"
        elif owner == REPORT_OWNER or table == "duplicate_reports":
            report = "t" if table == "duplicate_reports" else "d"
            if report == "d":
                joins = " JOIN duplicate_reports d ON d.id=t.report_id"
            joins += (
                f" LEFT JOIN import_executions e ON e.id={report}.execution_id"
                " LEFT JOIN import_jobs j ON j.id=e.import_job_id"
                f" LEFT JOIN preview_jobs p ON p.id={report}.preview_job_id"
            )
            predicate = "coalesce(j.product_id,p.product_id)"
        counts[table] = int(
            session.scalar(
                text(f"SELECT count(*) FROM {table} t{joins} WHERE {predicate}=:product"),
                {"product": product_id},
            )
            or 0
        )
    return counts


def _staging_identity(session: Session, execution_id: UUID) -> tuple[UUID, str, datetime] | None:
    row = session.execute(
        text(
            "SELECT j.product_id, e.id, e.import_job_id, e.state, e.finished_at "
            "FROM import_executions e JOIN import_jobs j ON j.id=e.import_job_id WHERE e.id=:id"
        ),
        {"id": execution_id},
    ).first()
    if not row or row.state not in ("succeeded", "failed") or row.finished_at is None:
        return None
    return row.product_id, _digest([str(item) for item in row]), row.finished_at


def _staging_count(session: Session, execution_id: UUID) -> int:
    return int(
        session.scalar(
            text("SELECT count(*) FROM staged_translation_values WHERE import_execution_id=:id"),
            {"id": execution_id},
        )
        or 0
    )


def build_manifest(
    session: Session,
    policy: MaintenancePolicy,
    product_ids: Sequence[UUID],
    now: datetime,
    *,
    temporary: bool = True,
    scheduled: bool = False,
) -> MaintenanceManifest:
    """Read-only inventory; explicit products are independent of scheduled retention."""
    if now.tzinfo is None:
        raise ValueError("timezone required")
    _timeouts(session, policy)
    cutoff = now - timedelta(days=policy.temporary_retention_days)
    targets: list[MaintenanceTarget] = []
    exclusions: list[MaintenanceExclusion] = []
    product_cutoff = (
        now - timedelta(days=policy.deleted_product_retention_days)
        if scheduled and policy.deleted_product_retention_days
        else None
    )
    selected_products = set(product_ids)
    if scheduled and product_cutoff is not None:
        product_candidates = (
            "SELECT p.id, p.deleted_at, "
            + _protection_reason_sql("p.id", submission_evidence=True)
            + " AS reason FROM products p WHERE deleted_at < :cutoff AND NOT is_active"
        )
        # Independent bounded exclusion samples cannot consume eligible target slots.
        for condition in ("IS NULL", "IS NOT NULL"):
            for row in session.execute(
                text(
                    f"SELECT id, reason FROM ({product_candidates}) candidates "
                    f"WHERE reason {condition} ORDER BY deleted_at, id LIMIT 100"
                ),
                {"cutoff": product_cutoff},
            ):
                if row.reason:
                    exclusions.append(
                        MaintenanceExclusion.model_validate({"id": row.id, "reason": row.reason})
                    )
                else:
                    selected_products.add(row.id)
    for product_id in sorted(selected_products):
        reason = _product_exclusion(session, product_id)
        identity = _product_identity(session, product_id)
        if (
            not reason
            and product_cutoff is not None
            and identity
            and identity[1] is not None
            and identity[1] >= product_cutoff
        ):
            reason = "recent"
        if reason:
            exclusions.append(
                MaintenanceExclusion.model_validate({"id": product_id, "reason": reason})
            )
        else:
            assert identity is not None
            targets.append(
                MaintenanceTarget(
                    kind="product",
                    id=product_id,
                    product_id=product_id,
                    identity=identity[0],
                    counts=_product_counts(session, product_id),
                )
            )
    if temporary:
        staging_candidates = (
            "SELECT e.id, "
            + _protection_reason_sql("j.product_id")
            + " AS reason FROM import_executions e JOIN import_jobs j ON j.id=e.import_job_id "
            "WHERE e.state IN ('succeeded','failed') AND e.finished_at < :cutoff "
            "AND EXISTS (SELECT 1 FROM staged_translation_values s "
            "WHERE s.import_execution_id=e.id) "
            "AND NOT (j.product_id = ANY(CAST(:products AS uuid[])))"
        )
        executions = []
        for condition in ("IS NULL", "IS NOT NULL"):
            for row in session.execute(
                text(
                    f"SELECT id, reason FROM ({staging_candidates}) candidates "
                    f"WHERE reason {condition} ORDER BY id LIMIT 1000"
                ),
                {"cutoff": cutoff, "products": list(selected_products)},
            ):
                if row.reason:
                    exclusions.append(
                        MaintenanceExclusion.model_validate({"id": row.id, "reason": row.reason})
                    )
                else:
                    executions.append(row.id)
        for execution_id in executions:
            staging_identity = _staging_identity(session, execution_id)
            assert staging_identity is not None
            product_id, token, _ = staging_identity
            if product_id in selected_products:
                continue
            reason = _blocked(session, product_id)
            if reason:
                exclusions.append(
                    MaintenanceExclusion.model_validate({"id": execution_id, "reason": reason})
                )
                continue
            targets.append(
                MaintenanceTarget(
                    kind="staging",
                    id=execution_id,
                    product_id=product_id,
                    identity=token,
                    counts={"staged_translation_values": _staging_count(session, execution_id)},
                )
            )
    manifest = MaintenanceManifest(
        origin="scheduled" if scheduled else "operator",
        database_identity=_database_identity(session),
        schema_revision=_revision(session),
        created_at=now,
        temporary_cutoff=cutoff,
        product_cutoff=product_cutoff,
        policy=policy,
        targets=tuple(targets),
        exclusions=tuple(exclusions),
    )
    return manifest.model_copy(update={"digest": manifest.calculated_digest()})


def _timeouts(session: Session, policy: MaintenancePolicy) -> None:
    session.execute(
        text(
            "SELECT set_config('lock_timeout', :lock, true), "
            "set_config('statement_timeout', :statement, true)"
        ),
        {"lock": str(policy.lock_timeout_ms), "statement": str(policy.statement_timeout_ms)},
    )


def _lock_target(session: Session, target: MaintenanceTarget) -> None:
    params = {"id": target.product_id}
    # Same ownership order as import/publication services, NOWAIT so readers/workers win.
    for query in (
        "SELECT id FROM products WHERE id=:id FOR UPDATE NOWAIT",
        "SELECT id FROM product_revisions WHERE product_id=:id ORDER BY id FOR UPDATE NOWAIT",
        "SELECT m.id FROM product_repository_mappings m "
        "JOIN product_revisions r ON r.id=m.revision_id "
        "WHERE r.product_id=:id ORDER BY m.id FOR UPDATE OF m NOWAIT",
        "SELECT id FROM import_jobs WHERE product_id=:id ORDER BY id FOR UPDATE NOWAIT",
        "SELECT e.id FROM import_executions e JOIN import_jobs j ON j.id=e.import_job_id "
        "WHERE j.product_id=:id ORDER BY e.id FOR UPDATE OF e NOWAIT",
    ):
        session.execute(text(query), params).all()


def _receipts(session: Session, digest: str, target: MaintenanceTarget) -> dict[str, int]:
    counts: dict[str, int] = {}
    for receipt in session.scalars(
        text(
            "SELECT counts FROM maintenance_batches WHERE "
            "run_digest=:digest AND target_id=:id AND kind=:kind"
        ),
        {"digest": digest, "id": target.id, "kind": target.kind},
    ):
        for table, count in receipt.items():
            counts[table] = counts.get(table, 0) + count
    return counts


def _staging_batch(
    session: Session, manifest: MaintenanceManifest, target: MaintenanceTarget, limit: int
) -> dict[str, int]:
    _lock_target(session, target)
    identity = _staging_identity(session, target.id)
    if not identity or identity[0] != target.product_id or identity[1] != target.identity:
        raise ValueError("changed")
    reason = _blocked(session, target.product_id)
    if reason or identity[2] >= manifest.temporary_cutoff:
        raise ValueError(reason or "changed")
    counts = _receipts(session, manifest.digest, target)
    remaining = _staging_count(session, target.id)
    if (
        remaining + counts.get("staged_translation_values", 0)
        != target.counts["staged_translation_values"]
    ):
        raise ValueError("changed")
    rows = session.scalars(
        text(
            "SELECT position FROM staged_translation_values "
            "WHERE import_execution_id=:id ORDER BY position LIMIT :limit "
            "FOR UPDATE NOWAIT"
        ),
        {"id": target.id, "limit": limit},
    ).all()
    if not rows:
        return {}
    session.execute(
        text(
            "INSERT INTO maintenance_authorizations "
            "(transaction_id, run_digest, kind, target_id, product_id, table_name, row_key) "
            "VALUES (pg_current_xact_id()::text, :digest, 'staging', :id, :product, "
            "'staged_translation_values', "
            "jsonb_build_object('import_execution_id', CAST(:id AS text), "
            "'position', CAST(:position AS int)))"
        ),
        [
            {
                "digest": manifest.digest,
                "id": target.id,
                "product": target.product_id,
                "position": row,
            }
            for row in rows
        ],
    )
    result = session.execute(
        text(
            "DELETE FROM staged_translation_values WHERE "
            "import_execution_id=:id AND position = ANY(:positions) RETURNING position"
        ),
        {"id": target.id, "positions": rows},
    ).all()
    return {"staged_translation_values": len(result)}


def _row_key_sql(table: str) -> str:
    columns = Base.metadata.tables[table].primary_key.columns
    return (
        "jsonb_build_object("
        + ",".join(f"'{column.name}', t.{column.name}" for column in columns)
        + ")"
    )


def _authorize_rows(
    session: Session,
    manifest: MaintenanceManifest,
    target: MaintenanceTarget,
    table: str,
    rows: Sequence[dict[str, object]],
) -> None:
    if rows:
        session.execute(
            text(
                "INSERT INTO maintenance_authorizations "
                "(transaction_id, run_digest, kind, target_id, product_id, table_name, row_key) "
                "VALUES (pg_current_xact_id()::text, :digest, :kind, :id, :product, :table, "
                "CAST(:key AS jsonb))"
            ),
            [
                {
                    "digest": manifest.digest,
                    "kind": target.kind,
                    "id": target.id,
                    "product": target.product_id,
                    "table": table,
                    "key": json.dumps(row),
                }
                for row in rows
            ],
        )


def _delete_rows(session: Session, table: str, rows: Sequence[dict[str, object]]) -> int:
    if not rows:
        return 0
    # jsonb_to_recordset gives indexed typed PK comparisons, never a JSON scan of application rows.
    columns = Base.metadata.tables[table].primary_key.columns
    fields = ",".join(
        f"{c.name} {c.type.compile(dialect=session.get_bind().dialect)}" for c in columns
    )
    predicate = " AND ".join(f"t.{c.name}=k.{c.name}" for c in columns)
    # A same-schema cross-product child must never be removed by a hidden cascade.
    # RESTRICT/NO ACTION already fail safely; explicitly check every mutating referential action.
    for child in Base.metadata.tables.values():
        for fk in child.foreign_key_constraints:
            if fk.referred_table.name != table or fk.ondelete not in ("CASCADE", "SET NULL"):
                continue
            join = " AND ".join(f"c.{f.parent.name}=t.{f.column.name}" for f in fk.elements)
            key = (
                "jsonb_build_object("
                + ",".join(f"'{c.name}',c.{c.name}" for c in child.primary_key.columns)
                + ")"
            )
            unsafe = session.execute(
                text(
                    f"SELECT 1 FROM {table} t "
                    f"JOIN jsonb_to_recordset(CAST(:keys AS jsonb)) AS k({fields}) ON {predicate} "
                    f"JOIN {child.name} c ON {join} WHERE NOT EXISTS "
                    "(SELECT 1 FROM maintenance_authorizations a "
                    "WHERE a.transaction_id=pg_current_xact_id()::text AND a.table_name=:child "
                    f"AND a.row_key={key}) LIMIT 1"
                ),
                {"keys": json.dumps(list(rows)), "child": child.name},
            ).first()
            if unsafe:
                raise ValueError("external_reference")
    return len(
        session.execute(
            text(
                f"DELETE FROM {table} t USING jsonb_to_recordset("
                f"CAST(:keys AS jsonb)) AS k({fields}) WHERE {predicate} RETURNING 1"
            ),
            {"keys": json.dumps(list(rows))},
        ).all()
    )


def _product_batch(
    session: Session, manifest: MaintenanceManifest, target: MaintenanceTarget, limit: int
) -> dict[str, int]:
    _lock_target(session, target)
    receipts = _receipts(session, manifest.digest, target)
    if receipts == target.counts or (receipts.get("products") == 1):
        return {}
    reason = _product_exclusion(session, target.id)
    identity = _product_identity(session, target.id)
    if reason or identity is None or identity[0] != target.identity:
        raise ValueError(reason or "changed")
    if manifest.product_cutoff and identity[1] and identity[1] >= manifest.product_cutoff:
        raise ValueError("changed")
    remaining = _product_counts(session, target.id)
    if any(
        remaining[table] + receipts.get(table, 0) != count for table, count in target.counts.items()
    ):
        raise ValueError("changed")
    for group in DELETE_GROUPS:
        if not any(remaining[table] for table in group):
            continue
        root = group[0]
        rows = session.scalars(
            text(
                f"SELECT {_row_key_sql(root)} FROM {root} t "
                f"WHERE {OWNERS[root]}=:product ORDER BY "
                + ",".join(f"t.{c.name}" for c in Base.metadata.tables[root].primary_key.columns)
                + " LIMIT :limit FOR UPDATE NOWAIT"
            ),
            {"product": target.id, "limit": 1 if len(group) > 1 else limit},
        ).all()
        selected = {root: rows}
        if len(group) > 1:
            child = group[1]
            parent_fk = "import_job_id" if child == "import_executions" else "mapping_id"
            selected[child] = session.scalars(
                text(
                    f"SELECT {_row_key_sql(child)} FROM {child} t "
                    f"WHERE {parent_fk}=:parent ORDER BY t.id LIMIT :limit FOR UPDATE NOWAIT"
                ),
                {"parent": rows[0]["id"], "limit": limit + 1},
            ).all()
            if sum(len(items) for items in selected.values()) > limit:
                raise ValueError("oversized_cycle")
        for table, items in selected.items():
            _authorize_rows(session, manifest, target, table, items)
        # Nullable root pointers may be cleared on the locked, still-deleted product only.
        if root == "product_revisions":
            session.execute(
                text(
                    "UPDATE products SET active_revision_id=NULL, "
                    "candidate_revision_id=NULL WHERE id=:id AND deleted_at IS NOT NULL "
                    "AND NOT is_active"
                ),
                {"id": target.id},
            )
        # All earlier leaf families were proven empty above. The sole possible cascade is the
        # explicitly authorized cycle child; its size counts against this transaction's budget.
        deleted = _delete_rows(session, root, rows)
        if deleted != len(rows):
            raise ValueError("changed")
        return {table: len(items) for table, items in selected.items()}
    return {}


def apply_manifest(
    session_factory: SessionFactory,
    manifest: MaintenanceManifest,
    policy: MaintenancePolicy,
    now: datetime,
) -> MaintenanceSummary:
    """Apply or resume a single manifest, holding one dedicated advisory-lock session."""
    if manifest.digest != manifest.calculated_digest() or manifest.policy != policy:
        raise ValueError("manifest_digest_or_policy_mismatch")
    if now < manifest.created_at:
        raise ValueError("manifest_from_future")
    start = time.monotonic()
    counts: dict[str, int] = {}
    remaining = 0
    status: Literal["complete", "partial", "failed", "skipped"] = "complete"
    reason = None
    run_started = False
    with session_factory() as lock_session:
        connection = lock_session.connection()
        if not connection.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": MAINTENANCE_LOCK}
        ):
            return MaintenanceSummary(digest=manifest.digest, status="skipped", reason="busy")
        try:
            with session_factory() as session:
                if (
                    _database_identity(session) != manifest.database_identity
                    or _revision(session) != manifest.schema_revision
                ):
                    raise ValueError("database_or_schema_mismatch")
                changed = session.scalar(
                    text(
                        "SELECT count(*) FROM maintenance_schema WHERE "
                        "name NOT IN ('foreign_keys', 'triggers') AND "
                        "pg_get_functiondef(to_regproc(name)) IS DISTINCT FROM installed_definition"
                    )
                )
                if changed:
                    raise ValueError("schema_guard_changed")
                expected_fks = session.scalar(
                    text(
                        "SELECT installed_definition FROM "
                        "maintenance_schema WHERE name='foreign_keys'"
                    )
                )
                if expected_fks != session.scalar(text(FK_CATALOG_SQL)):
                    raise ValueError("schema_foreign_keys_changed")
                expected_triggers = session.scalar(
                    text(
                        "SELECT installed_definition FROM maintenance_schema WHERE name='triggers'"
                    )
                )
                if expected_triggers != session.scalar(text(TRIGGER_CATALOG_SQL)):
                    raise ValueError("schema_triggers_changed")
            with session_factory() as session, session.begin():
                _timeouts(session, policy)
                session.execute(
                    text(
                        "INSERT INTO maintenance_runs(digest, manifest, status) "
                        "VALUES (:digest, CAST(:manifest AS jsonb), 'running') "
                        "ON CONFLICT (digest) "
                        "DO UPDATE SET status='running', error_code=NULL, updated_at=now()"
                    ),
                    {"digest": manifest.digest, "manifest": manifest.model_dump_json()},
                )
            run_started = True
            for target in manifest.targets:
                while True:
                    limit = min(policy.batch_rows, policy.max_rows_per_run - sum(counts.values()))
                    if limit <= 0 or time.monotonic() - start >= policy.max_run_seconds:
                        status, reason = "partial", "budget"
                        break
                    try:
                        with session_factory() as session, session.begin():
                            _timeouts(session, policy)
                            batch = (
                                _staging_batch if target.kind == "staging" else _product_batch
                            )(session, manifest, target, limit)
                            if batch:
                                session.execute(
                                    text(
                                        "INSERT INTO maintenance_batches "
                                        "(run_digest, kind, target_id, counts) VALUES "
                                        "(:digest, :kind, :id, CAST(:counts AS jsonb))"
                                    ),
                                    {
                                        "digest": manifest.digest,
                                        "kind": target.kind,
                                        "id": target.id,
                                        "counts": json.dumps(batch),
                                    },
                                )
                            session.execute(
                                text(
                                    "DELETE FROM maintenance_authorizations WHERE "
                                    "transaction_id=pg_current_xact_id()::text"
                                )
                            )
                        for table, count in batch.items():
                            counts[table] = counts.get(table, 0) + count
                        if not batch:
                            break
                    except (DBAPIError, ValueError) as error:
                        status = "partial"
                        safe_reasons = {
                            "changed",
                            "inflight",
                            "pending_rewrite",
                            "not_deleted",
                            "submission_evidence",
                            "oversized_cycle",
                            "external_reference",
                        }
                        reason = (
                            str(error)
                            if isinstance(error, ValueError) and str(error) in safe_reasons
                            else "database_busy_or_error"
                        )
                        break
                if reason == "budget":
                    break
            with session_factory() as session, session.begin():
                _timeouts(session, policy)
                for target in manifest.targets:
                    receipts = _receipts(session, manifest.digest, target)
                    remaining += sum(target.counts.values()) - sum(receipts.values())
                if remaining == 0:
                    status, reason = "complete", None
                session.execute(
                    text(
                        "UPDATE maintenance_runs SET status=:status, error_code=:reason, "
                        "updated_at=now() WHERE digest=:digest"
                    ),
                    {"status": status, "reason": reason, "digest": manifest.digest},
                )
        except BaseException:
            # The failed transaction (including its authorization/receipt) has rolled back.
            # A separately committed bounded status lets redelivery resume prior successful batches.
            # Preflight refusals must preserve imported/foreign audit history unchanged.
            if run_started:
                try:
                    with session_factory() as session, session.begin():
                        _timeouts(session, policy)
                        session.execute(
                            text(
                                "UPDATE maintenance_runs SET status='failed', "
                                "error_code='interrupted', updated_at=now() WHERE digest=:digest"
                            ),
                            {"digest": manifest.digest},
                        )
                except DBAPIError:
                    pass
            raise
        finally:
            try:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": MAINTENANCE_LOCK}
                )
            except BaseException:
                connection.invalidate()
                raise
    return MaintenanceSummary(
        digest=manifest.digest,
        status=status,
        counts=counts,
        deleted_rows=sum(counts.values()),
        remaining_rows=remaining,
        reason=reason,
    )


def run_scheduled_maintenance(
    session_factory: SessionFactory, policy: MaintenancePolicy, now: datetime
) -> MaintenanceSummary:
    if not policy.enabled:
        return MaintenanceSummary(digest="", status="skipped", reason="disabled")
    with session_factory() as session:
        _timeouts(session, policy)
        pending = session.scalars(
            text(
                "SELECT manifest FROM maintenance_runs WHERE "
                "status IN ('running','partial','failed') AND manifest->>'origin'='scheduled' "
                "AND (error_code IS NULL OR "
                "error_code IN ('budget','interrupted','database_busy_or_error')) "
                "AND manifest->>'database_identity'=:identity "
                "AND manifest->>'schema_revision'=:revision "
                "AND manifest->'policy'=CAST(:policy AS jsonb) "
                "ORDER BY updated_at LIMIT 1"
            ),
            {
                "policy": policy.model_dump_json(),
                "revision": _revision(session),
                "identity": _database_identity(session),
            },
        ).first()
        manifest = (
            MaintenanceManifest.model_validate(pending)
            if pending
            else build_manifest(session, policy, [], now, scheduled=True)
        )
    return apply_manifest(session_factory, manifest, policy, now)
