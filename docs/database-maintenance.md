# Database maintenance

Maintenance requires schema `0032_database_maintenance`. The workspace optimization is SQL-only: current-key metadata lookup and transaction-local `jit=off`; it introduces no cache, generation table or migration 0033. This document describes operator procedures, not evidence that a live purge has occurred.

## Policy and limits

Soft deletion hides a product and preserves its identity. An explicitly reviewed operator manifest can subsequently purge that deleted identity. Reusing its name creates a different product. No maintenance path calls Bitbucket.

| Environment variable suffix (prefix `VERBOFLEX_`) | Default | Meaning |
| --- | --- | --- |
| `MAINTENANCE_ENABLED` | `true` | Scheduled work enabled; `false` skips scheduled work. Explicit operator apply remains available. |
| `MAINTENANCE_TEMPORARY_RETENTION_DAYS` | `7` | Age of terminal, unused staging before eligibility. |
| `MAINTENANCE_DELETED_PRODUCT_RETENTION_DAYS` | absent | Automatic product purge off. Explicit opt-in value `30` enables eligibility after 30 days. Omit the variable to disable; do not set an empty string. |
| `MAINTENANCE_BATCH_ROWS` | `1000` | Total deleted rows per transaction, including graph dependencies. |
| `MAINTENANCE_MAX_ROWS_PER_RUN` | `10000` | Total deleted rows per invocation. |
| `MAINTENANCE_MAX_RUN_SECONDS` | `45` | Work budget checked between batches. |
| `MAINTENANCE_LOCK_TIMEOUT_MS` | `1000` | Maximum lock wait per statement. |
| `MAINTENANCE_STATEMENT_TIMEOUT_MS` | `5000` | Maximum statement duration. |

Beat dispatches `verboflex.maintenance.run` daily at **03:30 UTC**. The task retries transient database failures at most three times with backoff/jitter. Worker soft/hard limits are the work budget plus 10/20 seconds. One advisory lock excludes competing runners. Changing deployment environment settings requires recreating the affected backend/worker/scheduler containers; keep their policy identical for manifest apply.

Active and merely inactive products are protected. Purge excludes any product with submission reviews/batches, pending rewrites or in-flight import/preview work. Temporary cleanup removes only aged terminal staged values; jobs, executions, source references, parser/duplicate diagnostics, canonical history and review evidence remain. Pending rewrites protect staging for the entire product. Submission work also prevents temporary cleanup while in flight. An oversized immutable dependency cycle is retained, not forced through. Schema/guard drift refuses apply.

Discovery applies consumer protections before selecting up to 1,000 eligible staging executions and 100 eligible deleted products per manifest. Protected prefixes cannot starve later eligible rows. Separate bounded samples report up to 1,000 staging exclusions and 100 scheduled product exclusions; these samples are not an exhaustive inventory. Explicitly requested product IDs still receive individual outcomes. Every target is checked again under locks before deletion.

## Private evidence and exact commands

Run Python commands from `backend` with a private environment containing `VERBOFLEX_DATABASE_URL` for the intended database. Do not put credentials in command arguments, shell history, logs or committed files. `uv run python -m verboflex.cli maintenance {dry-run,apply} --help` is the authoritative argument reference. Use a private ignored evidence directory and restrictive umask:

```sh
umask 077
mkdir -p .pytest_cache/database-maintenance
```

The following variables denote operator-reviewed paths and UUIDs, never credentials. `PRODUCT_ID` must come from fresh deleted-product inventory. Repeat `--product-id` for each authorized UUID; there is no name-prefix selector. Excluding `--temporary` makes this a product-only manifest:

```sh
uv run python -m verboflex.cli maintenance dry-run \
  --product-id "$PRODUCT_ID" \
  --output .pytest_cache/database-maintenance/products-manifest.json

# Separate staging scope, when intended:
uv run python -m verboflex.cli maintenance dry-run --temporary \
  --output .pytest_cache/database-maintenance/staging-manifest.json
```

Dry run only reads the database and refuses to overwrite its output. Review the exact targets, counts, exclusions, database identity, schema revision, cutoff and policy. Store the reviewed digest in `MANIFEST_DIGEST` and keep the manifest unchanged:

```sh
uv run python -m verboflex.cli maintenance apply \
  --manifest .pytest_cache/database-maintenance/products-manifest.json \
  --digest "$MANIFEST_DIGEST"
```

To resume, run **the same command with the same manifest, digest and policy**. Custom `--batch-rows`, `--max-rows-per-run`, `--max-run-seconds` or `--temporary-retention-days` must match the dry run. Policy drift is refused. Manifests are database-specific: regenerate and review after restoring into a different database. Never copy a rehearsal manifest to live. Repeat bounded invocations only after inspecting their receipt; do not create an unattended retry loop that ignores errors.

The identity hashes PostgreSQL's persistent cluster system identifier together with the database name and catalog OID. It contains no address or credentials and remains stable across ordinary restarts. The checker uses the same calculation. The application role must be able to execute `pg_catalog.pg_control_system()`, which PostgreSQL 18 permits ordinary roles to do by default. No superuser role, security-definer wrapper, broad monitoring role or migration grant is needed. If the deployment has revoked that permission, a database administrator must explicitly grant this function's execution to the maintenance application role; maintenance otherwise refuses with `database_identity_unavailable`. There is no name/OID-only fallback. See [PostgreSQL control data functions](https://www.postgresql.org/docs/18/functions-info.html#FUNCTIONS-CONTROLDATA).

This boundary supports logical dump/restore into independent clusters or different databases. A physical cluster clone retains the system identifier and may retain the database name/OID; do not carry maintenance manifests into such a clone. Separately operated physical clones require a separately provisioned deployment discriminator before using this workflow there; that topology is outside the current dump/restore procedure.

Exit 0 means all targets in that manifest completed, including a no-op repeat; it does not mean excluded products were removed. Exit 2 means `partial`, `skipped` or another incomplete summary. `partial/budget` can resume; `partial/changed`, `inflight`, `pending_rewrite`, `submission_evidence`, `external_reference` or `oversized_cycle` requires investigation. `skipped/busy` indicates a concurrent runner. CLI exit 1 is a sanitized refusal. Durable failed/interrupted runs may already contain committed batches; resume rather than assuming rollback of the whole run.

Read durable results without translation text or credentials:

```sql
SELECT digest, status, error_code, created_at, updated_at
FROM maintenance_runs ORDER BY created_at DESC;
SELECT run_digest, kind, target_id, counts
FROM maintenance_batches ORDER BY id;
```

## Backup, rehearsal and deployment sequence

Current daily backups and operator restore are described in [backup-restore.md](backup-restore.md). The sequence below records the original migration-0032 maintenance rehearsal; its historical dataset counts are not the current application inventory. A successful daily restore does not authorize purges or close the maintenance-specific rehearsal gates.


1. Independently review migration 0032, exact-row DELETE authorization, consumer exclusions, bounded cycles, race handling, receipt validation and the SQL performance evidence. Fix all high/critical findings. The final schema has no 0033 or cache invalidation mechanism to review.
2. Verify the private backup metadata in `backend/.pytest_cache/database-maintenance/backup.json`, archive permissions and readability. A custom-format archive is required before purge. For the local PostgreSQL container, run from the repository root with `BACKUP` set to a private absolute path:

   ```sh
   umask 077
   docker exec verboflex-postgres-1 sh -c \
     'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$BACKUP"
   chmod 600 "$BACKUP"
   docker exec -i verboflex-postgres-1 pg_restore --list < "$BACKUP" > /dev/null
   ```

   A successful list alone is not restore proof. Restore into a **fresh generated, owned disposable database** using `pg_restore --exit-on-error --no-owner --no-privileges`, then migrate that database to 0032 with all triggers/FKs enabled. The existing benchmark's `owned_database(dump=..., postgres_container=...)` context manager creates only its generated destination, performs this restore/migration and drops only that database on exit. Never restore over the shared application database. Record private archive SHA-256, size, timestamp and rehearsal schema in the operator evidence.
3. Capture protected snapshots on the restored database, build its actual manifest, apply/resume within bounds, invoke the scheduled worker seam, then compare snapshots and representative API/service projections. Require unchanged active canonical/shared rows and account for every exact requested UUID. A blocked product remains retained with its specific reason. A benchmark-only restore does not establish purge rehearsal.
4. Resolve the nine authorized historical deleted products from fresh UUID/deleted-at inventory; never select by display-name heuristics. Keep the current active product out of every purge manifest. Review protected dependencies and exclusions. The expected active baseline is 1,343 keys and 1,906 values/revisions; refresh those counts and investigate concurrent changes before applying.
5. Deploy reviewed code with the existing Compose configuration. Build backend/frontend, run `alembic upgrade head`, and recreate only the required backend, worker, scheduler and frontend services with existing volumes. Check `alembic current` is `0032_database_maintenance`. Keep automatic deleted-product retention absent unless explicitly opted in. The parent owns this shared deployment.
6. Capture fresh live protected snapshots, build/review the exact live manifest and confirm scope has not widened from rehearsal. Run bounded apply/resume and reconcile receipts. No source executor may infer live completion from passing disposable tests.
7. Run ordinary per-table `VACUUM (ANALYZE)` on changed tables outside any transaction, then capture sizes/counts again. For example, through the existing local container:

   ```sh
   docker exec verboflex-postgres-1 sh -c \
     'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "VACUUM (ANALYZE) staged_translation_values;"'
   ```

   Repeat for reviewed tables appearing in durable batch counts. Ordinary vacuum reclaims reusable table space and updates statistics; it need not return the same number of bytes to the OS. Do not use routine `VACUUM FULL`, truncate shared tables, reset schemas or replace volumes.
8. Compare protected snapshots and target receipts, then check key pages, detail/source context, product summary and provider-free writeback selection. Verify backend health and worker/beat task registration. Do not hide active-data changes as volatility: preserve the mismatch report and attribute any authorized concurrent write separately.
9. Perform built browser read acceptance for the active product: first and continuation pages, search/language filters, details/source history and existing edit/read-only affordances. Create no provider writes.
10. Record sanitized final evidence paths and every requested product outcome. Keep same-data query benchmark results separate from post-cleanup live measurements; persistent Docker VM/static latency is a separate observation.

## Preservation snapshots and comparison

The read-only tool uses an explicit environment URL and never applies maintenance. Run snapshots immediately before and after maintenance, with other writers quiescent. Snapshot mode requires 0032 and uses a read-only repeatable-read transaction, fixed-size streaming batches and strict hashes of all columns. There are no excluded volatile columns. It protects all nondeleted products, including inactive ones, plus whole shared identity/repository/connection tables and submission evidence. Source references and all historical revisions are included. Only explicitly manifested staging targets are separated from protected staging; expected staging removal cannot mask a canonical row change.

```sh
uv run python ../tools/verify_database_maintenance.py snapshot \
  --manifest .pytest_cache/database-maintenance/products-manifest.json \
  --output .pytest_cache/database-maintenance/before.json

# After bounded apply/resume; use the SAME manifest for classification.
uv run python ../tools/verify_database_maintenance.py snapshot \
  --manifest .pytest_cache/database-maintenance/products-manifest.json \
  --output .pytest_cache/database-maintenance/after.json

uv run python ../tools/verify_database_maintenance.py compare \
  --before .pytest_cache/database-maintenance/before.json \
  --after .pytest_cache/database-maintenance/after.json \
  --manifest .pytest_cache/database-maintenance/products-manifest.json \
  --product-id "$PRODUCT_ID" \
  --output .pytest_cache/database-maintenance/comparison.json
```

Repeat `--product-id` for **every independently approved UUID**, including exclusions. Comparison refuses extra/missing manifest products, unknown/active UUIDs, wrong database/schema or protected hash drift. It reports `purged`, `retained` with the manifest exclusion reason, or `incomplete` per requested product and validates deletion counts against durable receipts. Exit 0 requires preservation and fully accounted outcomes; an incomplete target fails. Excluded products are an explicit retained outcome, never counted as purged. Outputs contain IDs, counts, hashes and safe outcome codes; files are created exclusively with mode 0600. Keep them private even though row contents are not emitted. The tool does not replace API/browser acceptance or independently authorize a manifest.

Sizes are observational and do not participate in strict row comparisons:

```sql
SELECT pg_database_size(current_database()) AS database_bytes;
SELECT relname, n_live_tup, n_dead_tup,
       pg_relation_size(relid) AS heap_bytes,
       pg_indexes_size(relid) AS index_bytes,
       pg_total_relation_size(relid) AS total_bytes
FROM pg_stat_user_tables ORDER BY relname;
```

Statistics estimates are not exact row counts; the preservation snapshots count streamed rows. Compare both before/after sizes and exact counts. PostgreSQL may reuse freed space without reducing the database-size number.

## Recovery

Disable scheduled work with `VERBOFLEX_MAINTENANCE_ENABLED=false` and recreate worker/scheduler if further work must stop. An already running bounded transaction can finish; inspect durable receipts. Restore the setting to resume scheduled policy work. Scheduled recovery only resumes scheduled manifests, never an operator-only product authorization.

Scheduled recovery also requires the current database identity. Foreign pending manifests restored from a backup are skipped permanently on this destination; their manifest, status, timestamps and committed receipts stay intact as source audit history. The scheduler builds a fresh local manifest and can resume it normally. An explicit apply with the foreign manifest still refuses before changing either application data or that audit record.

Source or migration rollback does **not** recreate purged data. Recovery requires the verified private archive, an explicit restore destination/cutover procedure, the matching encryption secrets and reconciliation of legitimate writes since the backup. Keep the source database intact while validating a separate restore. Never erase maintenance receipts to make a run look clean.
