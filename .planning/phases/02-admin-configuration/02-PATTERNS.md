# Phase 2: Admin Configuration - Pattern Map

**Mapped:** 2026-08-26  
**Executable topology:** 20 sequential plans (`02-01` through `02-20`)  
**Planned file families:** 20  
**Analogs found:** 16 / 20

This map treats the Phase 2 work as RED→GREEN vertical slices. A planner should create the focused test named in `02-VALIDATION.md`, record its RED result, add only the model/service/route or component behavior needed for GREEN, then continue to the next slice. Published configuration is immutable; existing transactional code is an analog for locks and rollback only, not permission to model the active revision as mutable.

## Executable Plan Topology

| Plan | Slice | Owned path families |
|------|-------|---------------------|
| `02-01` | Users and additive roles | `services/admin_users.py`, flat `routes/admin_users.py`, user API/unit/concurrency tests |
| `02-02` | Product identity and revisions | `models/product.py`, `0002_product_revisions.py`, `services/products.py`, flat `routes/admin_products.py` |
| `02-03` | Global repository registry | `models/repository.py`, `0003_repositories.py`, `services/repositories.py`, flat `routes/admin_repositories.py` |
| `02-04` | OAuth foundation | `models/bitbucket_connection.py`, `0004_bitbucket_connection.py`, `services/bitbucket_oauth.py`, `security/secret_box.py` |
| `02-05` | OAuth lifecycle and API | `services/bitbucket_oauth.py`, flat `routes/admin_bitbucket.py`, OAuth/OpenAPI tests |
| `02-06` | Safe provider HTTP adapter | `integrations/bitbucket/urls.py`, `integrations/bitbucket/client.py`, provider-boundary tests |
| `02-07` | Branch/source discovery | `services/repository_discovery.py`, flat `routes/admin_discovery.py`, discovery integration/API tests |
| `02-08` | Direct mapping persistence/API | `models/product_mapping.py`, `0005_product_mappings.py`, `services/mappings.py`, flat `routes/admin_mappings.py` |
| `02-09` | Separate topology and grouping | `services/mappings.py`, `services/pr_grouping.py`, mapping/grouping tests |
| `02-10` | Product publication lifecycle | `services/publication.py`, `services/products.py`, product publication/API tests |
| `02-11` | Durable preview jobs | `models/preview_job.py`, `0006_preview_jobs.py`, `services/preview_jobs.py`, `worker/preview_tasks.py` |
| `02-12` | Android detector tracer | `localization/preview/{core,android_xml}.py`, Android fixtures/tests, preview-job integration |
| `02-13` | Qt/JSON/iOS detectors | `localization/preview/{registry,qt_ts,json,ios_strings}.py` and detector tests |
| `02-14` | Confirmation and publication bridge | `0007_preview_confirmations.py`, `services/{preview_jobs,publication}.py`, confirmation/publication tests |
| `02-15` | Generated admin client | `frontend/openapi.json`, `frontend/src/api/client/**`, generated-client contract test |
| `02-16` | Guarded admin shell | `frontend/src/router.tsx`, `components/layout/AppShell.tsx`, `features/admin/products/ProductDetailLayout.tsx`, route/shell tests |
| `02-17` | User administration UI | official owned shadcn primitives and `features/admin/users/**` |
| `02-18` | Product/repository/mapping UI | `ProductsPage.tsx`, `ProductOverviewPage.tsx`, `ProductWizardPage.tsx`, repository/mapping pages |
| `02-19` | OAuth/preview UI and E2E | `features/admin/{bitbucket,previews}/**`, `e2e/admin-configuration.spec.ts` |
| `02-20` | Quality and deployment gate | `tools/phase2_{smoke,gauntlet}.sh`, migration/scope tests, review/evidence records |

## File Classification

| New/Modified File or Family | Role | Data Flow | Closest Analog | Match Quality |
|-----------------------------|------|-----------|----------------|---------------|
| `backend/pyproject.toml`, `backend/src/verboflex/core/config.py` | config | request-response | `backend/src/verboflex/core/config.py` | exact |
| `backend/src/verboflex/models/{product,repository,product_mapping,bitbucket_connection,preview_job}.py`, `models/__init__.py` | model | CRUD + event-driven | `backend/src/verboflex/models/user.py`, `auth_session.py` | role-match; revisions live in `product.py` |
| `backend/alembic/versions/{0002_product_revisions,0003_repositories,0004_bitbucket_connection,0005_product_mappings,0006_preview_jobs,0007_preview_confirmations}.py` | migration | batch | `backend/alembic/versions/0001_auth_foundation.py` | exact migration style; split by executable slice |
| `backend/src/verboflex/services/admin_users.py` | service | CRUD | `backend/src/verboflex/cli.py` | exact authority/transaction match |
| `backend/src/verboflex/services/{products,repositories,mappings,publication,pr_grouping,repository_discovery}.py` | service + utility | CRUD + transform + provider reads | `backend/src/verboflex/cli.py`, `services/system_status.py` | partial; revision/discovery seams are new |
| `backend/src/verboflex/services/bitbucket_oauth.py` | service | request-response | `backend/src/verboflex/auth/refresh_sessions.py` plus `core/config.py` | role-match; provider protocol is new |
| `backend/src/verboflex/integrations/bitbucket/{urls,client}.py` | provider | request-response + streaming file-I/O | none | new host-validation and generation-bound adapter seam |
| `backend/src/verboflex/localization/preview/{core,registry,android_xml,qt_ts,json,ios_strings}.py` | utility/parser | file-I/O + transform | none | new strict noncanonical detector seam |
| `backend/src/verboflex/services/preview_jobs.py` | service | event-driven | `backend/src/verboflex/services/system_status.py` | role-match |
| `backend/src/verboflex/worker/preview_tasks.py` | worker | event-driven + file-I/O | `backend/src/verboflex/worker/tasks.py`, `worker/celery_app.py` | exact process-boundary extension |
| `backend/src/verboflex/schemas/{admin_users,admin_products,admin_repositories,admin_bitbucket,admin_discovery,admin_mappings,previews}.py` | schema/model | request-response | `backend/src/verboflex/schemas/users.py` | exact closed-schema pattern |
| `backend/src/verboflex/api/v1/routes/{admin_users,admin_products,admin_repositories,admin_bitbucket,admin_discovery,admin_mappings,admin_previews}.py`, `api/v1/router.py` | route/controller | request-response | `backend/src/verboflex/api/v1/routes/users.py` | exact flat-route extension |
| `backend/tests/{unit,api,integration,worker,architecture}/...` and detector fixtures | test | CRUD + event-driven + file-I/O | `test_me.py`, `test_migrations.py`, `test_refresh_concurrency.py`, `test_smoke_task.py` | exact by test tier |
| `frontend/src/router.tsx`, `frontend/src/components/layout/AppShell.tsx` | route + component | event-driven | same files | exact extension point |
| `frontend/src/features/admin/{users,products,repositories,mappings,previews,bitbucket}/**` | component + hook | request-response + event-driven | `features/auth/session.tsx`, `LoginPage.tsx`, `ServiceStatus.tsx` | role-match |
| `frontend/src/components/ui/{alert-dialog,checkbox,dialog,radio-group,select,table,tabs,textarea}.tsx` | component | event-driven | existing `frontend/src/components/ui/*.tsx` | exact registry pattern |
| `frontend/openapi.json`, `frontend/src/api/client/**` | generated client | request-response | current generated client/export pipeline | exact; generated only |
| `frontend/src/features/admin/**/*.test.tsx`, `frontend/src/router.test.tsx`, `AppShell.test.tsx`, `frontend/e2e/admin-configuration.spec.ts` | test | event-driven + request-response | `router.test.tsx`, `AppShell.test.tsx`, `auth-shell.spec.ts` | exact by test tier |

## Pattern Assignments

### SQLAlchemy models and `models/__init__.py` (model, CRUD/event-driven)

**Analogs:** `backend/src/verboflex/models/user.py`, `role.py`, and `auth_session.py`

**Imports, UUID identity, durable defaults, and explicit constraints** (`models/user.py:5-14`, `21-50`):

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from verboflex.db.base import Base

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            r"email = lower(btrim(email, E' \t\n\r\f\v'))",
            name="email_normalized",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

Copy the typed `Mapped[...]` style, PostgreSQL UUIDs, database defaults, named checks, and explicit relationships. Product/repository identity constraints and candidate-version checks must exist in both declarative metadata and Alembic. Put revision-owned mappings behind `ProductRevision`; do not share mapping rows between active and candidate revisions.

**Many-to-many/set identity pattern** (`models/role.py:25-40`):

```python
user_roles_table = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", PostgreSQLUUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True),
)
```

Use a composite primary key or unique constraint for set-valued allowed targets and other identities. Do not rely on client deduplication.

**Complete metadata graph** (`models/__init__.py:1-7`):

```python
"""Import every mapped model so Alembic sees the complete metadata graph."""
from verboflex.models.auth_session import AuthSession
from verboflex.models.role import Role, user_roles_table
from verboflex.models.user import User

__all__ = ["AuthSession", "Role", "User", "user_roles_table"]
```

Every Phase 2 model must be imported here before migration/schema tests run.

---

### `backend/alembic/versions/0002_product_revisions.py` through `0007_preview_confirmations.py` (migrations, batch)

**Analog:** `backend/alembic/versions/0001_auth_foundation.py`

**Migration header and named schema objects** (`0001_auth_foundation.py:7-17`, `30-64`):

```python
from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001_auth_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
```

**Dependency-safe downgrade** (`0001_auth_foundation.py:143-150`):

```python
def downgrade() -> None:
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_family_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")
```

Create leaf tables/constraints after their parents and drop them in reverse dependency order. The migration RED test must inspect exact columns, foreign-key deletion behavior, unique constraints, and upgrade→downgrade→upgrade before implementation.

---

### `services/admin_users.py` (service, CRUD authority)

**Analog:** extract and generalize `backend/src/verboflex/cli.py`; both CLI and HTTP should call the service after extraction.

**Transactional advisory lock plus row lock** (`cli.py:55-91`, `94-122`):

```python
with session.begin():
    session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": FIRST_ADMIN_LOCK_KEY},
    )
    user = session.execute(
        select(User).where(User.email == normalized_email).with_for_update()
    ).scalar_one_or_none()
    # validate every prospective invariant before mutating
```

**Credential replacement and session revocation in the same transaction** (`cli.py:109-122`):

```python
validate_password_for_user(
    password,
    normalized_email=normalized_email,
    current_password_hash=user.hashed_password,
)
user.hashed_password = hash_password(password)
user.must_change_password = True
user.token_version += 1
session.execute(
    update(AuthSession)
    .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
    .values(revoked_at=datetime.now(UTC))
)
session.flush()
```

Generate the temporary password before hashing, retain plaintext only in the successful service result, and never attach it to `User` or another durable row. Under one global admin-authority advisory lock, reload actor/target roles, validate nonempty roles, self-admin protection, and the prospective last-active-admin count before changing anything. Domain conflicts should be typed service exceptions; routes translate them to bounded `409` responses.

---

### Product configuration, publication, and grouping services (service/utility, CRUD/transform)

**Partial analog:** `backend/src/verboflex/cli.py` supplies the transaction/locking shape, but the active/candidate revision design is new and must follow `02-RESEARCH.md`, not an existing mutable model.

Use this existing rule: validation happens inside `with session.begin()` and before mutation (`cli.py:69-90`, `102-122`). For publication, lock the stable Product row with `with_for_update()`, return a no-op when the candidate is already active, compare candidate UUID/version, quantify every mapping and current confirmation, and only then swap `active_revision_id` and clear `candidate_revision_id`. Do not catch an exception and commit a partial graph.

Keep `normalize_product_name()` and PR grouping pure. They belong in focused unit/property tests before route or persistence work. The grouping key is exactly `(repository_id, target_branch)` and must be independent of language/file order.

---

### Pydantic schemas and admin routes (schema/controller, request-response)

**Analogs:** `backend/src/verboflex/schemas/users.py`, `api/v1/routes/users.py`, `auth/principal.py`, and `api/v1/router.py`

**Closed response projection** (`schemas/users.py:18-27`):

```python
class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    email: EmailStr
    display_name: str
    roles: list[RoleName]
    must_change_password: bool
```

Use separate request, normal response, and one-time-credential response models. Provider ciphertext, access/refresh tokens, client secret, raw callback/provider bodies, and the temporary password must be absent from every ordinary/detail/list/status schema.

**Reusable database-authoritative admin guard** (`auth/principal.py:128-142`):

```python
def require_roles(*allowed: RoleName) -> Callable[[Principal], Principal]:
    accepted = frozenset(allowed)
    if not accepted:
        raise ValueError("at least one allowed role is required")

    def dependency(principal: CurrentPrincipal) -> Principal:
        if accepted.isdisjoint(principal.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return principal

    return dependency
```

Bind `require_roles(RoleName.ADMIN)` at the admin router or every resource. Keep missing/invalid bearer behavior in `get_current_principal()` (`principal.py:104-122`), so admin routes preserve `401` versus `403` without new information leaks.

**Thin route with explicit OpenAPI contract** (`routes/users.py:19-36`, `45-51`):

```python
router = APIRouter(prefix="/users", tags=["users"])

@router.get(
    "/me",
    operation_id="read_current_user",
    response_model=CurrentUserResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
    },
)
async def read_current_user(principal: CurrentPrincipal, ...) -> CurrentUserResponse:
    return CurrentUserResponse(...)
```

Routes validate transport, call one service, set the exact `201/202/204/409/422` contract, and return a schema. They must not implement authority transactions, provider pagination, parsing, or publication predicates.

**Router composition** (`api/v1/router.py:3-11`):

```python
from fastapi import APIRouter
from verboflex.api.v1.routes import auth, health, system, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(system.router)
```

Keep the planned flat `api/v1/routes/admin_*.py` modules and include each once from `api/v1/router.py`. This intentionally follows the repository's existing flat `routes/users.py`, `routes/system.py`, and `routes/auth.py` family; a nested admin-router hierarchy would add an unplanned path seam.

---

### Bitbucket OAuth service and provider adapter (service/provider, request-response/streaming)

**Nearest internal analogs:** typed secret settings in `core/config.py` and bounded/sanitized external work in `services/system_status.py`; there is no existing OAuth/provider HTTP adapter.

**Secret-bearing immutable settings** (`core/config.py:18-42`, `86-102`):

```python
class Settings(BaseSettings):
    jwt_secret_key: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_prefix="VERBOFLEX_",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )
```

Add OAuth client ID/secret, exact callback, and Fernet key-ring settings here with `SecretStr` for secrets and fail-closed deployed validation. Do not persist deployment client secrets.

**Bounded, sanitized failure projection** (`services/system_status.py:54-64`):

```python
async def _bounded(self, probe: ServiceProbe) -> ServiceState:
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(probe),
            timeout=self._timeout_seconds,
        )
    except Exception:
        return "unavailable"
    if result not in _SERVICE_STATES:
        return "unavailable"
    return result
```

The new adapter must add the research-specific controls: exact `https://api.bitbucket.org` host, redirects disabled, validated opaque `next`, `Accept-Encoding: identity`, streaming byte counts, four-way HTTPX timeouts, exact `{repository}` scope, and no automatic retry. Persist encrypted token generations behind a singleton row lock; expose only bounded connection states.

No codebase analog exists for Redis single-use OAuth state, authenticated encrypted-token rotation, generation leases, or provider pagination. The new `services/bitbucket_oauth.py` and `integrations/bitbucket/{urls,client}.py` seams therefore follow the exact contracts in `02-RESEARCH.md` and `02-VALIDATION.md`; they do not infer provider behavior from Phase 1 refresh tokens.

---

### Localization preview adapters (utility/parser, file-I/O/transform)

**Analog:** none in the current codebase.

Create a protocol/result model plus registry before the four adapters. Each adapter is pure over bounded bytes and returns a candidate/diagnostic; it never receives a database session, Celery app, or provider write client. The registry partitions by exact format + repository side + language/path convention and never selects among competing candidates.

Implementation must copy contracts from `02-RESEARCH.md` rather than a source analog:

- strict decode with no replacement characters;
- duplicate-aware standard-library JSON;
- hardened XML with DTD/entity rejection;
- a state-machine iOS `.strings` lexer, not regex;
- deterministic Unicode code-point ordering;
- confidence exactly `1.0`, samples explicitly partial;
- unsupported, empty, mixed, malformed, ambiguous, or over-budget input is non-confirmable.

Fixtures under `backend/tests/unit/localization/preview/` are the executable analog. Build one format at a time: supported RED→GREEN, then malformed/unsupported/ambiguous/encoding RED→GREEN.

---

### Durable preview job service and Celery task (service/worker, event-driven/file-I/O)

**Analogs:** `worker/celery_app.py`, `worker/tasks.py`, `tests/worker/test_smoke_task.py`, and `tests/architecture/test_background_boundaries.py`

**JSON-only separate worker configuration** (`worker/celery_app.py:9-36`):

```python
application = Celery(
    "verboflex",
    broker=redis_url,
    backend=redis_url,
    include=["verboflex.worker.tasks"],
)
application.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    task_always_eager=False,
    task_track_started=True,
    enable_utc=True,
)
```

**Named deterministic task seam** (`worker/tasks.py:1-9`):

```python
from verboflex.worker.celery_app import app

@app.task(name="verboflex.add")
def add(left: int, right: int) -> int:
    return left + right
```

The preview task payload should be only the durable job UUID. The task loads the row, conditionally transitions queued→running→terminal, invokes the bounded provider/detector services, and writes output only when candidate revision/version, connection generation, and input digest are still current. Public state comes from PostgreSQL, never raw `AsyncResult`. Add soft 60 s/hard 75 s limits at task declaration or routing.

**HTTP/worker separation guard** (`tests/architecture/test_background_boundaries.py:22-41`):

```python
def test_fastapi_modules_never_import_or_call_worker_task_bodies() -> None:
    # AST scan rejects verboflex.worker imports and .delay/.apply_async/.run in API modules
    assert violations == []
```

Keep enqueue mechanics in a service/provider seam outside route modules so this architecture test remains true.

---

### Backend tests (test, CRUD/request-response/event-driven/file-I/O)

**Migration rehearsal** (`tests/integration/test_migrations.py:57-70`):

```python
command.upgrade(config, "head")
assert_auth_schema(engine)
command.downgrade(config, "base")
assert EXPECTED_TABLES.isdisjoint(inspect(engine).get_table_names())
command.upgrade(config, "head")
assert_auth_schema(engine)
```

Extend the disposable PostgreSQL fixture and assertions; do not replace the harness.

**Real two-session race** (`tests/integration/test_refresh_concurrency.py:29-50`):

```python
with ThreadPoolExecutor(max_workers=2) as executor:
    results = list(executor.map(lambda _index: _submit_refresh(), range(2)))

assert sorted(status_code for status_code, _body in results) == [200, 401]
```

Use two independent sessions/requests for last-admin, duplicate repository, candidate version, publication, and OAuth generation races. Assert both HTTP outcomes and final durable state.

**HTTP through ASGI with dependency overrides** (`tests/api/test_me.py:74-82`, `118-145`):

```python
app.dependency_overrides[get_db_session] = override_session
app.dependency_overrides[get_settings] = principal_settings

transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
    response = await client.get("/api/v1/users/me", headers=headers)

assert response.status_code == 200
assert response.json() == {...}
```

Admin API tests must prove `401`, `403`, and no mutation before successful behavior. Secret-negative tests inspect response schemas, logs, persistence snapshots, and later reads.

**Canonical OpenAPI and no handwritten contract types** (`tests/api/test_openapi_contract.py:76-88`, `118-147`, `195-208`):

```python
assert set(operations) == set(EXPECTED_OPERATIONS)
assert operation["operationId"] == operation_id
assert operation.get("security") == (
    [{"OAuth2PasswordBearer": []}] if requires_bearer else None
)

assert first == second
assert first == CHECKED_IN_SCHEMA.read_bytes()
assert _handwritten_api_type_declarations(handwritten_source) == set()
```

Add every Phase 2 operation and bounded error code to the exact surface. Regenerate OpenAPI/client only after a stable GREEN API slice.

---

### Frontend router and shell (route/component, event-driven)

**Analogs/extension points:** `frontend/src/router.tsx` and `components/layout/AppShell.tsx`

**Server-session containment first** (`router.tsx:17-62`):

```tsx
if (state.status === "checking_session") { /* bounded skeleton */ }
if (state.status === "signed_out") {
  return <Routes><Route path="/login" element={loginElement} />...</Routes>;
}
if (state.status === "password_change_required") { /* restricted routes only */ }
return <Routes><Route path="/" element={ordinaryElement} />...</Routes>;
```

Nest the new `/admin/*` routing inside the authenticated branch. Project admin visibility from `state.principal.roles`, but for a non-admin direct route render the approved access-denied surface and issue no admin collection request. Backend authorization remains authoritative.

**Responsive navigation reused in desktop and Sheet** (`AppShell.tsx:35-49`, `59-99`, `121-125`):

```tsx
function WorkspaceNavigation() {
  return <nav aria-label="Primary navigation" className="w-full">...</nav>;
}

<SheetContent side="left" className="w-72 max-w-[calc(100vw-32px)]">
  <WorkspaceNavigation />
</SheetContent>
...
<aside className="hidden ... lg:flex">
  <WorkspaceNavigation />
</aside>
```

Extend one shared navigation component with the `Administration` group and links. Do not fork desktop/mobile route definitions. The product subnavigation is URL-backed in Overview→Repositories→Mappings→Preview order.

---

### Frontend admin feature modules and polling hooks (component/hook, request-response/event-driven)

**Analogs:** `features/auth/session.tsx`, `LoginPage.tsx`, and `components/layout/ServiceStatus.tsx`

**Generated-client-only calls and stale response guard** (`session.tsx:106-149`, `174-213`):

```tsx
const operation = Symbol();
activeOperation.current = operation;
const identityResult = await readCurrentUser({ auth: authority.access_token });
if (activeOperation.current !== operation) {
  return;
}
if (identityResult.data === undefined) {
  setState((current) => transitionSession(current, { type: "sign_out" }));
  return;
}
```

Use generated functions with `auth: accessToken`. Guard stale branch lists, draft saves, preview polls, and conflict reloads by operation/job/revision identity so an older response cannot overwrite current local state.

**Owned shadcn form/error/pending pattern** (`LoginPage.tsx:21-42`, `44-94`):

```tsx
const form = useForm<LoginFormValues>({ defaultValues: { email: "", password: "" } });
...
try {
  await login(values);
} catch {
  setAuthError(true);
}
...
{authError ? <Alert variant="destructive"><AlertDescription>bounded copy</AlertDescription></Alert> : null}
<Button aria-busy={form.formState.isSubmitting} disabled={form.formState.isSubmitting} type="submit">
  Sign in to VerboFlex
</Button>
```

Keep backend/provider details out of copy; preserve field values on recoverable errors; focus the first invalid field or owning alert. The one-time-password dialog is a deliberate exception: hold the plaintext only in component state, block outside/Escape dismissal, and erase state before `I saved the password` closes it.

Preview polling uses a pure state/reducer hook suitable for Vitest/Stryker: every 2 s through 30 s, every 5 s through 90 s, then paused with manual refresh. It announces state transitions only and never invents percentage progress.

---

### Official shadcn components (component, event-driven)

**Analog:** existing project-owned components under `frontend/src/components/ui/`, imported through the `@/components/ui/...` alias as in `LoginPage.tsx:4-13`.

Install only `alert-dialog`, `checkbox`, `dialog`, `radio-group`, `select`, `table`, `tabs`, and `textarea` with the pinned project-local official shadcn CLI. Keep generated source owned in the repository. Do not add a third-party registry, data grid, new state library, or extra design tokens.

---

### Frontend tests and Playwright (test, event-driven/request-response)

**Router test harness** (`router.test.tsx:44-64`, `66-88`):

```tsx
function renderRoutes(state: SessionState, initialEntry = "/") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <SessionRoutes state={state} ... />
      <LocationMarker />
    </MemoryRouter>,
  );
}
```

Use this for admin/non-admin direct navigation and prove non-admin denial triggers no generated admin call.

**Accessible async interaction test** (`LoginPage.test.tsx:71-126`):

```tsx
loginMock.mockRejectedValueOnce(reason);
await user.click(screen.getByRole("button", { name: "Sign in to VerboFlex" }));
const alert = await screen.findByRole("alert");
expect(alert).not.toHaveTextContent(reason.message);
...
expect(submit).toBeDisabled();
expect(submit).toHaveAttribute("aria-busy", "true");
```

Apply the same pattern to mutation pending states, sanitized errors, one-time credential erasure, stale conflict preservation, and preview polling cutoff.

**Responsive shell verification** (`AppShell.test.tsx:425-467`): test mobile Sheet labels, keyboard open/close, focus containment, and trigger focus restoration. Extend it with role-gated admin links rather than creating a disconnected navigation test.

**Playwright visual/secret guard** (`e2e/auth-shell.spec.ts:20-27`, `29-69`, `169-207`):

```ts
const storage = await page.evaluate(() => ({
  local: Object.entries(localStorage),
  session: Object.entries(sessionStorage),
}));
expect(storage).toEqual({ local: [], session: [] });
...
expect(layout.bodyWidth).toBeLessThanOrEqual(layout.innerWidth);
expect(layout.documentWidth).toBeLessThanOrEqual(layout.innerWidth);
```

The Phase 2 E2E spec should preserve these checks at 320/768/1024/wide viewports and add wizard, OAuth status projection, preview candidates/partial label/confirmation, publish blockers, and secret absence from URL/storage/toasts.

## Shared Patterns

### Authentication and authorization

**Source:** `backend/src/verboflex/auth/principal.py:104-142`  
**Apply to:** every admin route and every provider/job operation initiated over HTTP.

- `get_current_principal()` owns bounded `401` and password-change `403` behavior.
- `require_roles(RoleName.ADMIN)` owns admin denial.
- Roles are loaded from PostgreSQL, never trusted from the browser or extra token claims.

### Transaction and error handling

**Sources:** `backend/src/verboflex/cli.py:69-148`, `db/session.py:21-28`

```python
def get_db_session() -> Generator[Session]:
    with SessionFactory() as session:
        try:
            yield session
        except BaseException:
            session.rollback()
            raise
```

Service methods own one complete transaction. Validate the prospective state after required advisory/row locks and before mutation. Routes map typed expected conflicts; unexpected failures propagate to centralized bounded handling and roll back.

### Deterministic output and pagination

Use stable server ordering and UUID tie-breakers. The client displays API order and does not merge/re-sort pages. Provider `next` remains opaque and validated; application cursors never expose provider URLs.

### Secret handling

- Temporary password: plaintext exists only in the successful create/reset/reactivate service result and one blocking UI dialog; `Cache-Control: no-store`.
- Bitbucket credentials: `SecretStr` deployment inputs, encrypted persistence, generation-locked rotation, no response/OpenAPI/browser/log field.
- Tests scan schemas, responses, logs, persistence, URLs, storage, and toasts.

### Generated API contracts

**Sources:** `backend/src/verboflex/scripts/export_openapi.py:9-18`, `tests/api/test_openapi_contract.py:118-147`, `frontend/src/api/config.ts:1-9`

```python
json.dump(app.openapi(), sys.stdout, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
```

```ts
export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  baseUrl: configuredBaseUrl || "/",
  credentials: "include",
});
```

FastAPI is canonical. Regenerate `frontend/openapi.json` and `frontend/src/api/client/**`; never hand-edit generated operations or duplicate wire types in feature code.

### Background boundary

HTTP routes create/reuse a durable preview job through a service and return `202`. The Celery payload is a job UUID; PostgreSQL is the queryable status/result authority. Preview code performs no provider write and creates no canonical translation/import/PR state.

### TDD slice order

Use the exact 20-plan sequence: user authority → product revision → repository registry → OAuth foundation/lifecycle → safe HTTP adapter → branch/source discovery → direct/separate mappings and grouping → publication core → durable preview job → Android → Qt/JSON/iOS → confirmation/publication → generated client → admin shell → user UI → product/repository/mapping UI → OAuth/preview E2E → quality gate. Do not create every schema/model/route in one pre-test batch.

## No Analog Found

| File Family | Role | Data Flow | Reason / Planning Source |
|-------------|------|-----------|--------------------------|
| `backend/src/verboflex/integrations/bitbucket/{urls,client}.py` plus `services/bitbucket_oauth.py` | provider/service | request-response + streaming | No external HTTP/OAuth provider exists. The split keeps OAuth authority separate from reusable safe REST transport; exact scope, host, timeout, pagination, byte, redirect, state, encryption, and generation contracts come from `02-RESEARCH.md`. |
| `backend/src/verboflex/localization/preview/**` | parser/utility | file-I/O + transform | No localization parser exists. Use the strict A-02/A-03 fixture matrix and fail-closed detector registry contract; do not reuse as a canonical parser/writer. |
| Immutable revision publication predicate | service/model | CRUD | No active/candidate configuration exists. Reuse only SQLAlchemy transaction/lock mechanics; implement the research pointer-swap predicate and prove active snapshots never change on failure. |

## Metadata

**Analog search scope:** `backend/src`, `backend/alembic`, `backend/tests`, `frontend/src`, `frontend/e2e` (excluded `graphify-out/`)  
**Existing files scanned:** 114 project source/test/migration files; 36 high-relevance files inspected  
**Strong analog groups:** 5 — authority/API, models/migrations, workers, frontend shell/session, verification/generated contracts  
**Pattern extraction date:** 2026-08-26
