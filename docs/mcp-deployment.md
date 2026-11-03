# Enable remote MCP with OAuth

HTTP MCP is disabled when `VERBOFLEX_MCP_PUBLIC_URL` is empty or absent. Publishing
the web application does not enable it automatically. In that state, `/mcp`
returns HTTP 404 and the OAuth discovery endpoints return HTTP 404 with
`{"error":"MCP is not configured"}`.

## Configure the existing deployment

Set this value in the private environment file used by the running deployment,
replacing the example hostname with the application's public HTTPS hostname:

```dotenv
VERBOFLEX_MCP_PUBLIC_URL=https://verboflex.example.org/mcp
```

Use the exact `/mcp` path on the same origin as the frontend. Keep the environment
file out of Git. The base, staging and production Compose configurations pass this
setting to backend, worker and scheduler. It remains optional so installations can
keep HTTP MCP disabled.

The reverse proxy must route `/mcp`, `/oauth/*` and `/.well-known/*` to the backend,
preserving the public Host header. `/mcp/authorize` and `/mcp/connections` are
frontend pages. The supplied frontend Nginx configuration already separates these
routes. Claude's remote connector must be able to reach them from Anthropic's
servers, even when using Claude Desktop.

Use the **same environment file, Compose project name and overlay files** as the
existing deployment. For example, only if it already uses `.env.production`,
project `verboflex` and these two Compose files:

```sh
production_compose() {
  docker compose --env-file .env.production -p verboflex \
    -f docker-compose.yml -f docker-compose.prod.yml "$@"
}

production_compose config --quiet
production_compose up -d --no-deps --force-recreate --wait backend worker scheduler
```

For the [demo recipe](demo-deployment.md), use its `demo_compose` function with the
same `config` and `up` arguments instead. Recreating the services applies the new
environment; `docker compose restart` does not. This configuration-only change
uses the existing images and does not require rebuilding them.

## Verify before adding the connector

Replace the example origin below, then run these unauthenticated checks:

```sh
curl --fail --show-error --max-time 15 \
  https://verboflex.example.org/.well-known/oauth-authorization-server
curl --fail --show-error --max-time 15 \
  https://verboflex.example.org/.well-known/oauth-protected-resource/mcp
curl --include --show-error --max-time 15 https://verboflex.example.org/mcp
curl --include --show-error --max-time 15 \
  'https://verboflex.example.org/mcp/authorize?request=synthetic-routing-probe'
curl --include --show-error --max-time 15 https://verboflex.example.org/mcp/connections
```

Both discovery requests must return HTTP 200 with JSON. Their issuer,
authorization server and resource URLs must use the public origin; the resource
must end in `/mcp`. The unauthenticated MCP request must return HTTP 401 with a
`WWW-Authenticate` header pointing to the resource metadata. This challenge is
expected: access requires a user's OAuth authorization.

Both browser routes must return HTTP 200 with HTML. In a fresh browser session,
`/mcp/authorize?request=synthetic-routing-probe` must display the VerboFlex sign-in
page, preserving the request parameter. This synthetic request checks routing only;
start a new connection from Claude to obtain a valid authorization request.

If these pages return a JSON 404 while discovery works, check the **outer reverse
proxy** as well as the frontend proxy. Route only the exact `/mcp` resource to the
API; a prefix rule matching all `/mcp/*` paths incorrectly captures the consent and
connected-apps pages. Keep those pages on the frontend.

If discovery still returns `MCP is not configured`, the running backend has not
received the setting. Check the environment file, project and services being
recreated. An HTML response or a generic 404 after configuration instead calls for
checking the proxy routes and deployed application version.

## Connect Claude

Add the public `/mcp` URL as a custom web connector. If asked to choose an OAuth
client method, select automatic registration: VerboFlex supports dynamic client
registration and does not fetch client metadata documents. Each user signs in to
VerboFlex and approves their own connection; existing API permissions still apply.

On Claude Team, an Owner or Primary Owner must first add the connector to the
organization. Enterprise also supports a custom role with the relevant library
management permission. Members then connect individually. This organization
permission is separate from an HTTP 404; continuing manual setup cannot enable a
disabled MCP endpoint. See [Claude's custom connector guide](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

For scopes, revocation and local clients, see the [MCP guide](../mcp-server/README.md).
