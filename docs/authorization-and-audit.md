# Authorization and audit

VerboFlex uses installation-wide administrators and explicit product memberships.
Viewer, Translator, Reviewer and Product Owner authority is scoped to a product.
Separate customer organizations and per-language permissions are not implemented.
See [product teams and temporary credentials](product-membership.md) for setup and migration.
The API decides
whether an operation is permitted; hiding a button is only a UI convenience.

## Roles

| Operation | Viewer | Translator | Product manager / reviewer | Admin |
| --- | --- | --- | --- | --- |
| Read active products, translations and discussions | Yes | Yes | Yes | Yes |
| Save translation drafts and add comments | No | Yes | Yes | Yes |
| Edit a comment | No | Own comments | Own comments | Own comments |
| Remove a comment | No | No | No | Yes |
| Approve/reject translations and set length constraints | No | No | Yes | Yes |
| Review and submit change sets | No | No | Yes | Yes |
| Configure products, repositories, imports and users | No | No | No | Yes |
| Read/mark notifications and manage MCP connections | Own only | Own only | Own only | Own only |

The table describes authority within an assigned product. Product Owners have
Reviewer capabilities and can provision collaborators with temporary credentials
and manage operational memberships; only administrators
appoint or remove owners. Resource state, optimistic versions, current imports,
source validity and provider capabilities can further restrict an allowed role.
Submission retries also verify the original actor and frozen authority;
reconciliation follows its separate recovery policy. Public GitHub imports remain
read-only at the provider: they allow local review, not GitHub pull requests.

The executable inventory is
[`mutation_policy.json`](../backend/tests/architecture/mutation_policy.json).
It lists the versioned HTTP write operations, their policy boundaries and the
owner of their durable evidence. A regression test fails when an operation is
added or removed without updating the inventory. Direct HTTP tests exercise
anonymous requests, revoked sessions and insufficient roles, checking that denied
requests do not write to PostgreSQL. Existing resource fixtures cover ownership,
proposal transitions, constraints, notifications and submission recovery.

Products may enable [approval commits](approval-branches.md). Configuration requires
an administrator. Reviewers and Product Owners can approve commits and request a PR;
viewers and translators cannot publish. The worker rechecks current authority before
each external effect. `branch.*` audit events identify configuration, approval intake,
explicit PR requests and retry authorization. Immutable snapshots preserve the original
approval when later drafts are saved.

## MCP and OAuth

The separately mounted protocol exposes `POST /oauth/register`,
`POST /oauth/token` and `POST /oauth/revoke`; their closed inventory is tested too.
`GET /oauth/authorize` creates a short-lived authorization request. These use
protocol validation, rate limits, redirect/resource binding, PKCE, client
authentication where applicable, token rotation and replay protection. They do
not accept a role or actor supplied by the caller as authority.

Consent and grant management require the signed-in owner. `/mcp` uses Streamable
HTTP and current OAuth authority. Write scope is necessary for write tools, but
does not grant an application role. Tool calls enter the existing API with an
in-process principal; an HTTP header cannot set that principal. The MCP tests
cover scope limits, changed roles, token-version changes, expiry, revocation,
code replay, concurrent exchanges and owner-scoped grant revocation. The stdio
connector uses the same API permissions.

## Session changes

The backend validates current account and session authority. User administration
also reloads the acting administrator under its mutation lock; cached ORM objects
cannot restore a disabled account or bypass a required password change.

Administrators can permanently delete an account after deactivating it. The
`DELETE /api/v1/admin/users/{user_id}` endpoint returns 204, rejects active accounts
with 409, and returns 404 for missing or already deleted identities. It rechecks
current administrator authority under the same lock as reactivation and product
membership changes. Deletion attempts are limited to ten per administrator per
minute; 429 includes `Retry-After`, and limiter outages fail closed with 503.

Deletion removes the account from administration, removes its roles and product
memberships, revokes browser sessions and MCP grants, and removes pending MCP
authorization requests. The user UUID remains as a disabled historical identity
for authored content: name and email are replaced and the password hash is rotated
to an unknown random value. Existing contributions and audit receipts remain.
The original email can be provisioned again with a new UUID and no inherited
permissions. A deleted identity cannot be reset, edited or reactivated. Migration
`0051_user_deletion` refuses downgrade after a deletion, so a schema rollback cannot
make removed accounts available again.

The frontend renews access authority before requests when the token is within
30 seconds of expiry, including after an idle tab resumes. Concurrent requests
share one refresh and browsers with Web Locks serialize cookie rotation across
tabs. Access tokens remain in memory; the original token identifies the UI's
session scope while the API client supplies the current bearer. Renewal verifies
the current identity and preserves open editors, drafts and navigation. A cookie
belonging to a different account cannot authorize the pending request.

An authenticated API request returning 401 triggers renewal before signing out.
After successful renewal, GET and HEAD requests can be retried once. Writes are
never automatically replayed: a write rejected with 401 receives a recoverable
503 from the client after renewal, so the user can explicitly retry. Network,
rate-limit and service failures during renewal also remain recoverable and do
not clear the session. Initial restoration failures show a retry screen instead
of the login form.

When the server rejects the refresh session or newly issued access authority,
the frontend removes the session, editors and dirty-navigation blockers. A
password-change requirement opens the restricted flow. An ordinary 403 does not
sign the user out. Delayed responses from an older login cannot change a newer
session or replay its pending requests. An idle tab learns about revocation on
its next request. Permissions continue to be enforced by the API on every call.

## Durable mutation evidence

Migration `0038_audit_events` adds `audit_entries` for the previously uncovered
configuration, account, constraint, preview/import request and Bitbucket lifecycle
mutations. Each row contains only:

- Event UUID and a closed action name.
- Actor UUID and kind (`user`, `operator` or `system`).
- Entity UUID and a database-generated timestamp.

HTTP routes derive the actor from the authenticated principal. Privileged local
operator calls explicitly pass no user identity; automatic credential renewal is
identified as a system action. The installation-wide Bitbucket configuration
uses a fixed entity UUID.

The event is committed in the mutation's transaction. If recording it fails, the
mutation rolls back. Newly created preview/import work is dispatched only after
commit. No-op requests do not invent changes; concurrent first-time workspace
selection produces one event. Entity/time and actor/time indexes support bounded
investigation without joining the translation search path.

Existing evidence remains authoritative for review activities, comment versions,
preview confirmations, import baseline confirmations, submission batches and
change-set events. Notifications and OAuth credentials retain their existing
owner-bound lifecycle records. They are not duplicated into a second content
history.

The new ledger has no arbitrary metadata field, text bodies, credentials, email
addresses or provider responses. Actor/entity IDs are snapshots without foreign
keys, so they cannot block physical removal of retired translation content.
The ledger is not exposed as an editable API, but it is not a tamper-proof external
log: a privileged database operator can alter it. There is no historical backfill,
audit browser or automatic ledger expiry in this release. New events start when
the matching migration and application are deployed.

## Verification boundary

The application workflow tests PostgreSQL transactions and migrations, API role
matrices, frontend guards and MCP authorization. Its Docker smoke configures five
products through HTTP, imports through Celery, posts comments, edits/approves
translations and creates PRs against a controlled TLS Bitbucket fixture. It also
checks revoked-session saves and failure recovery without duplicate remote effects.

This verifies the application on disposable infrastructure. Production deployment,
off-host restore/alerts, native assistive-technology acceptance and target-volume
load tests remain separate release checks. See [production readiness](production-readiness.md).
