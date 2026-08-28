#!/usr/bin/env python3
"""Exercise the complete Phase 2 HTTP journey without printing secret material."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

COMMIT_HASH = "0123456789abcdef0123456789abcdef01234567"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


@dataclass(frozen=True)
class Response:
    status: int
    headers: Any
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)


class Api:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.opener = urllib.request.build_opener(_NoRedirect())

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json_body: object | None = None,
        form: dict[str, str] | None = None,
        expected: int | tuple[int, ...] = HTTPStatus.OK,
    ) -> Response:
        headers = {"Accept": "application/json"}
        body: bytes | None = None
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(json_body, separators=(",", ":")).encode()
        elif form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            body = urllib.parse.urlencode(form).encode()
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            opened = self.opener.open(request, timeout=20)
            response = Response(opened.status, opened.headers, opened.read())
        except urllib.error.HTTPError as error:
            response = Response(error.code, error.headers, error.read())
        allowed = (expected,) if isinstance(expected, int) else expected
        if response.status not in allowed:
            raise AssertionError(f"{method} {path} expected HTTP {allowed}, got {response.status}")
        return response


def login(api: Api, email: str, password: str, *, expected: int = 200) -> Response:
    return api.request(
        "POST",
        "/api/v1/auth/token",
        form={"username": email, "password": password},
        expected=expected,
    )


def assert_public_oauth_shape(payload: dict[str, object]) -> None:
    forbidden = {"access_token", "refresh_token", "scope", "client_secret", "generation"}
    assert forbidden.isdisjoint(payload)
    assert set(payload) == {
        "connected_at",
        "expires_at",
        "revoked_at",
        "scope_label",
        "scope_profile",
        "status",
    }
    assert payload["scope_profile"] == "repository"
    assert payload["scope_label"] == "Read-only repository access"


def poll_preview(api: Api, token: str, job_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        payload = api.request("GET", f"/api/v1/admin/preview-jobs/{job_id}", token=token).json()
        if payload["state"] == "succeeded":
            return payload
        if payload["state"] in {"failed", "timed_out"}:
            raise AssertionError(f"preview ended in bounded failure {payload['state']}")
        time.sleep(1)
    raise AssertionError("preview polling exceeded 120 seconds")


def confirm_first_candidate(api: Api, token: str, preview: dict[str, Any]) -> None:
    result = preview["result"]
    expected_side = (
        "direct"
        if any(side["role"] == "direct" for side in preview["repository_sides"])
        else "translations"
    )
    candidate = next(
        item for item in result["layout_candidates"] if item["repository_side"] == expected_side
    )
    response = api.request(
        "POST",
        f"/api/v1/admin/preview-jobs/{preview['id']}/confirmation",
        token=token,
        json_body={
            "preview_digest": result["digest"],
            "layout_candidate_id": candidate["id"],
            "layout_candidate_version": candidate["version"],
        },
    ).json()
    assert response["job_id"] == preview["id"]
    assert response["preview_digest"] == result["digest"]


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: phase2_compose_flow.py BACKEND_URL EMAIL TEMP_PASSWORD")
    api = Api(sys.argv[1])
    email, temporary_password = sys.argv[2:]
    new_password = "PhaseTwoOrdinary-9d81f73b-Strong!"

    assert api.request("GET", "/api/v1/health").json() == {"status": "ok"}
    restricted = login(api, email, temporary_password).json()
    assert restricted["must_change_password"] is True
    restricted_token = restricted["access_token"]
    api.request("GET", "/api/v1/users/me", token=restricted_token, expected=HTTPStatus.FORBIDDEN)
    api.request(
        "POST",
        "/api/v1/auth/change-password",
        token=restricted_token,
        json_body={
            "current_password": temporary_password,
            "new_password": new_password,
        },
        expected=HTTPStatus.NO_CONTENT,
    )
    login(api, email, temporary_password, expected=HTTPStatus.UNAUTHORIZED)
    ordinary = login(api, email, new_password).json()
    assert ordinary["must_change_password"] is False
    token = ordinary["access_token"]
    principal = api.request("GET", "/api/v1/users/me", token=token).json()
    assert principal["email"] == email and "admin" in principal["roles"]

    created_user_response = api.request(
        "POST",
        "/api/v1/admin/users",
        token=token,
        json_body={
            "email": "phase02-reviewer@example.com",
            "display_name": "Phase Two Reviewer",
            "roles": ["product_manager_reviewer", "viewer"],
        },
        expected=HTTPStatus.CREATED,
    )
    created_user = created_user_response.json()
    assert created_user_response.headers.get("Cache-Control") == "no-store"
    assert len(created_user["temporary_password"]) >= 12
    users = api.request("GET", "/api/v1/admin/users", token=token).json()
    assert any(user["email"] == "phase02-reviewer@example.com" for user in users["items"])
    assert all("temporary_password" not in user for user in users["items"])

    oauth_start = api.request("POST", "/api/v1/admin/bitbucket/oauth/start", token=token).json()
    authorization_url = oauth_start["authorization_url"]
    assert authorization_url.startswith("https://bitbucket.org/site/oauth2/authorize?")
    state = urllib.parse.parse_qs(urllib.parse.urlsplit(authorization_url).query)["state"][0]
    callback_query = urllib.parse.urlencode({"state": state, "code": "mock-code"})
    callback = api.request(
        "GET",
        f"/api/v1/admin/bitbucket/oauth/callback?{callback_query}",
        expected=HTTPStatus.SEE_OTHER,
    )
    assert callback.headers["Location"] == "/admin/bitbucket"
    oauth_status = api.request("GET", "/api/v1/admin/bitbucket", token=token).json()
    assert_public_oauth_shape(oauth_status)
    assert oauth_status["status"] == "Connected"

    repository_ids: list[str] = []
    for slug, label in (
        ("direct-app", "Direct application"),
        ("keys-app", "Keys repository"),
        ("translations-app", "Translations repository"),
    ):
        repository = api.request(
            "POST",
            "/api/v1/admin/repositories",
            token=token,
            json_body={
                "workspace": "verboflex-smoke",
                "repository_slug": slug,
                "descriptive_name": label,
            },
            expected=HTTPStatus.CREATED,
        ).json()
        repository_ids.append(repository["id"])

    repositories = api.request("GET", "/api/v1/admin/repositories", token=token).json()
    assert len(repositories["items"]) == 3
    branches = api.request(
        "GET", f"/api/v1/admin/repositories/{repository_ids[0]}/branches", token=token
    ).json()
    assert [branch["name"] for branch in branches["items"]] == ["main", "release/smoke"]
    assert branches["next_cursor"] is None
    sources = api.request(
        "GET",
        f"/api/v1/admin/repositories/{repository_ids[0]}/sources?branch=main",
        token=token,
    ).json()
    assert sources["commit_hash"] == COMMIT_HASH
    assert {item["path"] for item in sources["files"]} == {
        "app_en.ts",
        "catalog.json",
        "en.lproj/Localizable.strings",
        "res/values/strings.xml",
    }

    product = api.request(
        "POST",
        "/api/v1/admin/products",
        token=token,
        json_body={"name": "Phase Two Product", "description": "Compose smoke"},
        expected=HTTPStatus.CREATED,
    ).json()
    product_id = product["id"]
    assert product["candidate_revision"]["version"] == 1
    mappings_path = f"/api/v1/admin/products/{product_id}/candidate/mappings"
    direct = api.request(
        "POST",
        mappings_path,
        token=token,
        json_body={
            "topology": "direct",
            "repository_id": repository_ids[0],
            "source_branch": "main",
            "allowed_target_branches": ["main", "release/smoke"],
            "default_target_branch": "main",
            "expected_candidate_version": 1,
        },
        expected=HTTPStatus.CREATED,
    ).json()
    assert direct["candidate_version"] == 2
    separate = api.request(
        "POST",
        mappings_path,
        token=token,
        json_body={
            "topology": "separate",
            "sides": [
                {
                    "role": "keys",
                    "repository_id": repository_ids[1],
                    "source_branch": "main",
                },
                {
                    "role": "translations",
                    "repository_id": repository_ids[2],
                    "source_branch": "release/smoke",
                },
            ],
            "allowed_target_branches": ["main"],
            "default_target_branch": "main",
            "expected_candidate_version": 2,
        },
        expected=HTTPStatus.CREATED,
    ).json()
    assert separate["candidate_version"] == 3

    current_mappings = api.request("GET", mappings_path, token=token).json()["items"]
    assert {mapping["topology"] for mapping in current_mappings} == {"direct", "separate"}
    previews: list[dict[str, Any]] = []
    for mapping in current_mappings:
        roles = ["direct"] if mapping["topology"] == "direct" else ["keys", "translations"]
        created_preview = api.request(
            "POST",
            f"{mappings_path}/{mapping['id']}/preview-jobs",
            token=token,
            json_body={
                "expected_candidate_version": 3,
                "commits": [{"role": role, "commit_hash": COMMIT_HASH} for role in roles],
            },
            expected=HTTPStatus.ACCEPTED,
        ).json()
        preview = poll_preview(api, token, created_preview["id"])
        assert preview["is_current"] is True
        assert preview["result"] is not None
        confirm_first_candidate(api, token, preview)
        previews.append(preview)

    direct_preview = next(
        preview for preview in previews if preview["repository_sides"][0]["role"] == "direct"
    )
    assert {candidate["format"] for candidate in direct_preview["result"]["layout_candidates"]} == {
        "android_xml",
        "qt_ts",
        "json",
        "ios_strings",
    }

    current_product = api.request("GET", f"/api/v1/admin/products/{product_id}", token=token).json()
    candidate = current_product["candidate_revision"]
    published = api.request(
        "POST",
        f"/api/v1/admin/products/{product_id}/publish",
        token=token,
        json_body={
            "candidate_revision_id": candidate["id"],
            "expected_candidate_version": candidate["version"],
        },
    ).json()
    assert published["is_active"] is True
    assert published["active_revision"]["is_published"] is True
    assert published["candidate_revision"] is None

    revoked = api.request("POST", "/api/v1/admin/bitbucket/revoke", token=token).json()
    assert_public_oauth_shape(revoked)
    assert revoked["status"] == "Disconnected"
    api.request(
        "GET",
        f"/api/v1/admin/repositories/{repository_ids[0]}/branches",
        token=token,
        expected=HTTPStatus.CONFLICT,
    )
    print("phase2 compose API flow: PASS (3 repositories, 2 mappings, 4 formats)")


if __name__ == "__main__":
    main()
