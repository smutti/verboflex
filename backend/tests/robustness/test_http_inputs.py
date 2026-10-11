"""Malformed HTTP inputs must never crash, leak payloads or persist invalid data."""

import json
from uuid import uuid4

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select

from tests.api.test_mcp_oauth import CALLBACK, issue, support
from verboflex.models.mcp_oauth import McpClient
from verboflex.models.review import TranslationComment, TranslationProposal

FUZZ = settings(
    max_examples=120, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
INVALID_TEXT = ["\x00", "before\x00after", "\ud800", "\udfff", "x\ud800y"]


def body(value):
    # Preserve invalid Unicode escapes and non-finite numbers on the wire.
    return json.dumps(value, ensure_ascii=True).encode()


def assert_client_error(response):
    assert 400 <= response.status_code < 500, (response.status_code, response.text[:300])
    assert len(response.content) < 32768
    response.json()


@pytest.mark.parametrize("text", INVALID_TEXT)
def test_oauth_registration_rejects_unstorable_client_name(env, text):
    client, _, factory, _ = env
    with factory() as session:
        before = session.scalar(select(func.count()).select_from(McpClient))
    response = client.post(
        "/oauth/register",
        content=body({"client_name": text, "redirect_uris": [CALLBACK]}),
        headers={"Content-Type": "application/json"},
    )
    assert_client_error(response)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(McpClient)) == before


@pytest.mark.parametrize("path", ["/oauth/authorize", "/oauth/token", "/oauth/revoke"])
def test_oauth_client_lookup_rejects_nul(env, path):
    client = env[0]
    response = (
        client.get(path, params={"client_id": "\x00"})
        if path.endswith("authorize")
        else client.post(path, data={"client_id": "\x00", "grant_type": "refresh_token"})
    )
    assert_client_error(response)


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf"), "\ud800", {"\udfff": "x"}, "x" * 200000],
    ids=["nan", "inf", "negative-inf", "surrogate", "surrogate-key", "oversized"],
)
def test_validation_error_is_safe_and_bounded(env, value):
    client, owner, _, _ = env
    response = client.put(
        f"/api/v1/translations/{uuid4()}/proposal",
        content=body({"values": [], "expected_version": value}),
        headers={**owner, "Content-Type": "application/json"},
    )
    assert_client_error(response)


@pytest.mark.parametrize("text", INVALID_TEXT)
def test_edits_reject_unstorable_text_without_persistence(env, text):
    client, owner, factory, _ = env
    ids = support._seed_scalar_basis(factory, name="fuzz-" + uuid4().hex)
    response = client.put(
        f"/api/v1/translations/{ids['group']}/proposal",
        content=body(support._payload(ids, text)),
        headers={**owner, "Content-Type": "application/json"},
    )
    assert_client_error(response)
    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(TranslationProposal)
                .where(TranslationProposal.translation_key_id == ids["key"])
            )
            == 0
        )
    response = client.post(
        f"/api/v1/translations/{ids['group']}/comments",
        content=body({"body": text}),
        headers={**owner, "Content-Type": "application/json"},
    )
    assert_client_error(response)
    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(TranslationComment)
                .where(TranslationComment.translation_key_id == ids["key"])
            )
            == 0
        )


@pytest.mark.parametrize(
    "path", ["/api/v1/translations", "/api/v1/translations/keys", "/api/v1/users/mentions"]
)
def test_search_rejects_nul_without_database_error(env, path):
    response = env[0].get(path, params={"q": "\x00"}, headers=env[1])
    assert_client_error(response)


@FUZZ
@given(
    value=st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(),
        st.text(max_size=100),
        st.lists(st.integers(), max_size=5),
    )
)
def test_generated_invalid_versions_always_fail_cleanly(env, value):
    # Empty aggregate is always invalid, even when generated version happens to be valid.
    response = env[0].put(
        f"/api/v1/translations/{uuid4()}/proposal",
        content=body({"values": [], "expected_version": value}),
        headers={**env[1], "Content-Type": "application/json"},
    )
    assert_client_error(response)


@FUZZ
@given(value=st.text(max_size=120))
def test_generated_search_never_becomes_a_server_failure(env, value):
    response = env[0].get("/api/v1/translations/keys", params={"q": value}, headers=env[1])
    assert response.status_code in (200, 400, 422), (repr(value), response.status_code)
    if response.status_code == 200:
        assert len(response.json()["items"]) <= 50


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"[",
        b"null",
        b"[]",
        b"1",
        b"true",
        b'"text"',
        b'{"a":}',
        b"\xff",
        b"[" * 2000 + b"]" * 2000,
        b"[" * 20000 + b"]" * 20000,
    ],
    ids=[
        "empty",
        "unfinished",
        "null",
        "array",
        "number",
        "bool",
        "string",
        "syntax",
        "encoding",
        "nested",
        "deeply-nested",
    ],
)
def test_malformed_json_has_stable_client_error(env, raw):
    response = env[0].put(
        f"/api/v1/translations/{uuid4()}/proposal",
        content=raw,
        headers={**env[1], "Content-Type": "application/json"},
    )
    assert_client_error(response)


@pytest.fixture
def editable(env):
    return support._seed_scalar_basis(env[2], name="valid-" + uuid4().hex)


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    text=st.text(
        alphabet=st.characters(exclude_categories=("Cs",), exclude_characters="\x00"), max_size=160
    )
)
def test_valid_unicode_round_trips_without_normalizing_content(env, editable, text):
    client, owner, factory, _ = env
    with factory() as session:
        proposal = session.scalar(
            select(TranslationProposal).where(
                TranslationProposal.translation_key_id == editable["key"]
            )
        )
        version = proposal.version if proposal else 0
    payload = support._payload(editable, text, expected_version=version)
    path = f"/api/v1/translations/{editable['group']}"
    response = client.put(path + "/proposal", json=payload, headers=owner)
    assert response.status_code == 200, response.text
    expected = {item["translation_value_id"]: item["proposed_text"] for item in payload["values"]}
    saved = client.get(path, headers=owner)
    assert saved.status_code == 200, saved.text
    assert {
        item["translation_value_id"]: item["text"]
        for item in saved.json()["pending_change"]["values"]
    } == expected
    # A stale write cannot replace the successfully saved version.
    stale = client.put(path + "/proposal", json=payload, headers=owner)
    assert stale.status_code == 409


@pytest.mark.parametrize(
    "text",
    [
        "مرحبا 👨‍👩‍👧‍👦",
        "Tiếng Việt e\u0301",
        "日本語\n\ttext",
        "<script>alert(1)</script>",
        "' OR 1=1; --",
    ],
)
def test_comments_preserve_unicode_and_markup_as_plain_data(env, editable, text):
    client, owner, _, _ = env
    path = f"/api/v1/translations/{editable['group']}/comments"
    created = client.post(path, json={"body": text}, headers=owner)
    assert created.status_code == 201, created.text
    assert created.json()["body"] == text
    listed = client.get(path, headers=owner)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["body"] == text


@pytest.fixture
def mcp_token(env):
    return issue(env)[1]["access_token"]


@pytest.mark.parametrize(
    "arguments",
    [
        {"q": "\x00"},
        {"q": "\ud800"},
        {"page_size": float("nan")},
        {"page_size": -1},
        {"page_size": 1000000000},
        {"cursor": "tampered"},
        {"visible_languages": ["it"] * 21},
        {"q": "x" * 257},
    ],
)
def test_mcp_rejects_invalid_tool_arguments_without_server_failure(env, mcp_token, arguments):
    response = env[0].post(
        "/mcp",
        content=body(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "search_translation_keys", "arguments": arguments},
            }
        ),
        headers={
            "Authorization": f"Bearer {mcp_token}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": "2025-06-18",
        },
    )
    assert response.status_code in (200, 400, 422), response.text
    assert len(response.content) < 32768
    if response.status_code == 200:
        payload = response.json()
        assert "error" in payload or payload["result"]["isError"]
        assert payload.get("result", {}).get("structuredContent", {}).get("status_code", 422) < 500


@FUZZ
@given(token=st.text(alphabet="ABCabc019._-", min_size=1, max_size=4096))
def test_random_bearer_tokens_cannot_authenticate(env, token):
    response = env[0].get("/api/v1/users/me", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 401
    assert len(response.content) < 1024


@pytest.mark.parametrize(
    "name,value",
    [
        ("page_size", "999999999999999999999"),
        ("page_size", "-50"),
        ("cursor", "x" * 2049),
        ("product_id", "' OR 1=1; --"),
        ("language", "../../secret"),
        ("q", "x" * 257),
    ],
)
def test_search_limits_and_types_cannot_be_bypassed(env, name, value):
    assert_client_error(
        env[0].get("/api/v1/translations/keys", params={name: value}, headers=env[1])
    )


def test_validation_failure_does_not_reflect_raw_payload_or_grow_without_bound(env):
    marker = "sensitive-input-must-not-be-echoed"
    response = env[0].put(
        f"/api/v1/translations/{uuid4()}/proposal",
        content=body(
            {"values": [{"proposed_text": {"secret": marker}}] * 2000, "expected_version": 0}
        ),
        headers={**env[1], "Content-Type": "application/json"},
    )
    assert_client_error(response)
    assert marker not in response.text
    assert all(set(error) == {"loc", "type", "msg"} for error in response.json()["detail"])
