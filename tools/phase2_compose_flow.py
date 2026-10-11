#!/usr/bin/env python3
"""Exercise the complete Phase 2 HTTP journey without printing secret material."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
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
            raise AssertionError(
                f"{method} {path} expected HTTP {allowed}, got {response.status}"
            )
        return response


def login(api: Api, email: str, password: str, *, expected: int = 200) -> Response:
    return api.request(
        "POST",
        "/api/v1/auth/token",
        form={"username": email, "password": password},
        expected=expected,
    )


def assert_public_oauth_shape(payload: dict[str, object]) -> None:
    forbidden = {
        "access_token",
        "refresh_token",
        "scope",
        "client_secret",
        "generation",
    }
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
        payload = api.request(
            "GET", f"/api/v1/admin/preview-jobs/{job_id}", token=token
        ).json()
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
        item
        for item in result["layout_candidates"]
        if item["repository_side"] == expected_side
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


def _ordinary_admin_token(
    api: Api,
    email: str,
    password: str,
    *,
    new_password: str | None = None,
) -> str:
    authority = login(api, email, password).json()
    if authority["must_change_password"]:
        if new_password is None:
            raise AssertionError("ordinary administrator password required")
        api.request(
            "POST",
            "/api/v1/auth/change-password",
            token=authority["access_token"],
            json_body={"current_password": password, "new_password": new_password},
            expected=HTTPStatus.NO_CONTENT,
        )
        authority = login(api, email, new_password).json()
    assert authority["must_change_password"] is False
    return str(authority["access_token"])


def wait_for_preview_state(
    api: Api,
    token: str,
    job_id: str,
    expected_state: str,
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Poll one durable job state under a caller-owned monotonic deadline."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        payload = api.request(
            "GET", f"/api/v1/admin/preview-jobs/{job_id}", token=token
        ).json()
        if payload["state"] == expected_state:
            return payload
        if payload["state"] in {"failed", "timed_out", "succeeded"}:
            raise AssertionError(
                f"preview reached {payload['state']} before {expected_state}"
            )
        time.sleep(0.1)
    raise AssertionError(f"preview did not reach {expected_state} within the bound")


def _write_worker_loss_state(path: Path, payload: dict[str, Any]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
        json.dump(payload, destination, separators=(",", ":"), sort_keys=True)


def _read_worker_loss_state(path: Path) -> dict[str, Any]:
    if path.stat().st_mode & 0o077:
        raise AssertionError("worker-loss state must be owner-only")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("worker-loss state is invalid")
    return payload


def worker_loss_setup(
    base_url: str,
    email: str,
    temporary_password: str,
    new_password: str,
    state_path: Path,
) -> None:
    """Create one direct preview and return only after running is durable."""
    api = Api(base_url)
    token = _ordinary_admin_token(
        api,
        email,
        temporary_password,
        new_password=new_password,
    )
    api.request("POST", "/api/v1/admin/bitbucket/connect", token=token)
    repository = api.request(
        "POST",
        "/api/v1/admin/repositories",
        token=token,
        json_body={
            "workspace": "verboflex-smoke",
            "repository_slug": "translations",
            "descriptive_name": "Worker loss translations",
        },
        expected=HTTPStatus.CREATED,
    ).json()
    product = api.request(
        "POST",
        "/api/v1/admin/products",
        token=token,
        json_body={"name": "Worker Loss Product", "description": "Process-loss smoke"},
        expected=HTTPStatus.CREATED,
    ).json()
    product_id = product["id"]
    mappings_path = f"/api/v1/admin/products/{product_id}/candidate/mappings"
    mapping = api.request(
        "POST",
        mappings_path,
        token=token,
        json_body={
            "topology": "direct",
            "repository_id": repository["id"],
            "source_branch": "main",
            "allowed_target_branches": ["main"],
            "default_target_branch": "main",
            "expected_candidate_version": 1,
        },
        expected=HTTPStatus.CREATED,
    ).json()
    request_body = {
        "expected_candidate_version": mapping["candidate_version"],
        "commits": [{"role": "direct", "commit_hash": COMMIT_HASH}],
    }
    preview_path = f"{mappings_path}/{mapping['id']}/preview-jobs"
    job = api.request(
        "POST",
        preview_path,
        token=token,
        json_body=request_body,
        expected=HTTPStatus.ACCEPTED,
    ).json()
    running = wait_for_preview_state(
        api, token, job["id"], "running", timeout_seconds=30
    )
    assert running["started_at"] is not None
    _write_worker_loss_state(
        state_path,
        {
            "job_id": job["id"],
            "attempt": job["attempt"],
            "preview_path": preview_path,
            "request_body": request_body,
        },
    )


def worker_loss_terminal(
    base_url: str,
    email: str,
    password: str,
    state_path: Path,
    timeout_seconds: int,
) -> None:
    """Observe watchdog terminalization without relying on a task callback."""
    api = Api(base_url)
    token = _ordinary_admin_token(api, email, password)
    state = _read_worker_loss_state(state_path)
    terminal = wait_for_preview_state(
        api,
        token,
        state["job_id"],
        "timed_out",
        timeout_seconds=timeout_seconds,
    )
    assert terminal["error_code"] == "time_limit_exceeded"
    assert terminal["finished_at"] is not None
    assert terminal["result"] is None
    state["terminal_finished_at"] = terminal["finished_at"]
    state_path.write_text(
        json.dumps(state, separators=(",", ":"), sort_keys=True), encoding="utf-8"
    )
    state_path.chmod(0o600)


def retry_preview_job(
    base_url: str,
    email: str,
    password: str,
    state_path: Path,
) -> None:
    """Retry as a new attempt and prove the original terminal row is immutable."""
    api = Api(base_url)
    token = _ordinary_admin_token(api, email, password)
    state = _read_worker_loss_state(state_path)
    retry = api.request(
        "POST",
        state["preview_path"],
        token=token,
        json_body=state["request_body"],
        expected=HTTPStatus.ACCEPTED,
    ).json()
    assert retry["id"] != state["job_id"]
    assert retry["attempt"] == state["attempt"] + 1
    succeeded = wait_for_preview_state(
        api, token, retry["id"], "succeeded", timeout_seconds=60
    )
    assert succeeded["result"] is not None
    original = api.request(
        "GET", f"/api/v1/admin/preview-jobs/{state['job_id']}", token=token
    ).json()
    assert original["state"] == "timed_out"
    assert original["error_code"] == "time_limit_exceeded"
    assert original["finished_at"] == state["terminal_finished_at"]
    assert original["result"] is None


def _assert_cursor_boundary(
    api: Api,
    token: str,
    path: str,
    *,
    expected_count: int,
) -> None:
    first = api.request("GET", f"{path}?limit=50", token=token).json()
    assert len(first["items"]) == min(expected_count, 50)
    if expected_count <= 50:
        assert first["next_cursor"] is None
    else:
        assert isinstance(first["next_cursor"], str) and first["next_cursor"]
        second_query = urllib.parse.urlencode(
            {"limit": 50, "cursor": first["next_cursor"]}
        )
        second = api.request("GET", f"{path}?{second_query}", token=token).json()
        assert len(second["items"]) == expected_count - 50
        assert second["next_cursor"] is None
    maximum = api.request("GET", f"{path}?limit=100", token=token).json()
    assert len(maximum["items"]) == expected_count
    assert maximum["next_cursor"] is None
    api.request(
        "GET",
        f"{path}?limit=101",
        token=token,
        expected=HTTPStatus.UNPROCESSABLE_ENTITY,
    )


def run_gap_boundaries(base_url: str, email: str, password: str) -> None:
    """Exercise disposable 0/1/50/51 collection edges without provider writes."""
    api = Api(base_url)
    token = _ordinary_admin_token(api, email, password)
    status = api.request("GET", "/api/v1/admin/bitbucket", token=token).json()
    assert_public_oauth_shape(status)
    assert status["status"] == "Disconnected"

    products_path = "/api/v1/admin/products"
    assert api.request("GET", products_path, token=token).json() == {
        "items": [],
        "next_cursor": None,
    }
    for index in range(1, 52):
        api.request(
            "POST",
            products_path,
            token=token,
            json_body={
                "name": f"Gap Boundary Product {index:02d}",
                "description": "Disposable 0/1/50/51 Compose proof",
            },
            expected=HTTPStatus.CREATED,
        )
    _assert_cursor_boundary(api, token, products_path, expected_count=51)

    repositories_path = "/api/v1/admin/repositories"
    initial_repositories = api.request("GET", repositories_path, token=token).json()
    assert len(initial_repositories["items"]) == 1
    assert initial_repositories["next_cursor"] is None
    for index in range(1, 51):
        api.request(
            "POST",
            repositories_path,
            token=token,
            json_body={
                "workspace": "verboflex-gap-closure",
                "repository_slug": f"repository-{index:02d}",
                "descriptive_name": f"Gap repository {index:02d}",
            },
            expected=HTTPStatus.CREATED,
        )
    _assert_cursor_boundary(api, token, repositories_path, expected_count=51)
    print("phase2 gap boundaries: PASS (0/1/50/51 and maximum 100, 101 rejected)")


def run_worker_loss_recovery(
    base_url: str,
    email: str,
    password: str,
    state_path: Path,
    timeout_seconds: int,
) -> None:
    """Terminalize the killed attempt, then prove isolated replacement success."""
    worker_loss_terminal(base_url, email, password, state_path, timeout_seconds)
    retry_preview_job(base_url, email, password, state_path)


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "--gap-boundaries":
        if len(sys.argv) != 5:
            raise SystemExit("invalid gap-boundary arguments")
        run_gap_boundaries(sys.argv[2], sys.argv[3], sys.argv[4])
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "--worker-loss-setup":
        if len(sys.argv) != 7:
            raise SystemExit("invalid worker-loss setup arguments")
        worker_loss_setup(
            sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], Path(sys.argv[6])
        )
        print("phase2 worker-loss setup: PASS (running durable, provider blocked)")
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "--worker-loss-terminal":
        if len(sys.argv) != 7:
            raise SystemExit("invalid worker-loss terminal arguments")
        worker_loss_terminal(
            sys.argv[2], sys.argv[3], sys.argv[4], Path(sys.argv[5]), int(sys.argv[6])
        )
        print("phase2 worker-loss terminalization: PASS (time_limit_exceeded)")
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "--worker-loss-retry":
        if len(sys.argv) != 6:
            raise SystemExit("invalid worker-loss retry arguments")
        retry_preview_job(sys.argv[2], sys.argv[3], sys.argv[4], Path(sys.argv[5]))
        print(
            "phase2 worker-loss retry: PASS (new attempt succeeded, original immutable)"
        )
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "--worker-loss-recovery":
        if len(sys.argv) != 7:
            raise SystemExit("invalid worker-loss recovery arguments")
        run_worker_loss_recovery(
            sys.argv[2], sys.argv[3], sys.argv[4], Path(sys.argv[5]), int(sys.argv[6])
        )
        print(
            "phase2 worker-loss recovery: PASS "
            "(time_limit_exceeded watchdog terminalized, replacement isolated)"
        )
        return
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: phase2_compose_flow.py BACKEND_URL EMAIL TEMP_PASSWORD"
        )
    api = Api(sys.argv[1])
    email, temporary_password = sys.argv[2:]
    new_password = "PhaseTwoOrdinary-9d81f73b-Strong!"

    assert api.request("GET", "/api/v1/health").json() == {"status": "ok"}
    restricted = login(api, email, temporary_password).json()
    assert restricted["must_change_password"] is True
    restricted_token = restricted["access_token"]
    api.request(
        "GET", "/api/v1/users/me", token=restricted_token, expected=HTTPStatus.FORBIDDEN
    )
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
    assert any(
        user["email"] == "phase02-reviewer@example.com" for user in users["items"]
    )
    assert all("temporary_password" not in user for user in users["items"])

    oauth_start = api.request(
        "POST", "/api/v1/admin/bitbucket/oauth/start", token=token
    ).json()
    authorization_url = oauth_start["authorization_url"]
    assert authorization_url.startswith("https://bitbucket.org/site/oauth2/authorize?")
    state = urllib.parse.parse_qs(urllib.parse.urlsplit(authorization_url).query)[
        "state"
    ][0]
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
    assert {mapping["topology"] for mapping in current_mappings} == {
        "direct",
        "separate",
    }
    previews: list[dict[str, Any]] = []
    for mapping in current_mappings:
        roles = (
            ["direct"] if mapping["topology"] == "direct" else ["keys", "translations"]
        )
        created_preview = api.request(
            "POST",
            f"{mappings_path}/{mapping['id']}/preview-jobs",
            token=token,
            json_body={
                "expected_candidate_version": 3,
                "commits": [
                    {"role": role, "commit_hash": COMMIT_HASH} for role in roles
                ],
            },
            expected=HTTPStatus.ACCEPTED,
        ).json()
        preview = poll_preview(api, token, created_preview["id"])
        assert preview["is_current"] is True
        assert preview["result"] is not None
        confirm_first_candidate(api, token, preview)
        previews.append(preview)

    direct_preview = next(
        preview
        for preview in previews
        if preview["repository_sides"][0]["role"] == "direct"
    )
    assert {
        candidate["format"]
        for candidate in direct_preview["result"]["layout_candidates"]
    } == {
        "android_xml",
        "qt_ts",
        "json",
        "ios_strings",
    }

    current_product = api.request(
        "GET", f"/api/v1/admin/products/{product_id}", token=token
    ).json()
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
