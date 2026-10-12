# Product ownership and invitations

Implementation contract, 2026-10-11. The user authorized implementation after the
edge-case analysis. Tier 3 (authorization/concurrency). This file records that
contract; a separate review of this executable-spec file was not obtained.

## Behaviors

1. Only installation administrators appoint, demote or remove product owners.
   Owners manage viewer, translator and reviewer membership in their products.
   Owners have reviewer capabilities; they cannot administer global accounts.
2. Membership authorizes reads and writes only in that product, including search,
   dashboard, notifications, mentions, MCP and background submissions.
3. Existing users receive explicit memberships in existing products at migration,
   preserving their highest operational role. New products have no implicit team.
4. Invitations are delivered by a Celery SMTP task. Tokens are expiring, single-use,
   hashed for lookup and encrypted only for durable delivery. They never appear in
   ordinary API responses. Existing accounts authenticate to accept; new accounts
   choose their own password via the emailed token. Disabled accounts stay disabled.
5. Duplicate membership/invites never silently change roles. Resend rotates tokens.
   Revocation, product deactivation/deletion, and inviter authority changes prevent
   acceptance. Removing/readding someone never restores old invitations or jobs.
6. Team mutations serialize against current product, actor and membership state.
   Version conflicts cannot overwrite concurrent changes. Disabling an owner is
   allowed and the administrator can repair an ownerless product.
7. Removing membership preserves historical work and unrelated product access.
   Membership changes do not reset passwords or revoke all sessions. Workers
   revalidate the product authority generation before remote effects; effects
   already sent require existing reconciliation rather than automatic rollback.
8. Team and invitation mutations record actor, product, subject and before/after
   role in durable evidence, atomically with the mutation.

## Setup and validation

Use branch `codex/product-ownership`, existing Python/Node tools and dependencies,
and owned disposable PostgreSQL/Redis test containers. No production migration,
deployment, real invitation delivery, commit, or push is part of this change.
Add focused backend authorization/concurrency/invitation tests and frontend team
and acceptance tests. Regenerate OpenAPI/MCP contracts and write English operating
instructions. Validation/evidence is recorded in `docs/product-membership-evidence.md`.

Failure model: cross-product disclosure, privilege escalation, stale invitations,
global account takeover, concurrent lost updates, stale worker authority, migration
access loss, mail-delivery failure, and hidden UI/API contract drift. Test these
boundaries explicitly; use synthetic identities and a fake mail transport.

## 2026-10-11 revision: manually shared temporary credentials

The user's latest instruction replaces the unshipped email-invitation design above.
Admin or Product Owner adds a collaborator from the product team using email,
display name and an operational product role. A new account receives a random
32-character temporary password, returned once with `Cache-Control: no-store`.
The database stores only its Argon2 hash. The existing restricted first-login
session requires changing the password before product access. Global authority
starts at viewer; only the selected product receives the chosen role.

An existing active account is added without changing its name, password, global
roles or sessions. Disabled accounts cannot be reactivated by a Product Owner.
Duplicate adds return conflict without resetting credentials or changing roles;
concurrent adds serialize with global account administration. Re-adding a removed
member rotates membership authority so old work remains invalid. Role changes
remain versioned and only admins can appoint, demote or remove Product Owners.
An inactive or deleted product cannot provision accounts. A Product Owner cannot
provision into another product, change an administrator membership, reset existing
passwords, or inject global roles. If the response is lost, only the existing
global-admin password-reset workflow can issue replacement credentials.

The form displays credentials in memory until explicitly dismissed, with copy
support and a reminder to share them privately. A team refresh must not erase the
only visible copy. Ordinary team/user projections, audit events and logs contain
no password. SMTP settings, invitation tables, public token endpoints and delivery
workers from the superseded design are removed from this unshipped change.

Executable checks: new-account login/change/reuse lifecycle; existing account
preservation; duplicate and concurrent requests; current authority and stale forms;
input/role-injection rejection; transaction rollback; one-time UI display and
existing-account notice; migration rehearsal; complete API/SDK/MCP contracts.
No new dependencies or production changes. Create an English GitHub feature issue;
PR creation remains a later step. Separate spec approval: not obtained (autonomous
run under the user's implementation authorization).
