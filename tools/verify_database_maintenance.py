"""Read-only, content-free maintenance evidence; run with the backend environment.

Uses VERBOFLEX_DATABASE_URL only in snapshot mode. Compare never connects to a DB.
No row contents, SQL parameters, credentials or database names enter evidence/errors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import verboflex.models  # noqa: F401
from verboflex.db.base import Base
from verboflex.services.database_maintenance import (
    OWNERS,
    MaintenanceManifest,
    _database_identity,
    _product_counts,
)

REVISION = "0046_screenshots"
CHUNK_ROWS = 512
OPERATIONAL_TABLES = {
    "alembic_version",
    "maintenance_runs",
    "maintenance_batches",
    "maintenance_authorizations",
    "maintenance_schema",
}


def write_private(path, value):
    """Exclusive output creation also rejects symlink destinations; no overwrite."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(value, output, sort_keys=True, indent=2)
        output.write("\n")


def load_manifest(path):
    if path.stat().st_size > 2_000_000:
        raise ValueError("manifest too large")
    manifest = MaintenanceManifest.model_validate_json(path.read_text())
    if manifest.digest != manifest.calculated_digest():
        raise ValueError("invalid manifest digest")
    return manifest


def fingerprint(session, table, predicate, parameters):
    """Hash private rows on the server, then hash ordered fixed-size digest chunks."""
    columns = Base.metadata.tables[table].primary_key.columns
    order = ", ".join(f't."{column.name}"' for column in columns)
    query = text(
        "SELECT encode(sha256(convert_to(to_jsonb(t)::text, 'UTF8')), 'hex') "
        f'FROM "{table}" t WHERE {predicate} ORDER BY {order}'
    )
    total = 0
    chunks = []
    with session.execute(query, parameters, execution_options={"yield_per": CHUNK_ROWS}) as rows:
        for partition in rows.partitions(CHUNK_ROWS):
            total += len(partition)
            chunk = hashlib.sha256()
            for (digest,) in partition:
                chunk.update(bytes.fromhex(digest))
            chunks.append(chunk.hexdigest())
    combined = hashlib.sha256(b"".join(bytes.fromhex(value) for value in chunks)).hexdigest()
    return {"count": total, "sha256": combined, "chunks": chunks}


def snapshot(factory, manifest=None):
    """Protect every row outside the explicit purge graph, including inactive products."""
    with factory() as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        session.execute(text("SET LOCAL statement_timeout = '30s'"))
        session.execute(text("SET LOCAL lock_timeout = '1s'"))
        session.execute(text("SET LOCAL jit = off"))
        revision = session.scalar(text("SELECT version_num FROM alembic_version"))
        identity = _database_identity(session)
        if revision != REVISION:
            raise ValueError("unsupported schema")
        if manifest is not None and (
            manifest.digest != manifest.calculated_digest()
            or manifest.database_identity != identity
            or manifest.schema_revision != revision
        ):
            raise ValueError("manifest identity mismatch")
        actual_tables = set(
            session.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
        )
        if actual_tables != set(Base.metadata.tables) | OPERATIONAL_TABLES:
            raise ValueError("unclassified schema tables")
        products = [
            {
                "id": str(row.id),
                "is_active": row.is_active,
                "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None,
            }
            for row in session.execute(
                text("SELECT id,is_active,deleted_at FROM products ORDER BY id")
            )
        ]
        targets = manifest.targets if manifest else ()
        purged = [target.id for target in targets if target.kind == "product"]
        staging = [target.id for target in targets if target.kind == "staging"]
        protected, temporary = {}, {}
        parameters = {"purged": purged, "staging": staging}
        for table in sorted(Base.metadata.tables):
            predicate = "true"
            if table in OWNERS:
                owner = OWNERS[table]
                predicate = f"NOT coalesce(({owner}) = ANY(CAST(:purged AS uuid[])), false)"
            if table == "staged_translation_values":
                eligible = "t.import_execution_id = ANY(CAST(:staging AS uuid[]))"
                temporary[table] = fingerprint(
                    session, table, f"({predicate}) AND ({eligible})", parameters
                )
                predicate = f"({predicate}) AND NOT ({eligible})"
            protected[table] = fingerprint(session, table, predicate, parameters)
        target_counts = {
            str(target.id): _product_counts(session, target.id)
            for target in targets
            if target.kind == "product"
        }
        receipts = {}
        if manifest:
            for row in session.execute(
                text(
                    "SELECT kind,target_id,counts FROM maintenance_batches "
                    "WHERE run_digest=:digest "
                    "ORDER BY id"
                ),
                {"digest": manifest.digest},
            ):
                key = f"{row.kind}:{row.target_id}"
                accumulated = receipts.setdefault(key, {})
                for table, count in row.counts.items():
                    accumulated[table] = accumulated.get(table, 0) + count
        sizes = [
            dict(row)
            for row in session.execute(
                text(
                    "SELECT relname AS table_name,n_live_tup,n_dead_tup,"
                    "pg_relation_size(relid) AS heap_bytes,pg_indexes_size(relid) AS index_bytes,"
                    "pg_total_relation_size(relid) AS total_bytes "
                    "FROM pg_stat_user_tables ORDER BY relname"
                )
            ).mappings()
        ]
        return {
            "version": 1,
            "captured_at": datetime.now(UTC).isoformat(),
            "schema_revision": revision,
            "database_identity": identity,
            "manifest_digest": manifest.digest if manifest else None,
            "active_product_ids": [
                p["id"] for p in products if p["is_active"] and p["deleted_at"] is None
            ],
            "products": products,
            "protected": protected,
            "temporary": temporary,
            "target_counts": target_counts,
            "staging_counts": {
                str(target.id): session.scalar(
                    text(
                        "SELECT count(*) FROM staged_translation_values "
                        "WHERE import_execution_id=:id"
                    ),
                    {"id": target.id},
                )
                for target in targets
                if target.kind == "staging"
            },
            "receipts": receipts,
            "sizes": sizes,
            "database_bytes": session.scalar(text("SELECT pg_database_size(current_database())")),
        }


def compare(before, after, manifest=None, product_ids=()):
    errors = []
    for field in (
        "version",
        "schema_revision",
        "database_identity",
        "manifest_digest",
        "active_product_ids",
    ):
        if before[field] != after[field]:
            errors.append(field)
    for table in sorted(set(before["protected"]) | set(after["protected"])):
        if before["protected"].get(table) != after["protected"].get(table):
            errors.append("protected:" + table)
    requested = {str(value) for value in product_ids}
    prior = {row["id"]: row for row in before["products"]}
    current = {row["id"]: row for row in after["products"]}
    outcomes = []
    if manifest:
        if (
            manifest.digest != manifest.calculated_digest()
            or before["manifest_digest"] != manifest.digest
            or manifest.database_identity != before["database_identity"]
            or manifest.schema_revision != before["schema_revision"]
        ):
            errors.append("manifest_identity")
        targets = {str(t.id): t for t in manifest.targets if t.kind == "product"}
        excluded = {str(e.id): e.reason for e in manifest.exclusions if str(e.id) in prior}
        if requested != set(targets) | set(excluded):
            errors.append("requested_scope")
        for product in sorted(requested):
            outcome = {"id": product, "outcome": "incomplete"}
            if (
                product not in prior
                or prior[product]["deleted_at"] is None
                or prior[product]["is_active"]
            ):
                errors.append("unauthorized_product:" + product)
            elif product in excluded and product in current:
                outcome.update(outcome="retained", reason=excluded[product])
            elif product in targets:
                expected = targets[product].counts
                remaining = after["target_counts"].get(product, {})
                receipts = after["receipts"].get("product:" + product, {})
                if any(
                    remaining.get(table, -1) + receipts.get(table, 0) != count
                    for table, count in expected.items()
                ) or set(receipts) - set(expected):
                    errors.append("receipt_mismatch:" + product)
                elif product not in current and sum(remaining.values()) == 0:
                    outcome["outcome"] = "purged"
            if outcome["outcome"] == "incomplete":
                errors.append("incomplete:" + product)
            outcomes.append(outcome)
    elif requested or before["manifest_digest"] is not None:
        errors.append("manifest_required")
    if manifest:
        for target in manifest.targets:
            if target.kind != "staging":
                continue
            remaining = after["staging_counts"].get(str(target.id), -1)
            counts = after["receipts"].get("staging:" + str(target.id), {})
            if remaining + counts.get("staged_translation_values", 0) != target.counts[
                "staged_translation_values"
            ] or set(counts) - {"staged_translation_values"}:
                errors.append("staging_receipt_mismatch:" + str(target.id))
            if remaining != 0:
                errors.append("staging_incomplete:" + str(target.id))
    return {"ok": not errors, "errors": errors, "products": outcomes}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    take = actions.add_parser("snapshot")
    check = actions.add_parser("compare")
    for command in (take, check):
        command.add_argument("--output", required=True, type=Path)
        command.add_argument("--manifest", type=Path)
    check.add_argument("--before", required=True, type=Path)
    check.add_argument("--after", required=True, type=Path)
    check.add_argument("--product-id", action="append", default=[], type=UUID)
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest) if args.manifest else None
        if args.action == "snapshot":
            url = os.environ["VERBOFLEX_DATABASE_URL"]
            engine = create_engine(url, connect_args={"connect_timeout": 5}, hide_parameters=True)
            try:
                result = snapshot(sessionmaker(engine), manifest)
            finally:
                engine.dispose()
        else:
            result = compare(
                json.loads(args.before.read_text()),
                json.loads(args.after.read_text()),
                manifest,
                args.product_id,
            )
        write_private(args.output, result)
        return 0 if result.get("ok", True) else 2
    except Exception:
        # Even driver/parser exceptions can carry private values. Do not print them.
        print(
            "maintenance evidence refused: check environment, schema, manifest and private paths",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
