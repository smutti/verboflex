"""Synthetic capture inputs, escaping, bounded parsing and renderer output."""

import base64
import subprocess
from xml.etree import ElementTree as ET

import pytest
from hypothesis import given
from hypothesis import strategies as st

from verboflex.localization.code_keys.capture import CaptureBundle, preview_source, resource_overlay
from verboflex.localization.code_keys.catalog import CodeSourceConfig
from verboflex.localization.code_keys.process import extract_catalog_isolated
from verboflex.worker.screenshot_tasks import validate_png


def bundle(values=None):
    return CaptureBundle.model_validate(
        {
            "version": 1,
            "code_repository_id": "synthetic-app",
            "code_commit": "a" * 40,
            "translations_repository_id": "synthetic-strings",
            "translations_commit": "b" * 40,
            "import_execution_id": "synthetic-import",
            "language": "it",
            "base_language": "en",
            "capture": {"runner_profile": "synthetic", "preview_functions": ["demo.HomePreview"]},
            "request": {"preview_function": "demo.HomePreview", "theme": "dark"},
            "values": values or [],
        }
    )


def value(text, language="it", key="title", kind="scalar", fields=None):
    return {
        "key": key,
        "language": language,
        "text": text,
        "selector": {"version": 1, "kind": kind, "fields": fields or {}},
    }


def test_overlay_selected_language_wins_and_missing_uses_base():
    data = bundle([value("Welcome", "en"), value("Benvenuto"), value("Help", "en", "help")])
    root = ET.fromstring(resource_overlay(data))
    assert {n.attrib["name"]: n.text for n in root} == {"title": '"Benvenuto"', "help": '"Help"'}
    source = preview_source(data, "a" * 32)
    assert "import demo.HomePreview as SelectedPreview" in source
    assert 'locale = "it"' in source and "NIGHT_YES" in source
    assert "dpi=160" in source and "capture-" + "a" * 32 in source


@given(st.text(alphabet="abcXYZ &<>\"'@?\\\n\tè🙂", max_size=128))
def test_resource_text_cannot_inject_xml(text):
    root = ET.fromstring(resource_overlay(bundle([value(text)])))
    assert len(root) == 1
    assert root[0].attrib == {"name": "title"}
    assert len(root[0]) == 0
    assert root[0].text.startswith('"') and root[0].text.endswith('"')


def test_plurals_and_arrays_preserve_structure():
    root = ET.fromstring(
        resource_overlay(
            bundle(
                [
                    value("One", kind="android_quantity", fields={"quantity": "one"}),
                    value("Many", kind="android_quantity", fields={"quantity": "other"}),
                    value("First", key="items", kind="android_array_item", fields={"index": 0}),
                    value("Second", key="items", kind="android_array_item", fields={"index": 1}),
                ]
            )
        )
    )
    assert root.find("plurals/item[@quantity='other']").text == '"Many"'
    assert [node.text for node in root.findall("string-array/item")] == ['"First"', '"Second"']


@pytest.mark.parametrize(
    "values",
    [
        [value("text", kind="json_path")],
        [value("text", fields={"unexpected": "shape"})],
        [value("text", kind="android_quantity", fields={"quantity": "wrong"})],
        [value("text", kind="android_array_item", fields={"index": 2})],
        [value("text"), value("plural", kind="android_quantity", fields={"quantity": "other"})],
    ],
)
def test_unsupported_resource_shapes_fail_closed(values):
    with pytest.raises(ValueError):
        resource_overlay(bundle(values))


def test_registered_preview_and_nonce_are_required():
    data = bundle()
    with pytest.raises(ValueError):
        preview_source(data, "../escape")
    data.request.preview_function = "demo.Unregistered"
    with pytest.raises(ValueError):
        preview_source(data, "a" * 32)


def test_native_parser_isolated_success_and_bad_source():
    assert extract_catalog_isolated(
        {"Screen.kt": b"fun label() = Res.strings.title"}, CodeSourceConfig()
    ).keys == ("title",)
    with pytest.raises(ValueError, match="extraction failed"):
        extract_catalog_isolated({"Broken.kt": b"fun broken( {"}, CodeSourceConfig())


def test_native_crash_and_timeout_fail_without_partial_catalog(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kw: subprocess.CompletedProcess([], -11, b"{}")
    )
    with pytest.raises(ValueError):
        extract_catalog_isolated({}, CodeSourceConfig())

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("parser", 45)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(ValueError, match="timed out"):
        extract_catalog_isolated({}, CodeSourceConfig())


def test_png_output_boundaries():
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7n8AAAAASUVORK5CYII="
    )
    validate_png(png)
    for content in (b"not an image", png[:-8], png[:16] + b"\xff" * 8 + png[24:]):
        with pytest.raises(ValueError):
            validate_png(content)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("\\", '"\\\\"'),
        ('"', '"\\""'),
        ("'", '"\\\'"'),
        ("\n", '"\\n"'),
        ("\t", '"\\t"'),
        ("  @?  ", '"  @?  "'),
    ],
)
def test_android_escaping_preserves_resource_literal_text(text, expected):
    assert ET.fromstring(resource_overlay(bundle([value(text)])))[0].text == expected


def test_custom_dimensions_and_light_fixture_are_generated():
    data = bundle([value("Ignored", language="fr"), value("Title", language="en")])
    data.capture = data.capture.model_copy(update={"width_dp": 640, "height_dp": 480})
    data.request.theme = "light"
    source = preview_source(data, "b" * 32)
    assert "spec:width=640dp,height=480dp,dpi=160" in source
    assert "Configuration.UI_MODE_NIGHT_NO" in source
    assert '@Preview(name = "capture-' + "b" * 32 in source
    assert "@PreviewTest" in source and "@Composable" in source
    assert "fun Capture() { SelectedPreview() }" in source
    assert ET.fromstring(resource_overlay(data))[0].text == '"Title"'


@pytest.mark.parametrize("output", ["valid", "missing", "symlink", "invalid"])
def test_runner_process_gets_bounded_inputs_without_service_credentials(
    tmp_path, monkeypatch, output
):
    import sys

    from verboflex.core.config import Settings
    from verboflex.worker import screenshot_tasks

    script = tmp_path / "runner.py"
    script.write_text(
        """import argparse, base64, os
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument("--input"); p.add_argument("--output"); p.add_argument("--timeout")
a = p.parse_args()
assert "VERBOFLEX_TEST_SECRET" not in os.environ
assert Path(a.input).read_text() == '{"synthetic":true}'
assert a.timeout == "30"
out = Path(a.output)
"""
        + {
            "valid": 'out.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB'
            'CAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7n8AAAAASUVORK5CYII="))',
            "missing": "pass",
            "symlink": "out.symlink_to(a.input)",
            "invalid": 'out.write_bytes(b"old build log")',
        }[output]
    )
    monkeypatch.setenv("VERBOFLEX_TEST_SECRET", "synthetic-secret-not-forwarded")
    monkeypatch.setattr(
        screenshot_tasks,
        "get_settings",
        lambda: Settings(
            screenshot_runner_command=[sys.executable, str(script)],
            screenshot_timeout_seconds=30,
        ),
    )
    if output == "valid":
        validate_png(screenshot_tasks.render({"synthetic": True}))
    else:
        with pytest.raises(ValueError):
            screenshot_tasks.render({"synthetic": True})


def test_renderer_logs_cannot_fill_the_worker_disk(tmp_path, monkeypatch):
    import sys

    from verboflex.core.config import Settings
    from verboflex.worker import screenshot_tasks

    script = tmp_path / "noisy_runner.py"
    script.write_text("""import base64, os, stat, sys
from pathlib import Path
assert stat.S_ISCHR(os.fstat(1).st_mode) and stat.S_ISCHR(os.fstat(2).st_mode)
print("synthetic build output" * 10000)
Path(sys.argv[sys.argv.index("--output") + 1]).write_bytes(base64.b64decode(
"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7n8AAAAASUVORK5CYII="))
""")
    monkeypatch.setattr(
        screenshot_tasks,
        "get_settings",
        lambda: Settings(
            screenshot_runner_command=[sys.executable, str(script)],
            screenshot_timeout_seconds=30,
        ),
    )
    validate_png(screenshot_tasks.render({"synthetic": True}))
