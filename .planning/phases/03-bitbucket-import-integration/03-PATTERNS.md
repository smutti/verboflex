# Phase 3: Bitbucket Import Integration - Pattern Map

**Mapped:** 2026-09-02
**Files analyzed:** 34 logical new/modified file targets
**Analogs found:** 34 / 34
**Research input:** Skipped by orchestration; target files are inferred from `03-CONTEXT.md`, `03-UI-SPEC.md`, the roadmap, and the current Phase 2 implementation.

## File Classification

Paths marked “likely new” follow the repository's current feature naming. Phase 3 decision D-05 leaves exact names to planning, so the planner may rename them while retaining the assigned analog and ownership boundary.

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/src/verboflex/integrations/bitbucket/client.py` | service / provider adapter | request-response, streaming | same file | exact |
| `backend/src/verboflex/integrations/bitbucket/urls.py` | utility / provider allowlist | request-response | same file | exact |
| `backend/src/verboflex/services/bitbucket_oauth.py` | service | request-response, credential lifecycle | same file | exact |
| `backend/src/verboflex/services/repository_discovery.py` | service | bounded file-I/O, batch | same file | exact |
| `backend/src/verboflex/models/import_job.py` (likely new) | model | CRUD, event-driven | `backend/src/verboflex/models/preview_job.py` | role-match |
| `backend/src/verboflex/models/__init__.py` | config / model registry | startup metadata | same file | exact |
| `backend/alembic/versions/0012_import_baselines.py` (likely new) | migration | batch / schema evolution | `0006_preview_jobs.py`, `0011_active_revision_revalidations.py` | role-match |
| `backend/src/verboflex/services/import_jobs.py` (likely new) | service | event-driven, CRUD, batch | `backend/src/verboflex/services/preview_jobs.py` | role-match |
| `backend/src/verboflex/worker/import_tasks.py` (likely new) | worker | event-driven, bounded file-I/O | `backend/src/verboflex/worker/preview_tasks.py` | exact-role |
| `backend/src/verboflex/worker/celery_app.py` | config | event-driven | same file | exact |
| `backend/src/verboflex/core/config.py` | config | startup / request-response | same file and preview timeout settings | exact |
| `backend/src/verboflex/schemas/imports.py` (likely new) | schema / model | request-response | `backend/src/verboflex/schemas/previews.py` | role-match |
| `backend/src/verboflex/api/v1/routes/admin_imports.py` (likely new) | controller / route | request-response, event dispatch | `backend/src/verboflex/api/v1/routes/admin_previews.py` | role-match |
| `backend/src/verboflex/api/v1/router.py` | route registry | request-response | same file | exact |
| `backend/src/verboflex/schemas/admin_bitbucket.py` | schema / model | request-response | same file | exact |
| `backend/src/verboflex/api/v1/routes/admin_bitbucket.py` | controller / route | request-response | same file | exact |
| `backend/src/verboflex/services/mappings.py` | service | CRUD, server-ordered projection | same file | exact |
| `backend/src/verboflex/schemas/admin_mappings.py` | schema / model | request-response | same file | exact |
| `backend/src/verboflex/api/v1/routes/admin_mappings.py` | controller / route | request-response | same file | exact |
| `backend/src/verboflex/services/products.py` | service | CRUD, aggregate query | same file | exact |
| `backend/src/verboflex/schemas/admin_products.py` | schema / model | request-response | same file | exact |
| `backend/src/verboflex/api/v1/routes/admin_products.py` | controller / route | request-response | same file | exact |
| `frontend/openapi.json`, `frontend/src/api/client/**` | generated client / config | request-response | current generated Phase 2 client | exact process |
| `frontend/src/features/admin/imports/useImportPolling.ts` (likely new) | hook | request-response, event-driven polling | `frontend/src/features/admin/previews/usePreviewPolling.ts` | role-match |
| `frontend/src/features/admin/imports/PublishedMappingImports.tsx` (likely new) | component | request-response | `frontend/src/features/admin/mappings/ProductMappingsPage.tsx` | role-match |
| `frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx` (likely new) | component | request-response, confirmation | `BitbucketConnectionPage.tsx` alert-dialog flow | role-match |
| `frontend/src/features/admin/bitbucket/BitbucketConnectionPage.tsx` | component | request-response | same file | exact |
| `frontend/src/features/admin/mappings/ProductMappingsPage.tsx` | component | request-response | same file | exact |
| `frontend/src/features/admin/products/ProductOverviewPage.tsx` | component | request-response | same file | exact |
| `backend/tests/integration/test_bitbucket_oauth.py`, `test_bitbucket_http_adapter.py`, new `test_import_jobs.py` | test | request-response, event-driven | existing provider and preview integration tests | role-match |
| `backend/tests/integration/test_migrations.py`, API/OpenAPI tests | test | migration, request-response | existing migration and preview contract tests | role-match |
| `backend/tests/architecture/test_provider_boundaries.py`, `test_background_boundaries.py` | test | static analysis / policy | same files | exact |
| frontend import hook/component tests plus existing page/client tests | test | request-response, event-driven | preview polling and Phase 2 admin component tests | role-match |
| `frontend/e2e/admin-configuration.spec.ts` | test | end-to-end request-response | same Phase 2 admin E2E flow | role-match |

## Pattern Assignments

### Bitbucket capability and import-read boundary

**Targets:**

- `backend/src/verboflex/integrations/bitbucket/client.py`
- `backend/src/verboflex/integrations/bitbucket/urls.py`
- `backend/src/verboflex/services/bitbucket_oauth.py`
- `backend/src/verboflex/services/repository_discovery.py`
- Bitbucket schemas/routes/UI and their tests

**Primary analogs:** the same four backend files. Extend these boundaries in place; do not introduce a second HTTP client, credential authority, or URL validator.

**Imports and dependency direction** — `client.py` lines 14-28:

```python
from verboflex.core.config import Settings
from verboflex.integrations.bitbucket.urls import (
    repository_branch_url,
    repository_branches_url,
    repository_metadata_url,
    repository_source_url,
    validate_bitbucket_api_url,
    validate_repository_relative_path,
)
from verboflex.services.bitbucket_oauth import (
    REPOSITORY_SCOPE,
    BitbucketCredentialLease,
    OAuthConnectionUnavailable,
    OAuthGenerationRejected,
)
```

Keep URL construction below `integrations/bitbucket/urls.py`, transient credential acquisition below `services/bitbucket_oauth.py`, and provider response projection below the adapter. Import services should depend on a narrow protocol, as `repository_discovery.py` does at lines 42-72, rather than constructing HTTP clients.

**One pooled, no-redirect, no-hidden-retry client** — `client.py` lines 108-125:

```python
timeout = httpx.Timeout(
    connect=float(settings.bitbucket_http_connect_timeout_seconds),
    read=float(settings.bitbucket_http_read_timeout_seconds),
    write=float(settings.bitbucket_http_write_timeout_seconds),
    pool=float(settings.bitbucket_http_pool_timeout_seconds),
)
resolved_transport = transport or httpx.AsyncHTTPTransport(retries=0)
self._client = httpx.AsyncClient(
    headers={"Accept": "application/json", "Accept-Encoding": "identity"},
    timeout=timeout,
    follow_redirects=False,
    transport=resolved_transport,
    trust_env=False,
)
```

Locked D-11 supersedes the roadmap's older generic “bounded retry” wording: timeout, 429, provider unavailable, authentication, permission, and missing source all stop the current execution. Preserve `retries=0`; only an administrator starts the next execution.

**Exact branch to immutable commit** — `client.py` lines 164-181:

```python
async def resolve_repository_branch(..., branch: str) -> BitbucketBranch:
    url = repository_branch_url(
        workspace=workspace,
        repository_slug=repository_slug,
        branch=branch,
    )
    resolved = self._parse_branch(await self._read_json(session, url=url))
    if resolved.name != branch:
        raise BitbucketProviderReadError(kind="invalid_source")
    return resolved
```

Branch names stay opaque. An import must resolve each configured side again, then use only its returned 40-character commit for tree/file reads. For `separate` mappings, treat both sides as one mapping-level consistency boundary.

**Bounded snapshot traversal** — `repository_discovery.py` lines 229-317:

```python
resolved = await adapter.resolve_repository_branch(..., branch=branch)
if resolved.name != branch:
    raise BitbucketProviderReadError(kind="invalid_source")

while directories:
    ...
    if pages >= SOURCE_DISCOVERY_BUDGET.max_pages:
        raise BitbucketProviderReadError(kind="limit_exceeded")
    page = await adapter.list_repository_source_page(
        ...,
        commit_hash=resolved.commit_hash,
        directory_path=directory_path,
        next_url=next_url,
    )
    ...
    if entry_count > SOURCE_DISCOVERY_BUDGET.max_entries:
        raise BitbucketProviderReadError(kind="limit_exceeded")

return RepositorySourceSnapshot(
    commit_hash=resolved.commit_hash,
    files=tuple(files),
    total_bytes=total_bytes,
)
```

Reuse the current A-03 page, entry, depth, candidate-file, per-file-byte, and total-byte ceilings. Add exact file references/digests to the import result without putting raw source bytes into public schemas or logs. A rewritten-baseline delta must be complete or non-confirmable.

**Credential generation checked before and after the response** — `client.py` lines 332-408:

```python
lease = self._credential_leases.acquire_repository_read_lease(session)
self._credential_leases.require_current_repository_read_lease(session, lease)
async with self._client.stream(
    "GET",
    validated_url,
    headers={"Authorization": f"Bearer {lease.access_token}"},
) as response:
    ...
self._credential_leases.require_current_repository_read_lease(session, lease)
```

Continue mapping status codes and transport failures to closed kinds. Add an explicit rate-limit kind for HTTP 429; do not retain provider bodies. Keep connection/authentication, permission, rate limit, not found, timeout, unavailable, and limit failures distinguishable to the service, but project only stable codes and the UI contract's fixed copy.

**OAuth transaction and generation pattern** — `bitbucket_oauth.py` lines 245-303 and 515-534:

```python
with session.begin():
    connection = self._lock_connection(session)
    access_token, expires_in = self._exchange_and_validate()
    ...
    status = self._persist_access_only(...)

if (
    not isinstance(access_token, str)
    or not access_token
    or token_type.casefold() != "bearer"
    or scope != REPOSITORY_SCOPE
    or not isinstance(expires_in, int)
    or expires_in < 1
):
    raise OAuthConnectionUnavailable(CONNECTION_UNAVAILABLE_MESSAGE)
```

Replace the Phase 2 `repository` expectation with the locked Phase 3 `pullrequest:write` capability contract and a closed server-side capability profile. Existing read-only generations become `Reauthorization required`; a cached success never grants a later read. The browser must receive readiness fields, never raw scope strings.

**Provider-operation allowlist rule:** update the AST policy in `backend/tests/architecture/test_provider_boundaries.py`, but preserve the runtime Phase 3 guarantee that every provider resource request remains `GET`. D-09 allows only source reads and the future branch-create/source-commit/open-PR families; D-10 means no public mutation adapter method or mutating HTTP request is executable yet. Merge/approve/decline/admin/delete must remain structurally absent.

**Testing pattern** — `test_bitbucket_http_adapter.py` lines 81-217:

```python
adapter = BitbucketHttpAdapter(
    settings=Settings(),
    credential_leases=authority,
    transport=httpx.MockTransport(provider),
)
...
for slug in ("redirected", "safe-redirect", "failure", "retry", "wrong-scope"):
    with pytest.raises(BitbucketProviderReadError) as captured:
        await adapter.read_repository_metadata(...)
    diagnostic = f"{captured.value!r} {captured.value}"
    assert ACCESS_TOKEN not in diagnostic
    assert PROVIDER_BODY not in diagnostic
...
assert attempts["failure"] == 1
assert attempts["retry"] == 1
```

Extend this matrix with 429, new capability headers, branch ancestry, complete file-delta bounds, legacy read-only generations, and a provider spy proving zero POST/PUT/PATCH/DELETE calls.

---

### Durable logical import, baseline, and reconciliation persistence

**Targets:**

- `backend/src/verboflex/models/import_job.py` (likely new)
- `backend/src/verboflex/models/__init__.py`
- `backend/alembic/versions/0012_import_baselines.py` (likely new)
- `backend/src/verboflex/services/import_jobs.py` (likely new)

**Analog:** `models/preview_job.py` plus `services/preview_jobs.py`.

**Model constraints and payload/state coupling** — `models/preview_job.py` lines 26-102:

```python
class PreviewJob(Base):
    __tablename__ = "preview_jobs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed', 'timed_out')",
            name="state_value",
        ),
        CheckConstraint("attempt > 0", name="positive_attempt"),
        CheckConstraint(
            "(state = 'queued' AND started_at IS NULL AND finished_at IS NULL "
            "AND result IS NULL AND error_code IS NULL) OR ...",
            name="state_payload",
        ),
        ForeignKeyConstraint(
            ["product_id", "candidate_revision_id"],
            ["product_revisions.product_id", "product_revisions.id"],
            ondelete="CASCADE",
        ),
        ...
    )
```

Use UUID identity, explicit check constraints, composite ownership FKs, timestamps with timezone, and indexes matching status/latest-execution queries. Import persistence must bind the published product revision, mapping, repository side(s), connection generation, exact branch, exact commit, and every file reference.

Recommended responsibility within one model module:

- one logical import row unique to a published mapping;
- one active last-success baseline, atomic across both sides;
- exact baseline/latest-execution file-reference rows or a bounded closed JSON representation;
- one current rewrite proposal with old/new commits and a complete ordered delta;
- latest capability result, its timestamp, and source identity;
- retry count and latest execution timestamps.

The public model exposes only the last successful baseline and current logical execution, not attempt history.

**Critical divergence — do not copy preview retry row creation.** `preview_jobs.py` lines 653-680 creates a new row and increments `attempt` after failure. Phase 3 D-13 requires manual retry to reuse the same logical import record, replace current status/error, increment `retry_count`, and update latest execution time. Keep the logical import UUID stable. Any internal execution/reference storage must not create a second visible logical attempt or a UI history surface.

**Transaction and enqueue pattern** — `preview_jobs.py` lines 626-705:

```python
created = False
with session.begin():
    revision, mapping = _locked_mapping(...)
    connection_generation = _connected_generation(session)
    ...
    session.add(row)
    session.flush()
    created = True
    record = _record(row, is_current=...)

if created:
    try:
        enqueuer(record.id)
    except Exception:
        with session.begin():
            row = session.execute(
                select(PreviewJob).where(PreviewJob.id == record.id).with_for_update()
            ).scalar_one()
            if row.state == "queued":
                row.state = "failed"
                row.error_code = "enqueue_failed"
```

Persist durable queued state before dispatch; enqueue only the UUID after commit. If dispatch fails, replace the current logical state with a bounded failure. Run/refresh/retry must be single-flight under a mapping/product lock.

**Atomic rewrite confirmation sidecar pattern** — `preview_jobs.py` lines 901-974:

```python
with session.begin():
    row = session.execute(
        select(PreviewJob).where(PreviewJob.id == job_id).with_for_update()
    ).scalar_one_or_none()
    ...
    if _current_failure_code(session, row, for_update=True) is not None:
        raise PreviewJobConflict(...)
    ...
    sidecar = ActiveRevisionRevalidationConfirmation(...)
    session.add(sidecar)
    session.flush()
```

For imports, re-check mapping/revision, proposal identity, connection generation, exact proposed commits, and complete delta under lock. Confirm both sides of a separate mapping in one transaction. A stale, truncated, unreadable, or over-budget proposal returns 409/bounded failure and cannot partially update the active baseline.

**Last-success preservation:** worker failure changes only the current execution status/capability result. It must not clear or replace the active baseline. The mapping becomes `May be stale` only when a last-success baseline exists; an initial failure is `Import failed` with no baseline.

**Migration pattern** — `0006_preview_jobs.py` lines 20-129 and `0011_active_revision_revalidations.py` lines 33-172:

```python
def upgrade() -> None:
    op.create_table(
        "preview_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), ...),
        ...,
        sa.CheckConstraint(...),
        sa.ForeignKeyConstraint(...),
        sa.PrimaryKeyConstraint("id", ...),
    )
    op.create_index(...)

def downgrade() -> None:
    op.drop_index(...)
    op.drop_table("preview_jobs")
```

Make upgrade/downgrade reversible, name every constraint/index, test data preservation, and import new mapped classes from `models/__init__.py` so Alembic sees the full graph.

---

### Worker execution and durable conditional transitions

**Targets:**

- `backend/src/verboflex/worker/import_tasks.py` (likely new)
- `backend/src/verboflex/worker/celery_app.py`
- import timeout/watchdog settings in `backend/src/verboflex/core/config.py`

**Analog:** `worker/preview_tasks.py`.

**Process-owned adapter lifecycle** — `preview_tasks.py` lines 96-118:

```python
async def _production_preview(identity: PreviewJobIdentity) -> dict[str, object]:
    settings = get_settings()
    oauth_service = BitbucketOAuthService(
        settings=settings,
        token_exchange=BitbucketOAuthTokenExchange(),
    )
    adapter = BitbucketHttpAdapter(
        settings=settings,
        credential_leases=oauth_service,
    )
    try:
        return await _process_preview(..., adapter=adapter)
    finally:
        await adapter.aclose()
```

Construct the provider client only in worker execution, close it in `finally`, and give the processor a durable identity loaded from PostgreSQL.

**UUID-only Celery task** — `preview_tasks.py` lines 132-151:

```python
@app.task(
    name="verboflex.preview.run",
    acks_late=True,
    reject_on_worker_lost=True,
    serializer="json",
    ignore_result=True,
)
def run_preview_job(job_id: str) -> None:
    try:
        durable_job_id = UUID(job_id)
    except (TypeError, ValueError):
        return
    execute_preview_job(SessionFactory, job_id=durable_job_id, processor=_bounded_processor)
```

The import task payload is only the logical import UUID. Do not pass branches, commits, paths, tokens, errors, or source bytes through Redis. Keep JSON serialization, late acknowledgement, worker-loss rejection, hard/soft limits, and PostgreSQL-authoritative status.

**Conditional terminalization** — `preview_jobs.py` lines 1449-1548:

```python
row = session.execute(
    select(PreviewJob).where(PreviewJob.id == job_id).with_for_update()
).scalar_one_or_none()
if row is None or row.state != "queued":
    return None
...
if row is None or row.state != "running" or not _matches_started_identity(row, identity):
    return
```

Import completion must compare the UUID, execution/retry counter, mapping/revision identity, and connection generation so a late worker cannot overwrite a newer manual retry or confirmed baseline. Add a bounded watchdog if worker-loss recovery is part of the plan; register it in the existing Celery app/beat, never in FastAPI.

`backend/tests/architecture/test_background_boundaries.py` lines 22-41 is mandatory regression armor: route modules may call an injected service enqueuer, but must not import worker modules or call `.delay()`, `.apply_async()`, or task `.run()`.

---

### FastAPI routes, schemas, and projections

**Targets:** import schemas/routes/router plus the existing mapping, product, and Bitbucket schemas/routes/services.

**Analog:** `schemas/previews.py`, `routes/admin_previews.py`, and the existing mapping/product projections.

**Closed Pydantic contracts** — `schemas/previews.py` lines 23-39 and 117-149:

```python
class AdminPreviewJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_candidate_version: Annotated[int, Field(ge=1)]
    commits: Annotated[list[AdminPreviewCommitRequest], Field(min_length=1, max_length=2)]

class AdminPreviewJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["queued", "running", "succeeded", "failed", "timed_out"]
    ...
    error_code: Literal[...] | None
```

Use `extra="forbid"`, bounded list/string fields, closed `Literal` states and error codes, and explicit direct/keys/translations side roles. Import responses may expose repository identity, opaque branch, exact commit, path, timestamps, retry count, readiness, and bounded deltas; they must exclude token/ciphertext, raw OAuth scopes, provider bodies, raw source content, unsafe URLs, stack traces, and Celery internals.

**Auth and dependency pattern** — `admin_previews.py` lines 43-67:

```python
router = APIRouter(tags=["admin-previews"])
AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.ADMIN))]
AdminSession = Annotated[Session, Depends(get_db_session, use_cache=False)]

def get_preview_job_enqueuer(request: Request) -> PreviewEnqueuer:
    candidate = getattr(request.app.state, "preview_job_enqueuer", None)
    if candidate is None:
        return enqueue_preview_job
    if not callable(candidate):
        raise RuntimeError("preview job enqueuer unavailable")
    return cast(PreviewEnqueuer, candidate)
```

Every import list/status/mutation/reconciliation route is admin-only. Use an injected enqueuer seam for tests. Candidate visibility and route parameters never grant authority; service code must resolve the product's published revision and mapping ownership.

**202 create plus database status read** — `admin_previews.py` lines 226-278:

```python
@router.post(
    "/admin/products/{product_id}/candidate/mappings/{mapping_id}/preview-jobs",
    operation_id="create_admin_preview_job",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AdminPreviewJobResponse,
    responses=RESPONSES,
)
async def create_admin_preview_job(...):
    record = create_or_reuse_preview_job(..., enqueuer=enqueuer)
    return _response(record)

@router.get("/admin/preview-jobs/{job_id}", ...)
async def get_admin_preview_job(...):
    record = get_preview_job(session, job_id=job_id)
    return _response(record)
```

Recommended resource shape: a server-ordered published-mapping import collection, one start/refresh/retry mutation that returns the same logical import identity, one status/detail read, one rewrite-comparison read, and one atomic confirmation mutation. Do not add cancel, schedule, import-all, provider-write, or attempt-history endpoints.

**Bounded error translation** — `admin_previews.py` lines 172-188:

```python
if isinstance(error, PreviewJobNotFound):
    raise HTTPException(status_code=404, detail="Preview unavailable") from error
if isinstance(error, PreviewJobConflict):
    raise HTTPException(status_code=409, detail="Preview identity conflict") from error
if isinstance(error, PreviewConnectionUnavailable):
    raise HTTPException(status_code=503, detail="Preview connection unavailable") from error
raise error
```

Map domain failures once in the route. Use stable public status/error codes that select the UI contract's fixed messages. Never surface caught provider exception text.

**Published mapping order and ownership** — `services/mappings.py` lines 563-595:

```python
if product is None or revision_id not in {
    product.active_revision_id,
    product.candidate_revision_id,
}:
    raise MappingNotFound("revision unavailable")
revision = session.scalar(
    select(ProductRevision).where(
        ProductRevision.id == revision_id,
        ProductRevision.product_id == product.id,
    )
)
return _list_revision_mapping_page(..., revision=revision, ...)
```

Build the import collection only from the exact active/published revision. Preserve `_list_revision_mapping_page` server order; do not join candidate rows into the import projection. The Mappings API may be extended with a dedicated `AdminPublishedMappingImportResponse` rather than adding operational state to the candidate edit DTO.

**Product stale count:** extend `ProductRecord` (`services/products.py` lines 57-65), `AdminProductResponse` (`schemas/admin_products.py` lines 58-67), and the route `_response` (`admin_products.py` lines 74-81) with one server-computed `affected_mapping_count`. Count only active-revision mappings whose latest execution failed while a successful baseline remains. The frontend must not derive the count from a paginated mapping page.

**Bitbucket capability projection:** extend `AdminBitbucketStatusResponse` in `schemas/admin_bitbucket.py` with closed readiness fields for source reads, future branch/source-commit capability, and future PR capability. Update `_status_response` in `admin_bitbucket.py` lines 89-95. Do not expose the new raw OAuth scope string.

Register any new route module exactly as `api/v1/router.py` lines 5-30 imports modules and calls `api_router.include_router(...)`.

---

### Generated client and frontend server state

**Targets:** generated client files, the new import hook/components, and the existing Bitbucket/Mappings/Overview pages.

**Generated transport rule:** FastAPI/OpenAPI is the only contract source. Add frozen `operation_id` values, export OpenAPI, run the existing `frontend/package.json` scripts (`api:generate`, then `api:check`), and import only generated functions/types. Never hand-edit `frontend/src/api/client/**` or define handwritten request/response mirrors.

**Stale-load guard** — `BitbucketConnectionPage.tsx` lines 97-120:

```tsx
const loadConnection = useCallback(async (showLoading = true) => {
  const generation = ++loadGenerationRef.current;
  ...
  const result = await getAdminBitbucketStatus({ auth: accessToken });
  if (generation !== loadGenerationRef.current) return false;
  if (result.data === undefined) throw new Error();
  setLoadState({ status: "ready", connection: result.data });
  return true;
}, [accessToken]);
```

Use generation/abort identity for page loads and polls. Keep the previous visible capability profile on mutation failure; never infer authority from a prior successful read.

**Duplicate-submit guard and server refetch** — `BitbucketConnectionPage.tsx` lines 142-171:

```tsx
if (connectionPendingRef.current) return;
connectionPendingRef.current = true;
setConnectionPending(action);
try {
  const result = await generatedMutation(...);
  if (result.data === undefined) {
    setConnectionError(true);
    return;
  }
  const refreshed = await loadConnection(false);
  ...
} finally {
  connectionPendingRef.current = false;
  setConnectionPending(null);
}
```

Apply both state and ref guards to run/refresh/retry and baseline confirmation. No optimistic status or baseline update; render only fresh backend projections. Sonner is success-only (`Import started`, `Baseline updated`), never an error channel.

**Exact polling schedule and identity** — `usePreviewPolling.ts` lines 28-55 and 102-159:

```tsx
export function nextPreviewPollDelay(elapsedMs: number) {
  if (elapsedMs < 30_000) return Math.min(2_000, 30_000 - elapsedMs);
  if (elapsedMs < 90_000) return Math.min(5_000, 90_000 - elapsedMs);
  return null;
}

const result = await getAdminPreviewJob(...);
if (
  !mountedRef.current ||
  identityRef.current !== expectedIdentity ||
  result.data === undefined ||
  previewJobIdentity(result.data) !== expectedIdentity
) return;
if (result.data.state !== lastStateRef.current) {
  announcementRef.current?.(STATE_LABELS[result.data.state]);
}
```

Copy the 2-second through 30 seconds, then 5-second through 90 seconds schedule exactly. For imports, identity includes the stable logical import UUID plus current execution/retry counter and published mapping/revision identity. Stop at terminal/review-required state. After 90 seconds show `Automatic status updates paused` and `Refresh status`; unmount never cancels worker work. Announce transitions only.

**Published mappings composition** — insert `Published mapping imports` before the existing candidate list/form in `ProductMappingsPage.tsx`. Copy the desktop/mobile dual rendering at lines 878-945:

```tsx
<div className="hidden md:block">
  <Table aria-label="Mappings">...</Table>
</div>
<div className="grid min-w-0 max-w-full divide-y md:hidden" ...>
  {mappings.map((mapping) => (
    <article key={mapping.id} className="grid min-w-0 gap-3 py-4">...</article>
  ))}
</div>
```

Use the UI contract's columns in server order: Mapping, Import status, Last successful baseline, Latest execution, Actions. Candidate editing remains separate and unchanged. Long branches, paths, repositories, and commits use monospace/local focusable overflow; no page-level horizontal scroll at 320px.

**Rewrite dialog control pattern** — `BitbucketConnectionPage.tsx` lines 174-207 and 355-393:

```tsx
function changeRevokeOpen(open: boolean) {
  if (revokePendingRef.current) return;
  setRevokeOpen(open);
  if (!open) queueMicrotask(() => revokeTriggerRef.current?.focus());
}
...
<AlertDialog open onOpenChange={changeRevokeOpen}>...</AlertDialog>
```

Adapt this to `Review rewritten source history`: load comparison details after opening, show old/new commits and complete added/modified/removed rows, and omit confirm on incomplete/truncated/stale/failed data. During confirmation disable both buttons and block Escape/outside close. On cancel/success restore focus to `Review baseline change`; on concurrent conflict keep the dialog open and focus the bounded error.

**Capability page:** replace `Read-only repository access` only when the generated response proves the Phase 3 profile. Add the flat `Capability profile` definition list below the existing status section; keep `max-w-3xl`, existing connect/reconnect/revoke behavior, and the updated revocation copy from the UI contract.

**Overview count:** add the server-owned badge directly after lifecycle actions and before revision tabs (`ProductOverviewPage.tsx` lines 229-287). Hide when zero; render exact singular/plural copy and no action/link/banner.

---

### Tests and quality-gate files

**Backend integration pattern** — `test_preview_jobs.py` lines 644-705:

```python
created = asyncio.run(_request("POST", path, access_token=admin_token, json=...))
assert created.status_code == 202
assert created.json()["state"] == "queued"
assert enqueuer.payloads == [(created.json()["id"],)]
...
with start_worker(test_celery, pool="solo", perform_ping_check=False, loglevel="ERROR"):
    ...
```

Add one real API → durable row → Celery worker → terminal PostgreSQL flow. Cover initial import, fast-forward, rewritten branch proposal, atomic direct/separate confirmation, failed refresh preserving baseline, first-import failure, manual retry on the same logical UUID, late-worker suppression, watchdog recovery, capability revalidation every execution, and zero provider writes.

`test_preview_jobs.py` lines 992-1025 shows bounded enqueue failure and retry coverage, but Phase 3 assertions must additionally prove the logical import UUID is unchanged and current error/status is replaced.

**Authorization pattern** — `test_preview_jobs.py` lines 3070-3125 loops through every read/mutation route and asserts anonymous 401 and viewer 403 before happy-path work. Apply the same matrix to import start/refresh/retry/status/comparison/confirmation.

**Frontend polling pattern** — `usePreviewPolling.test.ts` lines 73-208 uses fake timers to assert exact delays, transition-only announcements, 90-second pause, manual refresh, terminal stop, and superseded-identity rejection. Clone this matrix for `useImportPolling` with import states and stable logical identity.

**Component safety pattern:**

- `BitbucketConnectionPage.test.tsx` lines 98-124 proves stable loading/retry and secret-free errors.
- `BitbucketConnectionPage.test.tsx` lines 337-404 proves duplicate-submit prevention, named confirmation, and server-authoritative failure preservation.
- `ProductMappingsPage.test.tsx` lines 215-253 proves one-action/one-cursor loading and bounded responsive collections.
- `ProductConfiguration.test.tsx` lines 2591-2614 proves desktop table/mobile article dual rendering and keyboard-focusable local overflow.
- `ProductConfiguration.test.tsx` lines 1920-1978 proves bounded Overview loading, unmount cancellation, and retry behavior.

Add all UI-SPEC Verification Hooks: every state/action label, retained baseline, first failure, retry replacement without history, polling pause, direct/separate/zero-delta reconciliation, incomplete-delta blocking, focus restoration/lock, capability reauthorization, zero/singular/plural product count, long-text reflow, and forbidden-field DOM assertions.

**Contract and architecture tests:**

- extend `backend/tests/api/test_openapi_contract.py` and `frontend/src/api/admin-client-contract.test.ts` with exact new operations, closed shapes, and forbidden provider fields;
- extend `backend/tests/integration/test_migrations.py` with head upgrade → downgrade → re-upgrade, constraint/index/FK checks, row preservation, and invalid-state rejection;
- update `test_provider_boundaries.py` without weakening host/URL/verb controls;
- keep `test_background_boundaries.py` green so HTTP never executes worker bodies;
- extend `frontend/e2e/admin-configuration.spec.ts` for initial import, fast-forward refresh, retained-baseline failure/manual retry, and rewrite confirmation at desktop and mobile sizes.

## Shared Patterns

### Authentication and authorization

**Source:** `backend/src/verboflex/api/v1/routes/admin_previews.py` lines 43-45  
**Apply to:** all import/capability/mapping/product routes

```python
AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.ADMIN))]
AdminSession = Annotated[Session, Depends(get_db_session, use_cache=False)]
```

Backend ownership checks remain authoritative. Browser role checks, mapping IDs, route parameters, cached capability results, and old success never authorize provider access or mutation.

### Error handling and sanitization

**Source:** `client.py` lines 47-52, 346-408; `admin_previews.py` lines 172-188  
**Apply to:** provider adapter, import service, worker, public schemas, UI

Use one safe provider exception message plus closed categories. Log only sanitized correlation/status metadata. Public responses and browser state exclude provider bodies, headers/scopes, source bytes, credentials, unsafe URLs, and stack traces. The row owns its execution error; no toast, page banner, contextual error button, or automatic navigation.

### Database authority and concurrency

**Source:** `preview_jobs.py` lines 626-705, 825-974, 1449-1505  
**Apply to:** start/refresh/retry, worker start/finish, rewrite confirmation

Use `with session.begin()`, product/mapping/import row locks, explicit currentness comparison, and conditional terminal writes. Preserve the last successful baseline on every failed refresh. Separate mappings are atomic across both sides.

### Background work

**Source:** `preview_tasks.py` lines 132-166; `celery_app.py` lines 12-54  
**Apply to:** import task, watchdog, configuration

Persist first, dispatch UUID only, execute outside HTTP, serialize JSON only, use late ack/worker-loss rejection, central time limits, and database status. No automatic provider retry.

### Generated client

**Source:** `frontend/package.json` lines 17-18 and imports in current admin pages  
**Apply to:** every frontend API call/type

Regenerate from canonical OpenAPI; never handwrite transport or duplicate DTOs. `api:check` is the drift gate.

### Accessible asynchronous UI

**Source:** `usePreviewPolling.ts`, `BitbucketConnectionPage.tsx`, `ProductMappingsPage.tsx`  
**Apply to:** import list, reconciliation dialog, capability profile, overview count

Use discriminated load states, stale-response guards, ref+state submit locks, geometry-matched skeletons, transition-only polite announcements, focus restoration, semantic table/stacked mobile articles, visible text status, and server-confirmed updates only.

## No Exact Semantic Analog

Every likely file has a role-level analog, but these Phase 3 behaviors are new and must come from the locked context/UI contract rather than copied Phase 2 semantics:

| Target Area | Why Existing Code Is Insufficient | Planning Rule |
|---|---|---|
| `client.py` / `urls.py`: ancestry and file delta | Phase 2 resolves branches and reads snapshots but has no descendant/rewrite classification or complete old/new localization delta. | Add bounded, host-locked, commit-exact reads; incomplete comparison is non-confirmable. |
| `import_jobs.py`: retry identity | Preview retry creates a new durable attempt row. | Keep one visible/logical import UUID; replace current status/error, increment retry count, and suppress late prior execution completion. |
| import baseline persistence | Preview results are historical/currentness evidence, not a retained usable baseline after failure. | Store active last-success separately from latest execution/proposal and never clear it on refresh failure. |
| OAuth capability profile | Phase 2 validates exact `repository` scope only. | Implement D-08's expanded provider capability and closed profile; legacy grants require reauthorization; raw scope never reaches browser. |

## Planner Guardrails

- Phase 3 reads source and establishes durable baselines; it does not parse canonical translations, persist searchable translation rows, write files, create branches/commits/PRs, or expose provider mutation controls.
- D-11 forbids automatic provider retry. HTTPX stays `retries=0`; “Retry import” is an administrator-triggered new execution of the same logical import.
- The latest failed refresh and last successful baseline coexist. `May be stale` is not equivalent to no baseline.
- Rewritten history is mapping-scoped and confirmation is atomic for direct or separate topology.
- The UI consumes only server-projected published mappings, readiness, states, counts, commits, and bounded deltas. It does not infer ancestry, capability, currentness, or stale counts.
- Preserve server order for mappings and delta rows; do not add an Imports route, global banner, timeline, attempt selector, automatic schedule, cancel, or import-all control.

## Metadata

**Analog search scope:** `backend/src`, `backend/tests`, `backend/alembic`, `frontend/src`, `frontend/e2e`  
**Files scanned:** 237  
**Principal analogs read:** Bitbucket client/URL/OAuth/discovery boundary; preview model/service/worker/API/schema; mapping/product projections; Bitbucket/Mappings/Overview frontend pages; preview polling; migrations and representative backend/frontend tests  
**Pattern extraction date:** 2026-09-02
