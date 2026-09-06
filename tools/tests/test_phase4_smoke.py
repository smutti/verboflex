"""Smoke guards reject content-bearing broker payloads before worker consumption."""

import base64
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

SPEC = importlib.util.spec_from_file_location(
    "phase4_smoke", Path(__file__).parents[1] / "phase4_smoke.py"
)
assert SPEC is not None and SPEC.loader is not None
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


@pytest.mark.parametrize(
    "corruption",
    [None, "extra-arg", "keyword", "duplicate", "missing", "task", "invalid-uuid"],
)
def test_uuid_only_queue_contract(monkeypatch, corruption):
    import redis
    from verboflex.core import config

    identities = [str(uuid4()) for _ in range(4)]
    payloads = [[[identity], {}, {}] for identity in identities]
    if corruption == "extra-arg":
        payloads[0][0].append("source bytes must never enter broker")
    elif corruption == "keyword":
        payloads[0][1]["source"] = "forbidden"
    elif corruption == "duplicate":
        payloads[0][0] = payloads[1][0]
    elif corruption == "missing":
        payloads.pop()
    elif corruption == "invalid-uuid":
        payloads[0][0] = ["not-a-uuid"]
    messages = [
        json.dumps(
            {
                "headers": {
                    "task": "unexpected.task"
                    if corruption == "task"
                    else "verboflex.import.run"
                },
                "body": base64.b64encode(json.dumps(p).encode()).decode(),
            }
        )
        for p in payloads
    ]

    class Broker:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def scan_iter(self):
            return ["celery"]

        def type(self, _key):
            return b"list"

        def lrange(self, *_args):
            return messages

    monkeypatch.setattr(redis.Redis, "from_url", lambda _url: Broker())
    monkeypatch.setattr(
        config, "get_settings", lambda: SimpleNamespace(redis_url="unused")
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(identities)))
    if corruption:
        with pytest.raises((AssertionError, ValueError)):
            smoke.queue_check()
    else:
        smoke.queue_check()


@pytest.mark.parametrize("format_name", smoke.FORMATS)
def test_smoke_fixtures_use_real_registry(format_name):
    from verboflex.localization.importing.core import CanonicalParserInput
    from verboflex.localization.importing.registry import parse_canonical_mapping

    layouts = {
        "android_xml": "res",
        "qt_ts": "qt-ts:translations/app_{locale}.ts",
        "json": "json:flat-per-locale:locales/{locale}.json",
        "ios_strings": "ios-strings:{locale}.lproj/Localizable.strings",
    }
    result = parse_canonical_mapping(
        tuple(
            CanonicalParserInput(
                format=format_name,
                repository_side="direct",
                path=path,
                content=content,
                layout_identity=layouts[format_name],
                layout_version=1,
                base_language="en",
            )
            for path, content in smoke.fixture_files(format_name).items()
        )
    )
    assert not result.issues
    assert len(result.values) == 2
    assert {value.language for value in result.values} == {"en", "it"}


@pytest.mark.parametrize(
    "corruption", [None, "mutation", "extra-field", "unknown-category"]
)
def test_provider_audit_is_closed_and_read_only(tmp_path, corruption):
    rows = [
        {
            "category": "oauth-token-exchange",
            "method": "POST",
            "resource_family": "oauth-token",
            "status": 200,
        },
        {
            "category": "resource",
            "method": "GET",
            "resource_family": "branch-read",
            "status": 200,
        },
        {
            "category": "resource",
            "method": "GET",
            "resource_family": "source-read",
            "status": 200,
        },
    ]
    if corruption == "mutation":
        rows[-1]["method"] = "POST"
    elif corruption == "extra-field":
        rows[-1]["body"] = "forbidden"
    elif corruption == "unknown-category":
        rows[-1]["category"] = "unknown"
    path = tmp_path / "audit.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows))
    if corruption:
        with pytest.raises(AssertionError):
            smoke.audit(str(path))
    else:
        smoke.audit(str(path))
