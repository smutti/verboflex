---
quick_id: 260907-uir
description: Move signed-in identity into a user menu beside logout and add a profile page with password change
status: complete
---

# Quick task plan

## Task 1: Lock the account UX with failing tests

- Prove the Workspace no longer repeats the signed-in identity card.
- Prove the header user control exposes name, email, roles, and a Profile destination beside logout.
- Prove every authenticated role can open `/profile` while restricted and signed-out authorities remain isolated.
- Prove an authenticated session can submit the existing secure password-change operation and is signed out after success.

## Task 2: Implement the user menu and Profile page

- Add an accessible user dropdown to the application header without changing logout behavior.
- Add an authenticated Profile route containing identity, roles, and the shared password-change form.
- Reuse the generated password-change API and extend session authority from required-change sessions to ordinary authenticated sessions.
- Remove the redundant identity card from Workspace.

## Task 3: Verify, deploy locally, and document

- Run targeted and full frontend tests, lint, type checking, formatting, and production build.
- Rebuild only the local frontend container while preserving live configuration and verify health.
- Commit source and GSD artifacts without staging unrelated working-tree changes.
