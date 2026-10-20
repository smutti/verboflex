# On-demand Compose rendering on Linux

The web API records a frozen capture request and immediately dispatches its UUID
to the dedicated `screenshots` Celery queue after the database commit. If the send
fails, the request stays queued: the scheduler retries jobs waiting at least 30
seconds, checking every 10 seconds. Its worker calls the authenticated private
relay in `tools/compose_capture_service.py`; only the relay can access Docker.
The relay must run on an internal network without published ports and without
application, database, OAuth or Maven credentials.

For each request the relay starts an immutable runner image with no network,
read-only root filesystem, UID 65532, dropped capabilities, process/CPU/memory
limits and an ephemeral tmpfs. The source mirror, request and optional reviewed
fixture patch are mounted read-only. The PNG is returned through a bounded stream;
there is no writable host mount in the renderer. Only the trusted relay's exchange
directory is writable on the host. Mount it at the identical absolute path in the
relay, since bind paths are interpreted by the host Docker daemon.

## Prepare a profile

1. Use Celery-based repository preparation to obtain a self-contained mirror of
   the exact imported commit and its pinned submodules. Remove dependencies on
   external Git alternates. Never mount a developer home, SSH directory or working
   repository with provider credentials.
2. Build `docker/compose-toolchain.Dockerfile` on an amd64 Linux host. It installs
   JDK 21, Android API 36, build tools 35 and 36, platform tools and NDK 27.
   AGP can select build tools 35 even when the application targets API 36.
   The Android command-line tools
   archive is checksum-verified against the [official downloads](https://developer.android.com/studio#command-tools).
   Match the SDK/NDK versions to the reviewed application profile when preparing
   another application. This preparation requires the Android SDK licenses.
3. Prewarm dependencies in an operator-controlled preparation environment. Seed
   private artifacts from a trusted cache or download them in a separate, trusted
   dependency-only project. Do not expose Maven credentials to application builds.
   Execute the screenshot task once, then verify a fresh offline build. Include
   every SDK package selected by that build in the immutable toolchain; packages
   downloaded inside a disposable warm-up container are not retained in its image.
   Keep only the needed Gradle caches and wrapper distribution; omit daemon logs, init scripts,
   credentials and `gradle.properties` from the cache.
   Keep `caches/modules-2` intact: the runner uses it as Gradle's shared read-only
   dependency cache, including compatible artifact and metadata formats.
4. Build `docker/compose-prewarmed.Dockerfile` using that private context. Supply
   `TOOLCHAIN_IMAGE` and `BACKEND_IMAGE` by registry digest, or unique local tags
   bound to verified image IDs (BuildKit does not accept a bare image ID in `FROM`).
   The context contains `gradle-cache/` and `capture-gradle.properties`, the latter containing reviewed
   resource limits and harmless offline property placeholders only.
5. Build `docker/compose-runner.Dockerfile` with `CAPTURE_BASE_IMAGE` set to the
   reviewed prewarmed image reference. Register the resulting runner's full image
   ID (`sha256:` plus 64 hex digits) or registry digest in the private operator
   profile. Mutable tags fail.
   The runner image removes dependency-cache lock files and `gc.properties` during
   preparation. At runtime `GRADLE_RO_DEP_CACHE` points to
   `/opt/gradle-cache/caches` in that immutable, read-only image. Dependency artifacts
   and metadata are shared directly between containers rather than copied into each
   tmpfs. Gradle creates any writable dependency state in the private user home.
   Compiler/transform caches, task-output caches and the wrapper distribution are
   still copied to each request's private `GRADLE_USER_HOME`; they are not shared
   writable directories. See [Gradle's dependency-cache documentation](https://docs.gradle.org/current/userguide/dependency_caching.html#sec:shared-readonly-cache).
6. Build `docker/compose-relay.Dockerfile` with the current backend image, and
   configure its private profile/token/exchange mounts. Give the worker only a copy
   of the relay token and `tools/compose_capture_http.py`, never the Docker socket.

Example operator profile (synthetic identifiers):

```json
{
  "demo": {
    "repository_id": "synthetic-repository-id",
    "commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "mirror": "/private/capture/mirror",
    "image": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "patch": "/private/capture/fixture.patch",
    "patch_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
  }
}
```

The optional fixture patch enables the screenshot plugin and callable preview
fixture without modifying the source mirror. It is bound to both its SHA-256 and
the exact imported code commit, verified again inside the runner, and applied only
to the disposable checkout. Prefer committing the integration in the Android app;
remove the patch fields once that imported revision contains it. A new source
revision requires operator review and cache/profile preparation before rendering.

Use a random relay token of at least 32 characters. Keep its host directory mode
0700; the dedicated worker's read-only token file may need mode 0644 inside that
private directory because the worker runs as an unprivileged container user.

The host deployment must start the relay and dedicated queue worker, restart the
API with a configured `VERBOFLEX_SCREENSHOT_RUNNER_COMMAND`, and set a timeout large
enough for a fresh build. Requests remain lazy: opening a string loads references;
only **Generate screenshot** creates a build. Unregistered screens need callable
fixtures before they can render. A preview represents its fixture state, not every
navigation path of the running Android application.

Run the synthetic runner/relay tests in `backend/tests/unit/localization/` and
verify a real queued capture through the authenticated API after deployment.
Confirm the returned image dimensions, anonymous image denial and offline container
restrictions. Keep private source, images and deployment credentials out of Git.
When changing the cache layout, verify a fresh offline render before switching the
profile: dependency paths can affect application-specific build plugins or cache
entries. Compare identical frozen inputs, PNG digests and unchanged CPU/memory limits,
reporting queue time separately from generation. Refresh the image to update shared
dependencies; never mutate the seed while renders are using it.
