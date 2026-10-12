# Deploy a VerboFlex demo

Use GitHub Pages for the product website and its browser-only sample. A live
portal also needs FastAPI, Celery, PostgreSQL and Redis on a server. The recipe
below prepares a small, invitation-only installation with synthetic data.

## Choose the experience

| Experience | Hosting | Visitors can do |
| --- | --- | --- |
| Website demo | GitHub Pages | Edit and approve a sample in page memory, without an account |
| Live portal | Separate Docker host + HTTPS hostname | Search, edit, comment and review real application data using individual accounts |
| Open editing sandbox | Additional application work | Each visitor needs isolated data, quotas, expiry and a reliable reset before anonymous access is offered |

The portal has internal accounts and explicit product teams (see
[product membership](product-membership.md)). It does not isolate
one visitor's changes from another visitor's changes. Never load customer or
company repositories into the public demonstration. Do not publish an admin password.

## Prepare a dedicated host

Install Docker Engine and the Compose plugin. As an initial sizing estimate for
the 400-value sample, start with 4 vCPU, 8 GB RAM and 40 GB disk; measure on the
chosen host before increasing users. This is not a capacity guarantee. Budget
for the server, domain and independent backup storage; no hosting is provisioned
by these files.

Point a hostname such as `demo.example.org` at the server. Open TCP ports 80 and
443 and restrict SSH to your administration network. Caddy obtains and renews
HTTPS certificates automatically when DNS and these ports are reachable. Keep
its data volume across restarts. [Caddy HTTPS requirements](https://caddyserver.com/docs/automatic-https).

From a fresh checkout on that host:

```sh
git clone https://github.com/smutti/verboflex.git
cd verboflex
python3 tools/init_demo_env.py --host demo.example.org

demo_compose() {
  docker compose --env-file .env.demo -p verboflex-demo \
    -f docker-compose.yml -f docker-compose.prod.yml \
    -f docker-compose.demo.yml "$@"
}

demo_compose config --quiet
demo_compose build
demo_compose up -d --wait postgres redis
demo_compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"'
demo_compose run --rm backend alembic upgrade head
demo_compose run --rm backend python -m verboflex.cli bootstrap-admin \
  --email operator@example.org --display-name 'Demo operator'
demo_compose up -d --wait
```

Replace the example hostname and administrator address. Bootstrap prompts for a
password; the first sign-in requires changing it. The generator refuses to
overwrite an existing environment file and writes random secrets with mode 0600.
Keep `.env.demo` private and backed up. The generated Bitbucket credentials are
unconnected dummy values required by Compose, not credentials for any repository.

Only Caddy is exposed publicly. The API and frontend host ports bind to loopback;
PostgreSQL and Redis have no host ports. The proxy sends `/api/*` directly to the
backend and serves the SPA at the same HTTPS origin. Use a dedicated host and the
`verboflex-demo` Compose project, so these volumes cannot be confused with an
existing installation.

## Load the sample and invite testers

1. Sign in over HTTPS and change the administrator password.
2. Follow the [sample setup guide](https://github.com/smutti/verboflex-demo/blob/main/docs/setup.md)
   to import the four synthetic Northstar products from the public demo repository.
3. Check product coverage, missing translations, native plural forms and suggestions.
4. Create individual translator and reviewer accounts. Share initial credentials
   privately, let users change them, and deactivate accounts when the trial ends.
5. Use the [presenter guide](https://github.com/smutti/verboflex-demo/blob/main/docs/presenter-guide.md)
   for an end-to-end walkthrough of local editing and review.

Public GitHub imports support local edits and review, but cannot open GitHub pull
requests. To demonstrate remote submission, connect a separate Bitbucket workspace
containing only synthetic files, with dedicated provider credentials; do not reuse
production credentials. Keep this step operator-led because it creates real branches
and pull requests.

HTTP MCP is disabled in the generated environment. Enable it explicitly by setting
`VERBOFLEX_MCP_PUBLIC_URL=https://demo.example.org/mcp`, recreating backend, worker
and scheduler, and following the [MCP guide](../mcp-server/README.md).

## Verify and operate

- Open the login page and check `/api/v1/health` over HTTPS, then inspect the authenticated service status page.
- Sign in as a tester; save a draft, reload, approve it as a reviewer and confirm
  that the repository has not changed. Check desktop and narrow-screen layouts.
- Use `demo_compose ps` and service logs for failures. Keep logs private.
- Add the [backup service](backup-restore.md) using the same environment and Compose
  project. The backup is not encrypted by the program; use private storage and an
  off-host copy, including the matching deployment keyring.
- Configure external availability and disk-space alerts. Test restoring a backup
  before announcing the live URL.

For a trial reset, use a verified clean demo backup and the documented restore into
a **new database**, followed by explicit cutover. Stop API, worker and scheduler
during cutover and select an empty Redis database. This also restores accounts and
sessions, so rotate tester access before reopening. The automatic database upkeep
job does not reset demo edits. No destructive reset timer is installed by this recipe.

For an unrestricted public sandbox, first add per-session datasets, account/session
expiry, write quotas and an idempotent reset. Until then, offer the account-free
website demo and invite people individually to the live portal.
