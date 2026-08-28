#!/usr/bin/env python3
"""TLS mock for the exact Bitbucket OAuth and repository-read Phase 2 surface."""

from __future__ import annotations

import base64
import json
import os
import ssl
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

COMMIT_HASH = "0123456789abcdef0123456789abcdef01234567"
FILES = {
    "app_en.ts": (
        b'<TS version="2.1" language="en"><context><name>Main</name>'
        b"<message><source>hello</source><translation>Hello</translation>"
        b"</message></context></TS>"
    ),
    "catalog.json": b'{"en":{"hello":"Hello"}}',
    "en.lproj/Localizable.strings": b'"hello" = "Hello";',
    "res/values/strings.xml": (b'<resources><string name="hello">Hello</string></resources>'),
}
TREE = {
    "": (
        [
            {"path": "res", "type": "commit_directory"},
        ],
        [
            {"path": "en.lproj", "type": "commit_directory"},
            {"path": "app_en.ts", "size": len(FILES["app_en.ts"]), "type": "commit_file"},
            {
                "path": "catalog.json",
                "size": len(FILES["catalog.json"]),
                "type": "commit_file",
            },
        ],
    ),
    "en.lproj": (
        [
            {
                "path": "en.lproj/Localizable.strings",
                "size": len(FILES["en.lproj/Localizable.strings"]),
                "type": "commit_file",
            }
        ],
    ),
    "res": ([{"path": "res/values", "type": "commit_directory"}],),
    "res/values": (
        [
            {
                "path": "res/values/strings.xml",
                "size": len(FILES["res/values/strings.xml"]),
                "type": "commit_file",
            }
        ],
    ),
}

AUDIT_LOCK = threading.Lock()
AUDIT_FILE = Path(os.environ["MOCK_AUDIT_FILE"])
ACCESS_TOKEN = os.environ["MOCK_ACCESS_TOKEN"]
REFRESH_TOKEN = os.environ["MOCK_REFRESH_TOKEN"]
CLIENT_ID = os.environ["MOCK_CLIENT_ID"]
CLIENT_SECRET = os.environ["MOCK_CLIENT_SECRET"]
CALLBACK_URL = os.environ["MOCK_CALLBACK_URL"]


def audit(*, method: str, path: str, category: str) -> None:
    """Append only bounded request metadata; never record headers, bodies, or tokens."""
    record = json.dumps(
        {"category": category, "method": method, "path": path},
        separators=(",", ":"),
        sort_keys=True,
    )
    with AUDIT_LOCK, AUDIT_FILE.open("a", encoding="utf-8") as destination:
        destination.write(record + "\n")


class MockBitbucketHandler(BaseHTTPRequestHandler):
    """Serve the fixed OAuth exchange and approved read-only repository paths."""

    server_version = "VerboFlexMockBitbucket/1"
    sys_version = ""

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _json(self, status: HTTPStatus, payload: object) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-OAuth-Scopes", "repository")
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, status: HTTPStatus, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-OAuth-Scopes", "repository")
        self.end_headers()
        self.wfile.write(payload)

    def _authorized(self) -> bool:
        if self.headers.get("Authorization") == f"Bearer {ACCESS_TOKEN}":
            return True
        self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
        return False

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path != "/site/oauth2/access_token":
            audit(method="POST", path=parsed.path, category="forbidden-mutation")
            self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "read_only"})
            return
        audit(method="POST", path=parsed.path, category="oauth-token-exchange")
        expected_basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        if self.headers.get("Authorization") != f"Basic {expected_basic}":
            audit(method="POST", path=parsed.path, category="invalid-oauth-client")
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "invalid_client"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(length).decode("ascii"), strict_parsing=True)
        if (
            form.get("grant_type") != ["authorization_code"]
            or form.get("code") != ["mock-code"]
            or form.get("redirect_uri") != [CALLBACK_URL]
        ):
            audit(method="POST", path=parsed.path, category="invalid-oauth-grant")
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_grant"})
            return
        self._json(
            HTTPStatus.OK,
            {
                "access_token": ACCESS_TOKEN,
                "expires_in": 3600,
                "refresh_token": REFRESH_TOKEN,
                "scope": "repository",
                "token_type": "bearer",
            },
        )

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path == "/_health":
            self._json(HTTPStatus.OK, {"status": "ok"})
            return
        if not parsed.path.startswith("/2.0/repositories/"):
            audit(method="GET", path=parsed.path, category="unapproved-read")
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not self._authorized():
            return
        audit(method="GET", path=parsed.path, category="repository-read")
        self._repository_read(parsed.path, parse_qs(parsed.query))

    def do_PATCH(self) -> None:  # noqa: N802
        self._reject_mutation()

    def do_PUT(self) -> None:  # noqa: N802
        self._reject_mutation()

    def do_DELETE(self) -> None:  # noqa: N802
        self._reject_mutation()

    def _reject_mutation(self) -> None:
        parsed = urlsplit(self.path)
        audit(method=self.command, path=parsed.path, category="forbidden-mutation")
        self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "read_only"})

    def _repository_read(self, raw_path: str, query: dict[str, list[str]]) -> None:
        relative = raw_path.removeprefix("/2.0/repositories/").strip("/")
        parts = relative.split("/")
        if len(parts) < 2:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        workspace, slug, *resource = (unquote(part) for part in parts)
        repository_url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{slug}"
        if not resource:
            self._json(
                HTTPStatus.OK,
                {"full_name": f"{workspace}/{slug}", "scm": "git", "uuid": "{mock-repo}"},
            )
            return
        if resource[:2] == ["refs", "branches"]:
            self._branches(repository_url, resource[2:], query)
            return
        if resource[0] == "src":
            self._source(repository_url, resource[1:], query)
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _branches(
        self,
        repository_url: str,
        detail: list[str],
        query: dict[str, list[str]],
    ) -> None:
        if detail:
            branch = "/".join(detail)
            if branch not in {"main", "release/smoke"}:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            self._json(HTTPStatus.OK, {"name": branch, "target": {"hash": COMMIT_HASH}})
            return
        if query.get("page") == ["2"]:
            self._json(
                HTTPStatus.OK,
                {"values": [{"name": "release/smoke", "target": {"hash": COMMIT_HASH}}]},
            )
            return
        self._json(
            HTTPStatus.OK,
            {
                "next": f"{repository_url}/refs/branches?pagelen=100&page=2",
                "values": [{"name": "main", "target": {"hash": COMMIT_HASH}}],
            },
        )

    def _source(
        self,
        repository_url: str,
        resource: list[str],
        query: dict[str, list[str]],
    ) -> None:
        if not resource or resource[0] != COMMIT_HASH:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        repository_path = "/".join(resource[1:]).strip("/")
        if "pagelen" not in query:
            payload = FILES.get(repository_path)
            if payload is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            self._bytes(HTTPStatus.OK, payload)
            return
        pages = TREE.get(repository_path)
        if pages is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        page_index = 1 if query.get("page") == ["2"] else 0
        if page_index >= len(pages):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_page"})
            return
        response: dict[str, object] = {"values": pages[page_index]}
        if page_index + 1 < len(pages):
            suffix = f"/{repository_path}" if repository_path else "/"
            response["next"] = f"{repository_url}/src/{COMMIT_HASH}{suffix}?pagelen=100&page=2"
        self._json(HTTPStatus.OK, response)


def main() -> None:
    """Run a loopback-independent TLS endpoint on the Compose network."""
    certificate = os.environ["MOCK_TLS_CERT"]
    private_key = os.environ["MOCK_TLS_KEY"]
    port = int(os.environ.get("MOCK_PORT", "443"))
    server = ThreadingHTTPServer(("0.0.0.0", port), MockBitbucketHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate, private_key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
