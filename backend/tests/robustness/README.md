# Input robustness tests

Run from the repository root with the backend development dependencies installed.
The HTTP tests create, migrate and drop their own databases on a **dedicated test
PostgreSQL server**. They never use the application's database or external repositories.

```sh
docker run -d --rm --name verboflex-fuzz-tests \
  -e POSTGRES_HOST_AUTH_METHOD=trust -p 127.0.0.1:55432:5432 postgres:18
# Wait until pg_isready succeeds, then prepare the template for migrated test DBs.
docker exec verboflex-fuzz-tests pg_isready -U postgres
docker exec verboflex-fuzz-tests psql -U postgres -d template1 \
  -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm'

VERBOFLEX_TEST_POSTGRES_ADMIN_URL=postgresql://postgres@127.0.0.1:55432/postgres \
  backend/.venv/bin/pytest backend/tests/robustness -q \
  --hypothesis-seed=20261004 --hypothesis-show-statistics

docker stop verboflex-fuzz-tests
```

Remove `--hypothesis-seed` to explore new inputs. Hypothesis shrinks failures to
minimal counterexamples and reports a replay seed. Keep minimized failures as
explicit regression cases. Do not publish raw failure logs: the test harness may
include short-lived test access tokens in a failing example.

## Coverage

- Invalid Unicode, NUL, malformed UTF-8/JSON, deep JSON, non-finite numbers,
  oversized fields and large validation-error sets.
- OAuth client registration and lookup; MCP tool argument validation; rejected
  bearer tokens; fixed search page size, filter lengths/types and signed cursors.
- Invalid translation proposals/comments leave no proposal behind; legitimate
  Unicode saves and reads back unchanged; stale edits return a conflict.
- Comments preserve multilingual text and markup as data. This assertion checks
  storage/API behavior, not browser XSS rendering.
- Random bytes and mutations of valid Android XML, Qt TS, JSON, iOS strings and
  XLIFF files produce deterministic, bounded parse results or diagnostics.

The suite exercises 4,000 generated examples at its configured budgets, plus a
fixed regression corpus. Exact generated counts are printed by Hypothesis and
can vary with generation/exhaustion. These are functional robustness tests, not
throughput/load tests, a complete endpoint inventory or a penetration test.
Redis rate limiting is substituted in this suite; existing auth/OAuth regression
tests cover rate-limit decisions separately.

## Fixes motivated by the campaign

Previously, NUL characters in OAuth client names/IDs, translation searches,
proposals, comments and mention searches reached PostgreSQL and caused server
errors. These inputs now fail at the request boundary. Valid text is not stripped
or normalized.

FastAPI validation errors also reflected raw inputs. NaN/Infinity, lone Unicode
surrogates and deeply nested invalid values could crash error serialization;
oversized values produced oversized responses. The shared handler now returns
only bounded `type`, `loc` and `msg` fields for the first eight errors, omitting
raw `input` and `ctx`. The existing HTTP 422 and error-envelope shape are retained.
