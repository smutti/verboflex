# Product teams and temporary credentials

An administrator creates/configures products and appoints Product Owners in
**Administration → Products → Team**. A Product Owner uses the product's **Team**
page to add collaborators, change their operational role, or remove access.

Each account has one role per product: Viewer, Translator, Reviewer or Product
Owner. Owners have Reviewer capabilities, including review/submission, and can
appoint Reviewers. Only a global administrator can appoint, demote or remove
Product Owners. Owners cannot modify administrator memberships, reset passwords,
reactivate disabled accounts, change existing identities or global roles,
configure repositories, or manage another product. An ownerless product remains
recoverable by a global administrator; Team shows when no active owner remains.

## Add a collaborator

Enter their email, display name and operational role. For a new account, Team
shows a random temporary password once, with a copy button. Save it and share it
privately with the recipient, together with their email and the application URL.
A team refresh preserves the open password dialog; dismiss it with **I saved the
password**. The password is held only in browser memory and cannot be retrieved
from a later request. No email service or invitation link is required.

The recipient signs in with the temporary password and must change it before
accessing the application. The temporary credential grants only password-change
authority, not a normal session. After changing it, sign in with the new password.
The account has the global viewer baseline and only the selected product role.
The database stores an Argon2 hash, never the plaintext credential.

For an existing active account, Team adds product membership and returns no
password. The account keeps its name, password, global roles, other memberships
and sessions. Accounts already awaiting a password change still have to complete
that flow with their previously issued password. Disabled accounts require admin
intervention; a Product Owner cannot reactivate them.

Repeated or concurrent adds do not reset credentials or change an existing
member's role. They return a conflict. If the response is lost or the temporary
password was not saved, ask a global administrator to use the existing account
password-reset action. A Product Owner cannot reset an existing account, even
one they created. Role changes use the current membership version to reject
stale forms; refresh the team after a conflict.

## Access and revocation

Administrator remains installation-wide. Legacy global operational labels no
longer grant product access; `/users/me` includes explicit `product_roles` and
`managed_product_ids` for the interface. The API revalidates membership for each
operation. Users without memberships can sign in and see an empty workspace.
Global account administration does not implicitly replace product assignments.

Removing membership affects only that product, including reads, writes, mentions,
notifications and previously authorized background work. Re-adding a member
rotates their membership version so old work cannot become valid again. Product
Owners cannot remove or demote themselves or another owner. An inactive/deleted
product cannot provision accounts. Recreating a product does not inherit its
memberships. Global account disablement still revokes all sessions and access.

## Migration and operations

Migration `0044_product_membership` backfills existing users into each non-deleted
product, preserving the highest prior operational capability (admin/reviewer →
Reviewer, translator → Translator, otherwise Viewer). This is a one-time
compatibility migration. New products have no automatic members. No account is
automatically promoted to Product Owner. Administrators should review migrated
teams and nominate owners before adding collaborators.

Deploy the API and workers together with the migration. Old frozen submission
proofs lack the new membership generation and are rejected; recreate unaccepted
reviews after upgrading. Membership removal/regrant and role changes invalidate
queued review/writeback authority. Repository operations continue to use Celery.

Team events retain actor/product/subject IDs, action, role transition and time.
Account provisioning also emits a content-free `user.created` audit event.
Credentials are excluded from team projections and audit events; the creation
response uses `Cache-Control: no-store`. Product-maintenance deletion removes
memberships but retains team evidence. Downgrade refuses to discard recorded team
activity; restore a reviewed backup instead of silently broadening authority.

Feature tracking: [issue #7](https://github.com/smutti/verboflex/issues/7).
Verification: [evidence report](product-membership-evidence.md).
