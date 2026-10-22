"""Synthetic repository image resolution, isolation and resource budgets."""

import base64
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

import pytest

from verboflex.integrations.bitbucket.client import BitbucketProviderReadError
from verboflex.localization.html_images import (
    MAX_IMAGE_BYTES,
    image_data_uri,
    is_image_data_uri,
    referenced_images,
    repository_image_path,
)
from verboflex.localization.html_preview import passive_html_preview
from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.services.html_preview_images import collect_html_preview_images

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWq0AAAAASUVORK5CYII="
)


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("/images/logo.png", "images/logo.png"),
        ("../../../images/logo.png", "images/logo.png"),
        ("../icons/My%20logo.PNG?v=2#icon", "drafts/mail/icons/My logo.PNG"),
        ("images/logo.png", "drafts/mail/nested/images/logo.png"),
        ("../../../../secret.png", None),
        ("/../secret.png", None),
        ("https://example.test/logo.png", None),
        ("//example.test/logo.png", None),
        ("\\\\example.test\\logo.png", None),
        ("/images/%5csecret.png", None),
        ("/images/%00secret.png", None),
        ("/images/%252e%252e/secret.png", None),
        ("/.git/config.png", None),
        ("data:image/png;base64,AAAA", None),
        ("cid:logo.png", None),
        ("file:///tmp/logo.png", None),
        ("/images/icon.svg", None),
        ("/images/icon.html", None),
    ],
)
def test_repository_paths(reference, expected):
    assert repository_image_path("drafts/mail/nested/Hello-EN.html", reference) == expected


def test_raster_validation_and_deduplication():
    uri = image_data_uri(PNG)
    assert uri and is_image_data_uri(uri)
    assert image_data_uri(b"<svg onload='attack()'></svg>") is None
    assert image_data_uri(b"\x89PNG\r\n\x1a\n" + b"x" * MAX_IMAGE_BYTES) is None
    assert not is_image_data_uri("https://example.test/logo.png")
    assert not is_image_data_uri("data:image/svg+xml;base64,PHN2Zz4=")
    assert not is_image_data_uri("data:image/png;base64,bad!")
    assert not is_image_data_uri("data:image/jpeg;base64," + uri.split(",")[1])
    assert referenced_images(
        "mail/Hello-EN.html",
        b"""<html><body background="../images/bg.png">
      <img src="/images/logo.png"><img src="../images/logo.png">
      <img src="https://example.test/tracker.png"><img src="/images/icon.svg"></body></html>""",
    ) == {
        "images/logo.png",
        "images/bg.png",
    }


def test_only_imported_images_can_be_embedded_and_source_is_preserved():
    uri = image_data_uri(PNG)
    raw = """<html><body background="../images/bg.png">
      <img src="/images/logo.png" onerror="attack()">
      <img src="/images/missing.png">
      <img src="https://example.test/tracker.png" srcset="bad.png 2x">
      <img src="data:image/png;base64,AAAA"><p><!--VERBOFLEX-SELECTED-TEXT--></p></body></html>"""
    result = passive_html_preview(
        raw,
        template_path="mail/Welcome-EN.html",
        images={
            "images/logo.png": uri,
            "images/bg.png": uri,
        },
    )
    assert result.document.count(uri) == 2
    assert result.missing_images == 1
    assert "onerror" not in result.document and "srcset" not in result.document
    assert "https://" not in result.document and "base64,AAAA" not in result.document
    assert 'src="/images/logo.png"' in raw
    assert "<!--VERBOFLEX-SELECTED-TEXT-->" in result.document


def test_preview_expansion_is_bounded(monkeypatch):
    import verboflex.localization.html_preview as module

    uri = image_data_uri(PNG)
    monkeypatch.setattr(module, "MAX_PREVIEW_IMAGE_CHARACTERS", len(uri))
    result = passive_html_preview(
        '<img src="/logo.png"><img src="/logo.png">', images={"logo.png": uri}
    )
    assert result.document.count(uri) == 1 and result.missing_images == 1


def test_worker_reads_once_per_asset_at_exact_commit_and_tolerates_missing():
    import asyncio

    factory = MagicMock()
    side = MagicMock(
        role="direct", provider="bitbucket", workspace="demo", repository_slug="emails"
    )
    identity = MagicMock(repository_sides=(side,))
    adapter = MagicMock()
    adapter.read_repository_source_file = AsyncMock(
        side_effect=[PNG, BitbucketProviderReadError(kind="not_found")]
    )
    parser = CanonicalParserInput(
        format="html",
        repository_side="direct",
        path="mail/Welcome-EN.html",
        content=(
            b'<html><body><img src="/logo.png"><img src="/missing.png"><p>Welcome</p></body></html>'
        ),
        layout_identity="html:mail",
        layout_version=1,
        base_language="en",
    )
    result = asyncio.run(
        collect_html_preview_images(
            factory,
            identity=identity,
            adapter=adapter,
            parser_inputs=(parser, replace(parser, path="mail/Welcome-IT.html")),
            commits={"direct": "b" * 40},
        )
    )
    assert result == {"direct": {"logo.png": image_data_uri(PNG)}}
    calls = adapter.read_repository_source_file.call_args_list
    assert len(calls) == 2
    assert {call.kwargs["commit_hash"] for call in calls} == {"b" * 40}
    assert all(call.kwargs["max_bytes"] == MAX_IMAGE_BYTES for call in calls)
    adapter.read_repository_source_file.side_effect = BitbucketProviderReadError(
        kind="permission_denied"
    )
    with pytest.raises(BitbucketProviderReadError):
        asyncio.run(
            collect_html_preview_images(
                factory,
                identity=identity,
                adapter=adapter,
                parser_inputs=(parser,),
                commits={"direct": "b" * 40},
            )
        )


def test_worker_budgets_count_unique_images_across_templates(monkeypatch):
    import asyncio

    import verboflex.services.html_preview_images as module

    monkeypatch.setattr(module, "MAX_IMAGE_PATHS", 3)
    adapter = MagicMock()
    adapter.read_repository_source_file = AsyncMock(return_value=PNG)
    identity = MagicMock(
        repository_sides=(
            MagicMock(
                role="direct", provider="bitbucket", workspace="demo", repository_slug="emails"
            ),
        )
    )
    first = CanonicalParserInput(
        format="html",
        repository_side="direct",
        path="mail/One-EN.html",
        content=b'<img src="/a.png">',
        layout_identity="html:mail",
        layout_version=1,
        base_language="en",
    )
    inputs = (
        first,
        replace(first, path="mail/Two-EN.html", content=b'<img src="/a.png"><img src="/b.png">'),
        replace(first, path="mail/Three-EN.html", content=b'<img src="/b.png"><img src="/c.png">'),
    )
    result = asyncio.run(
        collect_html_preview_images(
            MagicMock(),
            identity=identity,
            adapter=adapter,
            parser_inputs=inputs,
            commits={"direct": "a" * 40},
        )
    )
    assert set(result["direct"]) == {"a.png", "b.png", "c.png"}
    assert adapter.read_repository_source_file.call_count == 3
    adapter.read_repository_source_file.reset_mock()
    monkeypatch.setattr(module, "MAX_TOTAL_IMAGE_BYTES", 2 * len(PNG))
    result = asyncio.run(
        collect_html_preview_images(
            MagicMock(),
            identity=identity,
            adapter=adapter,
            parser_inputs=inputs,
            commits={"direct": "a" * 40},
        )
    )
    assert set(result["direct"]) == {"a.png", "b.png"}
    assert adapter.read_repository_source_file.call_count == 2


def test_editor_markers_survive_title_rcdata_without_allowing_source_markup():
    result = passive_html_preview(
        "<html><head><title><!--APP-TITLE-->&lt;script&gt;bad&lt;/script&gt;</title></head>"
        "<body><!--APP-BODY--><!--UNTRUSTED--><script><!--APP-BODY--></script></body></html>",
        markers=frozenset({"APP-TITLE", "APP-BODY"}),
    )
    assert result.document.count("<!--APP-TITLE-->") == 1
    assert result.document.count("<!--APP-BODY-->") == 1
    assert "UNTRUSTED" not in result.document
    assert "<script>" not in result.document
    assert "&lt;script&gt;bad&lt;/script&gt;" in result.document
