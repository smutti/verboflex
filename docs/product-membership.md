# Product teams and temporary credentials

An administrator creates/configures products and appoints Product Owners in
**Administration → Products → Team**. A Product Owner uses the product's **Team**
page to add collaborators, change their operational role, or remove access.
The page separates **Product Owner** from **Collaborators**, showing each person's
name, email and role. Choose **Edit** beside a person to change their role or
remove them; removal still requires confirmation. Administrators use
**Assign Product Owner** to open the owner assignment form. The product navigation
highlights the current **Strings**, **Change sets** or **Team** page.

Each account has one role per product: Viewer, Translator, Reviewer or Product
Owner. Owners have Reviewer capabilities, including review/submission, and can
appoint Reviewers. Only a global administrator can appoint, demote or remove
Product Owners. Owners cannot modify administrator memberships, reset passwords,
reactivate disabled accounts, change existing identities or global roles,
configure repositories, or manage another product. An ownerless product remains
recoverable by a global administrator; Team shows when no active owner remains.

## Add a collaborator

Administrators can also create an account and assign several products at once in
**Administration → Users → Add user**. Under **Product access**, choose one role
per active product: Viewer, Translator, Product manager / reviewer, or Product
Owner. Products default to **No access**. Use **Load more products** to reach later
pages; up to 100 products can be assigned during account creation. Assignments
are optional and independent of the global account roles. Only Administrator
grants installation-wide access.

Account creation and all selected memberships are one transaction. If any selected
product has become inactive, deleted or unavailable, no account or memberships
are created; remove that assignment or reopen the form to refresh the list. The
temporary password is still shown only once after success.

The administrator create endpoint accepts an optional `product_assignments` array
of `{ "product_id": "<UUID>", "role": "translator" }` objects. Duplicate product
IDs, unsupported roles and unavailable products are rejected. Each successful
assignment records a `member.added` team event in the same transaction as the
`user.created` audit event.

Choose **Add collaborator**, enter their email, display name and operational role,
then select **Add to team**. For a new account, Team
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

## Edit product access from a user account

Administrators can use **Administration → Users → Edit → Product access** to
manage an existing account across products. Current roles are preselected;
choose **No access** to remove a membership. The list includes inactive products,
marked **(inactive)**, and excludes deleted products. An inactive product remains
inaccessible to ordinary members until it is reactivated. Disabled accounts can
lose memberships, but must be reactivated before receiving or changing roles.

**Save user** applies profile fields, global roles and explicit product changes
in one transaction. Up to 100 product changes can be saved together. Products on
unloaded pages and unchanged roles are preserved. Cancel discards the form's
changes. Membership edits take effect on the next authorized request and retain
the same team audit events and version checks as the product's Team page.

If another administrator or owner changes an affected membership, or a selected
product is deleted, the entire save is rejected. Inputs remain visible; reopen
the form to load current roles and review the changes again. No password is
generated or reset by editing product access.

`GET /api/v1/admin/users/{user_id}/products` returns a bounded product page with
the account's current `role` and membership `version` (both null without access).
The existing user PATCH endpoint accepts optional `product_assignments` changes:
`{ "product_id": "<UUID>", "role": "translator", "expected_version": "<UUID>" }`.
Use a null expected version only when granting absent access. A null role removes
access and requires the current membership version. Omitted or empty changes
leave all memberships untouched; duplicates, unsupported roles and stale versions
are rejected by the API.

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
