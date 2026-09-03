| Plan ID | Objective | Wave | Depends On | Requirements |
|---------|-----------|------|------------|--------------|
| 02-44 | RED-first TDD: close CR-14 by resolving every configured source branch through the exact branch-detail operation, requiring the returned exact name, and covering branch 101+ for candidate and immutable active-revalidation previews across direct and separate mappings while preserving the ASVS L1 High read-only boundary. | 37 | 02-38 | PROD-08 |
| 02-45 | RED-first TDD: close CR-15 with one shared React Router-native dirty-form blocker for product and mapping forms, retaining `beforeunload`; real-router link tests must prove the named Alert Dialog, `Keep editing` value/focus preservation, and navigation only after `Discard changes` under ASVS L1 High. | 38 | 02-44 | UI-03 |
| 02-46 | After both fixes, run a fresh source-bound closeout: focused frontend and real-router Playwright regressions, the full Phase 2 gate, a Critical-zero ASVS L1 High code/security review, and a fresh independent verifier, with no schema or API-scope expansion. | 39 | 02-45 | PROD-08, UI-03 |

All three downstream plans must set `gap_closure: true`; 02-44 and 02-45 are TDD plans. WR-08 remains explicitly `OPEN — WARNING` unless the retained default Compose flow is required by 02-46 closeout, in which case only WR-08 may be repaired and added to that gate. WR-03..WR-07 remain open and out of scope.

## OUTLINE COMPLETE
