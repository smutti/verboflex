# Quick task 260908-rfq: Semantic product status badges

## Goal

Make product lifecycle states immediately recognizable through consistent semantic badge colors.

## Assumptions

- The scope is the product catalogue and product overview, where lifecycle and configuration states are shown.
- Active and Published are positive states and use green.
- Inactive, Draft, and Not configured are non-terminal or attention states and use yellow.
- Failed, blocked, and error states keep the existing destructive red treatment.

## Tasks

1. Add failing component tests for reusable success and warning badge variants.
2. Add failing product UI assertions for Active/Inactive and Published/Draft states.
3. Implement the shared semantic variants and apply them to product catalogue and overview.
4. Run targeted frontend tests and the production build, then refresh the local frontend container.

## Verification

- Targeted Vitest suites pass.
- Frontend production build passes.
- Local frontend container is rebuilt and healthy.
