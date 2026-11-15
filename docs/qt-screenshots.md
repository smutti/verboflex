# Qt screenshots

Qt TS projects use the existing screenshot panel beside the translation. Select
a registered screen scenario and generate a capture of the imported text or the
current **saved** proposal. Unsaved edits block capture. Images retain their device
resolution; **Open screenshot full size** opens the original PNG without adding
the text-position overlay to its pixels.

## Import contract

The Celery import worker optionally reads `.verboflex/qt-screenshots.json` from the
same resolved commit as the TS catalogs. A missing manifest leaves ordinary Qt
imports unchanged. Malformed manifests and provider permission failures fail the
import; they are not silently treated as missing. The manifest is activated
atomically with the catalog and included in its immutable staging digest.

```json
{
  "version": 1,
  "runner_profile": "reviewed-device",
  "width": 800,
  "height": 480,
  "qt_version": "5.15.8",
  "platform": "offscreen",
  "sources": {
    "ui/screen.ui": "<SHA-256 of the original file>"
  },
  "scenarios": [
    {
      "id": "home",
      "label": "Home screen",
      "context": "HomeScreen",
      "source": "Welcome",
      "disambiguation": ""
    }
  ]
}
```

List the complete rendering source closure: original forms, widget implementations,
styles, fonts, resources and any configuration affecting layout. The manifest is
data only; it cannot select a shell command. The deployment operator reviews the
closure and prepares the profile's image. Initial support covers scalar,
source-based messages, selected by **context + source + disambiguation**. ID-based,
plural and length-variant messages require a future explicit runtime contract.
Unregistered strings show the existing unavailable state. Empty translations use
Qt's source fallback. Only the selected value's saved proposal is overlaid.

## Runner

Set `VERBOFLEX_QT_SCREENSHOT_RUNNER_COMMAND` to a trusted adapter accepting
`--input`, `--output`, `--timeout`. `tools/qt_capture_container.py --profiles PATH`
is the Docker adapter, suitable for a dedicated capture worker with an isolated
Docker daemon or an authenticated operator relay. Never mount the Docker socket
into the API. Repository archives are created only inside the Celery capture path.

Profiles map the manifest's `runner_profile` to a repository UUID, a local bare
`mirror`, immutable `image` digest, `source_digest` and `manifest_digest`.
The source digest is SHA-256 of `json.dumps(manifest.sources, sort_keys=True).encode()`;
the manifest digest is SHA-256 of its exact repository bytes. Update the mirror
through the normal authorized repository worker before capturing a newer commit.

The image contains the original compiled application widgets and assets,
`/opt/qt-manifest.json`, `/opt/qt-capture-render`, and the entry point
`tools/qt_capture_runtime.py`. The executable accepts `--input` and `--output`
and writes a PNG plus a JSON sidecar with `qt_version`, `platform`, `width`,
`height`, `text`, and the standard normalized `location` object. It must select
deterministic application state, load original fonts, disable animations and
wait for layout and painting. Do not reconstruct product screens in HTML.

The adapter archives the **requested commit** and the image verifies every listed
source hash before rendering. Stale manifests therefore cannot authorize changed
forms, fonts or widgets. Archive contents are never executed or extracted. The
container is unprivileged, read-only, networkless, resource limited and receives
no provider credentials. The worker validates the receipt against the selected
text, language, scenario, source hashes, runtime and actual PNG dimensions.
Existing quotas, cancellation, expiry, authenticated images and access rechecks
apply unchanged.

## Pixel comparison

Repeatable offscreen rendering is not proof of device parity. Validate against a
lossless reference from the target firmware, using the same Qt build, font files,
DPI, pixel format and application state. Video/hardware surfaces require their
own deterministic reference; a widget capture does not exercise them.

An operator profile may contain `references`, mapping
`source_digest:scenario_id:language:sha256(rendered_text_utf8)` to the SHA-256 of a
validated reference PNG. Exact PNG equality is deliberately strict, including
encoding. Normalize device references through the reviewed capture process before
registering them. A mismatch rejects the capture. Only a matching operator-owned
reference enables **Matches the device reference**. Otherwise the panel says
**Device comparison pending**. Repository manifests cannot self-certify parity.

## Checks

Use synthetic catalogs and sources for public tests:

```sh
backend/.venv/bin/pytest backend/tests/unit/localization/test_qt_capture.py
backend/.venv/bin/pytest backend/tests/integration/test_qt_screenshots.py
npm --prefix frontend test -- --run src/features/translations/TranslationScreenshots.test.tsx
```

Integration tests require the disposable PostgreSQL setup in
[application checks](application-ci.md). They exercise context/disambiguation,
saved-proposal versions, fixed dimensions and revoked access. Runner tests reject
altered source archives and mismatched receipts. Product captures and device
references remain in the private deployment evidence, outside this repository.
