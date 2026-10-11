#!/usr/bin/env python3
"""Secret-safe Phase 2 probe that drives only authenticated VerboFlex APIs."""

from __future__ import annotations

import ast
import json
import os
import re
import stat
import sys
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from typing import Any, NoReturn
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_ENV_BYTES = 65_536
MAX_RESPONSE_BYTES = 1_048_576
REQUEST_TIMEOUT_SECONDS = 20
EXACT_OPT_IN = "production-api-read-only-confirmed"
_ENV_NAME = re.compile(r"[A-Z][A-Z0-9_]*")
_REPOSITORY_PART = re.compile(r"[A-Za-z0-9._-]+")
_REQUIRED_KEYS = (
    "VERBOFLEX_LIVE_PROVIDER_OPT_IN",
    "VERBOFLEX_BASE_URL",
    "VERBOFLEX_ADMIN_EMAIL",
    "VERBOFLEX_ADMIN_PASSWORD",
    "VERBOFLEX_ADMIN_NEW_PASSWORD",
    "BITBUCKET_WORKSPACE",
    "BITBUCKET_REPOSITORY_SLUG",
    "BITBUCKET_BRANCH",
)
_DIAGNOSTIC_STAGE = "configuration"


class LiveSmokeRejected(RuntimeError):
    """Reject an unsafe or invalid probe with a stable non-secret diagnostic."""


class LiveSmokeSkipped(RuntimeError):
    """Report an unmet opt-in/configuration precondition before application contact."""


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


def _reject() -> NoReturn:
    raise LiveSmokeRejected(f"local production API smoke rejected during {_DIAGNOSTIC_STAGE}")


def _skip() -> NoReturn:
    raise LiveSmokeSkipped("local production API smoke skipped")


def _parse_dotenv_value(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        _skip()
    if value[0] in {"'", '"'}:
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            _reject()
        if not isinstance(parsed, str) or not parsed:
            _skip()
        return parsed
    if any(character.isspace() for character in value) or "#" in value:
        _reject()
    return value


def _read_secure_dotenv(path: Path) -> dict[str, str]:
    try:
        metadata = path.lstat()
    except OSError:
        _skip()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_uid != os.getuid()
        or metadata.st_size > MAX_ENV_BYTES
    ):
        _reject()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        _reject()
    if "\x00" in text:
        _reject()
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        if "=" not in line:
            _reject()
        name, raw_value = line.split("=", 1)
        if _ENV_NAME.fullmatch(name) is None or name in values:
            _reject()
        values[name] = _parse_dotenv_value(raw_value)
    return values


@dataclass(frozen=True, slots=True)
class LiveSmokeConfig:
    """Local administrator authority plus one non-secret repository identity."""

    base_url: str
    administrator_email: str
    administrator_password: str = field(repr=False)
    administrator_new_password: str = field(repr=False)
    workspace: str
    repository_slug: str
    branch: str

    @classmethod
    def from_dotenv(cls, path: Path) -> LiveSmokeConfig:
        values = _read_secure_dotenv(path)
        if values.get("VERBOFLEX_LIVE_PROVIDER_OPT_IN") != EXACT_OPT_IN:
            _skip()
        if any(not values.get(name) for name in _REQUIRED_KEYS):
            _skip()
        base_url = values["VERBOFLEX_BASE_URL"].rstrip("/")
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            _reject()
        workspace = values["BITBUCKET_WORKSPACE"]
        repository_slug = values["BITBUCKET_REPOSITORY_SLUG"]
        branch = values["BITBUCKET_BRANCH"]
        if (
            _REPOSITORY_PART.fullmatch(workspace) is None
            or _REPOSITORY_PART.fullmatch(repository_slug) is None
            or not branch
            or len(branch) > 255
            or "\\" in branch
            or any(ord(character) < 32 for character in branch)
            or any(part in {"", ".", ".."} for part in branch.split("/"))
        ):
            _reject()
        return cls(
            base_url=base_url,
            administrator_email=values["VERBOFLEX_ADMIN_EMAIL"],
            administrator_password=values["VERBOFLEX_ADMIN_PASSWORD"],
            administrator_new_password=values["VERBOFLEX_ADMIN_NEW_PASSWORD"],
            workspace=workspace,
            repository_slug=repository_slug,
            branch=branch,
        )


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    headers: Any
    body: bytes = field(repr=False)

    def json(self) -> dict[str, Any]:
        try:
            decoded = json.loads(self.body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            _reject()
        if not isinstance(decoded, dict):
            _reject()
        return decoded


class LocalApi:
    """Bounded client for the loopback VerboFlex API only."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url
        self._opener = build_opener(_RejectRedirects())

    def request(
        self,
        method: str,
        path: str,
        *,
        session_token: str | None = None,
        json_body: object | None = None,
        form: dict[str, str] | None = None,
        expected: int | tuple[int, ...] = HTTPStatus.OK,
    ) -> Response:
        if not path.startswith("/api/v1/") or "://" in path:
            _reject()
        headers = {"Accept": "application/json"}
        body: bytes | None = None
        if session_token is not None:
            headers["Authorization"] = f"Bearer {session_token}"
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(json_body, separators=(",", ":")).encode()
        elif form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            body = urlencode(form).encode()
        request = Request(
            f"{self._base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with self._opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as opened:
                response_body = opened.read(MAX_RESPONSE_BYTES + 1)
                response = Response(opened.status, opened.headers, response_body)
        except HTTPError as error:
            response = Response(
                error.code,
                error.headers,
                error.read(MAX_RESPONSE_BYTES + 1),
            )
        except (URLError, OSError, TimeoutError):
            _reject()
        if len(response.body) > MAX_RESPONSE_BYTES:
            _reject()
        allowed = (expected,) if isinstance(expected, int) else expected
        if response.status not in allowed:
            _reject()
        return response


def _login(api: LocalApi, config: LiveSmokeConfig) -> str:
    response = api.request(
        "POST",
        "/api/v1/auth/token",
        form={
            "username": config.administrator_email,
            "password": config.administrator_password,
        },
    ).json()
    token = response.get("access_token")
    if not isinstance(token, str) or not token:
        _reject()
    if response.get("must_change_password") is True:
        api.request(
            "POST",
            "/api/v1/auth/change-password",
            session_token=token,
            json_body={
                "current_password": config.administrator_password,
                "new_password": config.administrator_new_password,
            },
            expected=HTTPStatus.NO_CONTENT,
        )
        response = api.request(
            "POST",
            "/api/v1/auth/token",
            form={
                "username": config.administrator_email,
                "password": config.administrator_new_password,
            },
        ).json()
        token = response.get("access_token")
        if not isinstance(token, str) or not token:
            _reject()
    return token


def _assert_connection(payload: dict[str, Any], expected_status: str) -> None:
    if set(payload) != {
        "connected_at",
        "expires_at",
        "revoked_at",
        "scope_label",
        "scope_profile",
        "status",
    }:
        _reject()
    if payload.get("status") != expected_status or payload.get("scope_profile") != "repository":
        _reject()


def _repository_id(api: LocalApi, config: LiveSmokeConfig, session_token: str) -> str:
    response = api.request(
        "POST",
        "/api/v1/admin/repositories",
        session_token=session_token,
        json_body={
            "workspace": config.workspace,
            "repository_slug": config.repository_slug,
            "descriptive_name": "Phase 2 provider smoke",
        },
        expected=(HTTPStatus.CREATED, HTTPStatus.CONFLICT),
    )
    if response.status == HTTPStatus.CREATED:
        repository_id = response.json().get("id")
        if isinstance(repository_id, str) and repository_id:
            return repository_id
        _reject()
    collection = api.request(
        "GET",
        "/api/v1/admin/repositories?limit=100",
        session_token=session_token,
    ).json()
    items = collection.get("items")
    if not isinstance(items, list):
        _reject()
    for item in items:
        if (
            isinstance(item, dict)
            and item.get("workspace") == config.workspace.casefold()
            and item.get("repository_slug") == config.repository_slug.casefold()
            and isinstance(item.get("id"), str)
        ):
            return item["id"]
    _reject()


def run(path: Path) -> None:
    global _DIAGNOSTIC_STAGE

    config = LiveSmokeConfig.from_dotenv(path)
    api = LocalApi(config.base_url)
    _DIAGNOSTIC_STAGE = "administrator-login"
    session_token = _login(api, config)
    _DIAGNOSTIC_STAGE = "initial-connect"
    connected = api.request(
        "POST",
        "/api/v1/admin/bitbucket/connect",
        session_token=session_token,
    ).json()
    _assert_connection(connected, "Connected")
    _DIAGNOSTIC_STAGE = "initial-status"
    _assert_connection(
        api.request(
            "GET",
            "/api/v1/admin/bitbucket",
            session_token=session_token,
        ).json(),
        "Connected",
    )
    _DIAGNOSTIC_STAGE = "reconnect"
    _assert_connection(
        api.request(
            "POST",
            "/api/v1/admin/bitbucket/reconnect",
            session_token=session_token,
        ).json(),
        "Connected",
    )
    _DIAGNOSTIC_STAGE = "reconnect-status"
    _assert_connection(
        api.request(
            "GET",
            "/api/v1/admin/bitbucket",
            session_token=session_token,
        ).json(),
        "Connected",
    )
    _DIAGNOSTIC_STAGE = "first-revoke"
    _assert_connection(
        api.request(
            "POST",
            "/api/v1/admin/bitbucket/revoke",
            session_token=session_token,
        ).json(),
        "Disconnected",
    )
    _DIAGNOSTIC_STAGE = "revoked-status"
    _assert_connection(
        api.request(
            "GET",
            "/api/v1/admin/bitbucket",
            session_token=session_token,
        ).json(),
        "Disconnected",
    )
    _DIAGNOSTIC_STAGE = "reacquire"
    _assert_connection(
        api.request(
            "POST",
            "/api/v1/admin/bitbucket/connect",
            session_token=session_token,
        ).json(),
        "Connected",
    )
    _DIAGNOSTIC_STAGE = "reacquired-status"
    _assert_connection(
        api.request(
            "GET",
            "/api/v1/admin/bitbucket",
            session_token=session_token,
        ).json(),
        "Connected",
    )
    _DIAGNOSTIC_STAGE = "repository-registration"
    repository_id = _repository_id(api, config, session_token)
    _DIAGNOSTIC_STAGE = "branch-list"
    branches = api.request(
        "GET",
        f"/api/v1/admin/repositories/{repository_id}/branches?limit=100",
        session_token=session_token,
    ).json()
    items = branches.get("items")
    if not isinstance(items, list) or config.branch not in {
        item.get("name") for item in items if isinstance(item, dict)
    }:
        _reject()
    _DIAGNOSTIC_STAGE = "source-read"
    sources = api.request(
        "GET",
        (
            f"/api/v1/admin/repositories/{repository_id}/sources?"
            f"{urlencode({'branch': config.branch})}"
        ),
        session_token=session_token,
    ).json()
    if not isinstance(sources.get("commit_hash"), str) or not sources.get("files"):
        _reject()
    _DIAGNOSTIC_STAGE = "final-revoke"
    _assert_connection(
        api.request(
            "POST",
            "/api/v1/admin/bitbucket/revoke",
            session_token=session_token,
        ).json(),
        "Disconnected",
    )
    _DIAGNOSTIC_STAGE = "terminal-status"
    _assert_connection(
        api.request(
            "GET",
            "/api/v1/admin/bitbucket",
            session_token=session_token,
        ).json(),
        "Disconnected",
    )


def main() -> int:
    if len(sys.argv) != 2:
        print("phase2-live SKIP: secure local API configuration is required")
        return 0
    try:
        run(Path(sys.argv[1]))
    except LiveSmokeSkipped:
        print("phase2-live SKIP: opt-in or local server configuration is unavailable")
        return 0
    except LiveSmokeRejected as error:
        print(f"phase2-live error: {error}", file=sys.stderr)
        return 1
    except Exception:
        print("phase2-live error: production API smoke rejected", file=sys.stderr)
        return 1
    print(
        "phase2 live provider production API smoke: PASS\n"
        "provider_gets_expected=5 provider_writes_expected=0 final_local_revoke=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
