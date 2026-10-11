# Pre-release capacity experiment

The 2026-10-04 load experiment found a release blocker for large filtered
workspaces. The provisional target is **p95 ≤ 2 seconds with five concurrent
readers, with no unexpected HTTP errors or incorrect results**. Twenty readers
are a saturation probe. This is a local experiment, not a production capacity
certification; the production host has not been chosen.

## Reproduce

Run from the repository root with Docker running and backend dependencies installed:

```sh
backend/.venv/bin/python tools/load_translation_capacity.py \
  --output /tmp/verboflex-capacity-new \
  --values 100000 1000000 10000000 --products 10 \
  --seconds 45 --clients 1 5 20

backend/.venv/bin/python tools/benchmark_import_capacity.py \
  --output /tmp/verboflex-import-new --values 50000 --refresh

backend/.venv/bin/python tools/benchmark_import_capacity.py \
  --output /tmp/verboflex-import-limit-new --values 100000 --refresh
```

Each output directory must be new. These commands create their own PostgreSQL
and Redis containers, bind them to loopback ports, use generated databases, and
remove their resources on completion or SIGTERM. They do not load application
`.env` files, restore user data or call repository providers. Do not run the load
and import benchmarks concurrently. Reserve disk space and keep the machine
awake; ten million values also create ten million revisions and locators.
Exit code 2 means a measured target failed; exceptions return a nonzero status.
Results and diagnostic logs are written even when a target fails. Raw logs stay
local; the versioned evidence excludes tokens, database URLs and SQL parameters.

## Workload and limits

- PostgreSQL 18: 4 CPU quota, 6 GiB memory limit, 512 MiB shared buffers,
  16 MiB work memory, 15-second statement timeout. Redis: 0.5 CPU, 256 MiB.
  Shared Docker VM: 16 CPUs and about 15.6 GiB RAM. Other services were running.
- One host uvicorn process, normal SQLAlchemy pool (5 persistent + 10 overflow),
  TCP HTTP, real JWT verification, database sessions and role resolution.
  Synthetic identities are inserted directly; password login throughput is excluded.
- Ten products, twenty languages, one current scope per product, short scalar
  strings, one revision and one locator per value. Target strings are 20% empty;
  draft, approved and rejected values are present. Direct seeding keeps indexes,
  constraints and triggers enabled. It is not an import throughput measurement.
- Each read phase has one request in flight per user and a 550 ms think time.
  Phases last 45 seconds plus in-flight completion; the small-volume recheck uses
  30 seconds. This closed-loop model reduces offered traffic as responses slow;
  it is not an open-loop arrival-rate or sustained soak certification.
- The mix covers global/product browsing, a continuation page, exact-key and broad
  text search, approved/missing filters, options and product summary. Pages contain
  up to 50 keys × 20 language slots. Checks validate page bounds, product isolation,
  cursor disjointness, filter contents and summary counts.
- Save tests use independent keys, ten saves per user, then read the pending text
  back and verify the published value did not change. Replaying an old version
  must return 409. Ordinary-read rate limiting is tested separately through
  `/api/v1/users/me`; heavy translation routes currently do not use that limiter.
- Percentiles use nearest rank. Both all-response and successful-response
  percentiles are recorded; HTTP failures are never counted as fast successes.
  Per-case sample counts matter, especially for slow queries. The one-request
  pilot is diagnostic, not a statistically meaningful percentile estimate.
- Data is warm after seeding; OS caches are not cleared. Browser rendering, WAN,
  TLS, replicas, multiple API workers, large/plural text, rich historical data and
  mixed read/import contention are outside this run. Resource sampling itself
  adds some overhead. The 15-second SQL timeout belongs to this laboratory;
  removing it would not make the slow queries meet the interactive target.

## Defects fixed during the experiment

**Connection starvation.** At 100,010 values and twenty users, the baseline
completed only 11 of 23 requests successfully; ten returned 503 and two returned
500, with p95 around 30.6 seconds. All fifteen pool connections were held by
idle authentication transactions while routes requested another connection.
The authentication dependency now rolls back its read transaction after copying
the immutable principal. A real HTTP regression with a one-connection pool failed
before the change and passes after it.

**Blocking product summary.** The asynchronous summary route called synchronous
SQLAlchemy code on the event-loop thread. It now uses FastAPI's synchronous
handler dispatch. A regression asserts that the database service runs outside
the request event loop.

Both fixes are in `51b42cebf2d8fe999ce57159f1006cbd66a83a96`.
The targeted suite passed 103 tests. [Application CI 37228669720](https://github.com/smutti/verboflex/actions/runs/37228669720)
passed 3,207 backend, 1,003 frontend and 39 MCP tests, with no failures, errors
or skips, plus contracts, builds and the Docker/browser workflow.

## Query diagnosis and next gate

Plain browsing selects a bounded set of candidate keys before building the
multilingual rows. Filtered search instead materializes the rich value projection
for the selected current scopes, resolves source/history/provenance and only then
filters and limits the page. A selective key search therefore still performs
work proportional to the product's values. Pagination limits the response but
not the expensive intermediate work.

At one million total values (100,001 in the queried product), isolated
`EXPLAIN ANALYZE` measured 3,291 ms for selective search and 2,879 ms for the state
filter; product browsing took 52 ms. These are SQL measurements, separate from
end-to-end HTTP timings. The sanitized operator plans are retained with the evidence.

Before certifying the intended large volumes:

1. Select and rank matching key candidates before loading rich language rows,
   with indexed predicates for imported and pending text/state. Preserve source
   context, missing-language semantics and deterministic cursor order.
2. Repeat this workload after that change, including broad/global filters and
   concurrent imports. Do not raise the latency target to make it pass.
3. Check whether product summaries need incrementally maintained counts and
   whether expensive read routes need explicit concurrency/traffic controls.
4. Run longer arrival-rate and recovery tests on the chosen deployment, then
   validate the required production data distribution and resource budget.

The existing per-mapping import budget remains 100,000 canonical values. The
10-million read corpus deliberately exceeds that limit in each synthetic scope;
this experiment cannot justify raising parser or worker limits.
