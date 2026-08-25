# Phase 1 staging smoke

This smoke is the command-driven deployment proof for the Phase 1 authentication slice. It creates an isolated staging Compose project, uses generated one-run credentials and secrets, and removes its containers, volumes, images, traces, and temporary files on both success and failure.

## Prerequisites

- Docker Desktop or another reachable Docker daemon with Compose v2.
- `uv`, Node.js, and the frontend dependencies already installed from the checked-in lockfiles.
- Local ports may be allocated dynamically; no project service needs to be running first.

The harness does not accept or print reusable credentials. Admin passwords and the JWT/database secrets are generated for the isolated run, passed through protected temporary files or non-echoed stdin, and discarded during cleanup.

## TLS termination boundary

The staging and production Compose overlays are application-origin deployments behind a separately managed TLS edge; they are not safe as a standalone Internet-facing stack. Both the backend and frontend publish plaintext container ports only on host loopback (`127.0.0.1`), so an edge process on the same host may reach them but a remote client cannot bypass TLS by connecting to those ports.

The deployment owner must provide the external edge and verify all of these controls before exposing the service:

- a publicly trusted certificate for the configured frontend and API origins;
- TLS 1.2 or TLS 1.3 only, with certificate and hostname validation intact;
- HTTP either unreachable or redirected to HTTPS;
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` on browser responses;
- forwarding only to the loopback ports rendered by the applicable Compose overlay.

The repository smoke verifies the loopback binding and HTTPS origin configuration. Certificate, redirect, and HSTS checks belong to the environment-specific edge smoke because no private key or certificate is stored in this repository.

## Commands

Run the fast sensitivity checks before the full deployment proof:

```bash
bash -n tools/real_smoke.sh tools/adversarial_auth.sh
tools/real_smoke.sh --preflight
tools/adversarial_auth.sh --self-test
```

Run the complete staging and hostile-authentication proof:

```bash
tools/real_smoke.sh
```

Run only the real production-build browser path when diagnosing responsive UI behavior:

```bash
tools/real_smoke.sh --browser-only
```

## Expected checkpoints

A successful full run proves, in order:

1. The staging configuration accepts a generated strong JWT secret and the Secure, HttpOnly `__Secure-verboflex_refresh` cookie contract while the preflight rejects placeholder secrets, insecure cookies, legacy unprefixed cookies, and deliberately wrong assertions.
2. PostgreSQL and Redis become healthy under an isolated Compose project; Alembic completes `upgrade -> downgrade -> upgrade`; the first administrator is bootstrapped through stdin without credential output.
3. The backend, worker, and production frontend become ready within bounded polling deadlines, and a real Celery task returns exactly `5`.
4. The API completes temporary login, forced password change, ordinary login, identity/status reads, refresh rotation, double logout, and stale-authority rejection with exact status/body/cookie checks.
5. The browser completes keyboard-only authentication and navigation at widths `1440`, `768`, and `375` pixels, survives reload through the refresh cookie, keeps auth data out of Web Storage, and logs out.
6. The hostile suite rejects wrong-purpose, tampered, expired, stale-version, and replayed authority; blocks hostile origins and brute-force overflow; keeps credential failures non-enumerating; and fails Redis-dependent auth operations closed while liveness/logout remain available.

Success ends with:

```text
adversarial auth: PASS
real staging smoke: PASS
```

## Failure interpretation

- `real-smoke error:` identifies the first staging/API/browser checkpoint that diverged.
- `adversarial-auth error:` identifies the first hostile-input or outage invariant that diverged.
- A readiness timeout prints the isolated Compose status; inspect that first rather than extending the deadline.
- A Playwright failure includes its screenshot, error context, and trace under the protected per-run temporary directory. The enclosing smoke cleanup removes them after the command exits, so copy a needed diagnostic before interrupting cleanup only in a local debugging session.
- A preflight negative control that unexpectedly passes means the harness has lost sensitivity and the full smoke must not be trusted.

Cleanup targets only the exact generated Compose project and image tags. After an interrupted diagnostic run, the normal trap still invokes `docker compose down --volumes --remove-orphans` for that project and removes only its two generated image tags.
