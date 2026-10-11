"""Verified regular-file metadata and byte authority precede every writer."""

import hashlib
from dataclasses import replace
from uuid import uuid4

import pytest

from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.writing.core import (
    SourceFileAuthority,
    WritebackReason,
    WritebackRejected,
)


def _inputs(content=b'{"hello":"Hello"}', *, attributes=()):
    from verboflex.integrations.bitbucket.client import BitbucketSourceMetadata

    authority = SourceFileAuthority(
        uuid4(),
        0,
        uuid4(),
        "direct",
        "main",
        "a" * 40,
        "i18n/en.json",
        len(content),
        hashlib.sha256(content).hexdigest(),
    )
    parser = CanonicalParserInput(
        "json",
        "direct",
        authority.path,
        content,
        "json:flat-per-locale:i18n/{locale}.json",
        1,
        "en",
    )
    metadata = BitbucketSourceMetadata(
        authority.path, authority.commit_hash, len(content), attributes
    )
    return authority, parser, metadata


def _build(*inputs):
    from verboflex.services.writeback_authority import build_source_file_snapshot

    return build_source_file_snapshot(*inputs)


def test_verified_snapshot_retains_exact_bytes_and_confirmed_layout():
    authority, parser, metadata = _inputs()
    result = _build(authority, parser, metadata)
    assert result.authority is authority
    assert result.parser_input is parser
    assert result.attributes == ()


@pytest.mark.parametrize(
    "attributes",
    [None, ("link",), ("subrepository",), ("executable",), ("unknown",), ("binary", "binary")],
)
def test_special_file_is_rejected(attributes):
    with pytest.raises(WritebackRejected) as error:
        _build(*_inputs(attributes=attributes))
    assert error.value.reason is WritebackReason.UNSUPPORTED_FILE_ATTRIBUTES


def test_utf16_binary_marker_with_supported_codec():
    content = '"hello" = "Ciao";'.encode("utf-16")
    authority, parser, metadata = _inputs(content, attributes=("binary",))
    authority = replace(authority, path="it.lproj/Localizable.strings")
    parser = replace(
        parser,
        format="ios_strings",
        path=authority.path,
        layout_identity="ios-strings:{locale}.lproj/Localizable.strings",
    )
    metadata = replace(metadata, path=authority.path)
    assert _build(authority, parser, metadata).parser_input.content == content


@pytest.mark.parametrize(
    "change", [{"path": "else.json"}, {"commit_hash": "b" * 40}, {"size_bytes": 0}]
)
def test_metadata_identity_mismatch(change):
    authority, parser, metadata = _inputs()
    with pytest.raises(WritebackRejected):
        _build(authority, parser, replace(metadata, **change))


def test_digest_mismatch():
    authority, parser, metadata = _inputs()
    with pytest.raises(WritebackRejected) as error:
        _build(replace(authority, sha256="b" * 64), parser, metadata)
    assert error.value.reason is WritebackReason.SOURCE_FILE_CHANGED


@pytest.mark.parametrize(
    "change",
    [
        {"repository_side": "translations"},
        {"layout_version": 2},
        {"layout_identity": "wrong"},
        {"format": "xliff"},
    ],
)
def test_unconfirmed_parser_authority_is_rejected(change):
    authority, parser, metadata = _inputs()
    with pytest.raises(WritebackRejected):
        _build(authority, replace(parser, **change), metadata)


def test_binary_marker_cannot_bypass_text_decoding():
    with pytest.raises(WritebackRejected):
        _build(*_inputs(b"\x00\xff\x01", attributes=("binary",)))
