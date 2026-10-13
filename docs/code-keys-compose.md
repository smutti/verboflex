# Kotlin/Java keys and on-demand Compose screenshots

A separate mapping can use application code as its key catalog and another
repository as the localization dataset. In the mapping editor, choose **Separate
repositories**, enable **Extract keys from application code**, and configure the
resource roots, constant patterns or translation functions used by the application.
An omitted `code_source` retains the existing localization-file behavior.

The pilot uses 1953 as Keys (`app/src/main`) and Babel as Translations
(`babel/src/commonMain/moko-resources`), with English as the base language.
1953 uses references such as `Res.strings.title.resourceId`; Babel supplies the
actual base and localized text. The extractor also supports explicitly selected
Kotlin constants, Java static-final constants, single-string enum entries and
configured calls with statically resolvable keys. Synthetic tests cover those forms.

## Import and editing

Run layout preview and confirm the translations layout/base language, then publish
and import normally. Celery discovers the code and localization files at immutable
commits. Native parsing runs in a bounded child process. Syntax errors, dynamic
selected keys, ambiguous declarations, exceeded budgets or an empty discovered
catalog cannot replace the active dataset. Comments and ordinary string literals
are ignored; test/generated/build directories are excluded.

Exact keys are joined to independently parsed translations. No identifier is used
as invented base text. Existing duplicate quarantine and format-preserving writers
remain in force. Missing keys and translations outside the code catalog are reported
under **Code keys** in the product's translation workspace. Missing-language values
can be added through the existing authoring flow. The first translation for a code
key can be proposed with **Add text**, provided the identifier belongs to the active
catalog. Creation or renaming of code identifiers belongs in the application repo.

The catalog is stored on its import execution, covered by the canonical staging
digest, and becomes visible only with that execution's atomic activation. Code
locations are separate from localization file locators and can never be write targets.

## Registering a screen

Compose screenshots render a callable, zero-argument fixture preview in the Android
module. An `internal` or public top-level `@Preview @Composable` function in main
sources is suitable; a private function needs a small callable wrapper or visibility
change. Fixtures must supply their own screen state. Layoutlib cannot reproduce an
arbitrary live app state, device services, dependency injection or network responses.

Example mapping fragment (use the actual function name for the application):

```json
{
  "code_source": {
    "resource_roots": ["Res.strings"],
    "declaration_symbols": [],
    "localization_calls": [],
    "compose": {
      "runner_profile": "android-preview",
      "module": ":app",
      "variant": "Debug",
      "preview_functions": ["com.example.screens.HomePreview"],
      "width_dp": 1280,
      "height_dp": 800
    }
  }
}
```

Static call/reference evidence links keys to possible previews. Overloads are
conservatively combined; runtime branches, navigation state, dependency injection,
reflection and arbitrary property indirection are not resolved. A listed key may not
be visible in a particular fixture. Parameterized and custom multi-preview annotations
need a dedicated zero-argument registered preview for this first integration.

The Android module must apply `com.android.compose.screenshot` **0.0.1-alpha16** when
`-Pverboflex.capture=true`, enable `android.experimental.enableScreenshotTest`, add
`com.android.tools.screenshot:screenshot-validation-api:0.0.1-alpha16` and `ui-tooling`
to `screenshotTestImplementation`, and include the supplied
`verboflex.captureRoot/res` directory in the selected variant's resources. The pilot
implements this opt-in setup without changing AGP 8.12.3 or Kotlin 2.3.0. Commit the
capture setup and fixture before importing that application revision.

The runner creates one temporary screenshotTest wrapper, overlays imported Android
strings/plurals/arrays for the selected locale with base-language fallback, and runs
`update<Variant>ScreenshotTest --rerun --offline --build-cache`. It uses fresh
reference output and rejects zero/multiple images or an invalid PNG. It never checks
generated images into either repository. Arbitrary non-Android selectors are rejected.
The resource overlay preserves text and selectors; it does not recreate rich-text
spans from a translation file. Such screens need a reviewed application-specific
fixture adapter before their typography can be treated as representative.

## Isolated runner deployment

Apply Alembic migrations through `0046_screenshots` and deploy the regenerated API
client. The normal API process never invokes Git or Gradle. Run a dedicated Celery
worker consuming `screenshots` (for example `celery -A verboflex.worker.celery_app:app
worker -Q screenshots --concurrency=2`) and keep the existing scheduler running.

Configure `VERBOFLEX_SCREENSHOT_RUNNER_COMMAND` on the API and capture worker with a
JSON argument array pointing to the trusted host adapter, for example:

```json
["/opt/venv/bin/python", "/opt/verboflex/tools/compose_capture_container.py", "--profiles", "/etc/verboflex/capture-profiles.json"]
```

The adapter's operator-owned profile file maps a reviewed profile to exactly one
repository ID, credential-free local mirror with initialized pinned submodules, and
an Android runner image pinned by digest:

```json
{
  "android-preview": {
    "repository_id": "00000000-0000-4000-8000-000000000001",
    "mirror": "/srv/capture-mirrors/application",
    "image": "registry.example/android-capture@sha256:REPLACE_WITH_VERIFIED_DIGEST"
  }
}
```

Build the image using `docker/compose-runner.Dockerfile` on top of a reviewed base
containing the current backend runtime at `/opt/venv`, JDK 21, Git, Android SDK at
`/opt/android-sdk`, and prewarmed Gradle caches at `/opt/gradle-cache`. Warm private
dependencies during image preparation using build secrets. Never include credentials,
Gradle properties containing passwords, application service configuration or Git
authentication headers in the image/mirror. Base image preparation is specific to the
application's dependencies; there is no universal ready-made 1953 image in this repo.
For 1953, settings evaluation requires `artifactory_consumer_user` and
`artifactory_consumer_key` even offline. In its prepared base image, set the corresponding
`ORG_GRADLE_PROJECT_…` environment variables to the non-secret placeholder `offline`;
all artifacts must already be cached. Do not copy real credentials into the runner.

Code discovery allows at most 200 listing pages, 5,000 entries, 500 source files,
12 repository path segments, 1 MiB per file and 20 MiB total. The pinned Kotlin
grammar rejects some otherwise valid one-line class members without a semicolon;
put the closing brace on a new line or use an explicit semicolon. A grammar error
fails the refresh and retains the previous active dataset.

At runtime the adapter disables network, drops capabilities, uses an unprivileged UID,
read-only root/mirror, temporary writable checkout, and bounded CPU/memory/processes.
Build stdout/stderr are discarded and Docker logging is disabled, so untrusted
build output cannot fill either host log spool. All host mounts are read-only;
the PNG is returned over a stream capped at 8 MiB with a deadline. The image's
`--emit-png` protocol and host adapter must be deployed together. Generated files
stay in the container's bounded temporary filesystem. Public failures remain closed codes.
The application build receives no API, database or provider credentials. The capture
worker host needs Docker access; deploy that worker separately from the API/import
workers. Do not configure the bare `compose_capture.py` command as the production
worker adapter. Its explicit `--development-workspace` option is for trusted local
validation only and does not establish production container isolation.

`VERBOFLEX_SCREENSHOT_TIMEOUT_SECONDS` defaults to 900. Disconnected queues recover
through durable dispatch. Interrupted renders terminate as failed; a new user request
starts a new capture. Cancelled jobs cannot publish late results. A build already
running may continue until completion or its timeout.

## User flow and access

Open a translation's **Screenshots and code references**, choose a registered preview
and appearance, save pending edits, then select **Generate screenshot**. The request
freezes code and translation commits, import execution, locale, fixture configuration
and the selected saved proposal version. Other strings use their imported values.
Each new request renders again; retrying the same request ID returns the same job.
The latest personal capture is restored when reopening the panel.

Membership is enforced on context, catalog, acceptance, status and image delivery.
The worker checks the original membership generation before publishing. Source
activation changes and access revocation fence late results. There is a limit of two
active requests per user, four per product and twenty requests per user per hour.
Images and frozen translation bundles expire after seven days and are removed by the
watchdog. Images use authenticated, `private, no-store` responses, never public URLs.

Google's tooling is experimental. See the [official Compose screenshot setup](https://developer.android.com/studio/preview/compose-screenshot-testing)
and [preview limitations](https://developer.android.com/develop/ui/compose/tooling/previews).

## Local macOS runner

For a trusted developer checkout, `tools/compose_capture_macos.py` can use the
installed Mac SDK instead of preparing a Linux Android image. The normal screenshot
Celery task calls it through `tools/compose_capture_http.py`; Git/Gradle work stays
outside the API. Include `docker-compose.capture-macos.yml` when starting the stack.
It adds a single-concurrency worker for the `screenshots` queue.

The operator-owned profile pins `repository_id`, `commit`, `mirror`, `java_home`,
`android_home`, `gradle_home` and `work_root`. The mirror must contain that exact commit
and its initialized submodules. Prepare repository snapshots through Celery. Copy
only dependency caches and the matching Gradle wrapper distribution to a separate
Gradle home; never copy the developer's credential-bearing `gradle.properties` or
initialization scripts. Use offline placeholder properties where required.

A local profile may also specify a reviewed `patch` and its `patch_sha256`. This
allows testing capture instrumentation before publishing an Android branch. The
patch applies only to a fresh archived checkout; an unexpected source commit or
changed patch is rejected. Keep a receipt of the patch alongside the profile: the
imported commit identifies application code, while the profile identifies local
preview instrumentation. After importing a new app commit, prepare and verify its
profile again. Shared deployments should commit the fixture and use the container
runner described above.

Generate a random relay token and store it in a private operator directory. Configure:

```text
VERBOFLEX_CAPTURE_TOKEN_PATH=/absolute/private/directory/worker-token
VERBOFLEX_SCREENSHOT_RUNNER_COMMAND=["/opt/venv/bin/python","/opt/verboflex/compose_capture_http.py","--url","http://host.docker.internal:8766","--token-file","/run/secrets/capture-token"]
```

The token file mounted into Docker must be readable by the container user; keep its
parent directory private and mount only that file. Start the host service with
`backend/.venv/bin/python tools/compose_capture_macos.py --profiles /absolute/profiles.json
--token-file /absolute/token`. A user LaunchAgent can keep it running across local
stack restarts and relaunch it after login. It listens only on host loopback port 8766,
requires the relay token, bounds requests/images and accepts one build at a time.
The worker uses Docker Desktop's `host.docker.internal` bridge.

Gradle receives a minimal environment, runs offline and uses a macOS Seatbelt profile.
Read access is limited to the disposable checkout, SDK, JDK, system files and isolated
cache; writes are limited to the checkout and cache. Gradle requires local daemon
sockets, so loopback connections and listening sockets are permitted. Connections to
the relay and standard local application ports are explicitly denied. Database and
Redis ports remain unpublished. Build logs are discarded; timeouts stop the entire
build process group. This is a local development service for reviewed code, without
the container runner's CPU/memory/tmpfs limits or multi-tenant isolation guarantees.

Verify a real screenshot through the translation page after deployment. The host
must be awake, the LaunchAgent running and Docker Desktop available. Each request
uses a fresh checkout and preview wrapper; dependency/build caches do not reuse a
previous screenshot.

On Macs where Seatbelt rejects Java's IPv4-mapped IPv6 loopback sockets, every JVM
must use `-Djava.net.preferIPv4Stack=true`, including Gradle worker daemons. Gradle
can strip `JAVA_TOOL_OPTIONS` from worker environments. Use a dedicated copy of the
same JDK with a `bin/java` launcher that forwards that option to its renamed original
binary (`java-real`); point the local profile at that copy. Do not modify the system
JDK or broaden the sandbox's outbound network policy to work around this problem.
