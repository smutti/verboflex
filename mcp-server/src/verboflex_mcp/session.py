"""Private native-client sessions; no passwords in MCP arguments or persistent storage."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from filelock import FileLock

COOKIE = "__Host-verboflex_refresh"


class ConnectorError(Exception):
    """An intentionally safe, user-facing connector failure."""


def api_url(value: str) -> str:
    """Credentials may travel only to HTTPS or an explicit loopback development server."""
    try:
        url = urlsplit(value)
        # Accessing port validates malformed/out-of-range ports as well.
        _ = url.port
    except ValueError as error:
        raise ConnectorError("Invalid API URL.") from error
    if (
        url.scheme not in {"http", "https"}
        or not url.hostname
        or url.username is not None
        or url.password is not None
        or url.query
        or url.fragment
        or (url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1", "::1"})
    ):
        raise ConnectorError("Use an HTTPS API URL, or HTTP on localhost for development.")
    return value.rstrip("/")


def http_client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(30, connect=5), follow_redirects=False)


@dataclass(repr=False)
class Session:
    api_url: str
    access_token: str
    refresh_token: str
    expires_at: float


def read_authority(response: httpx.Response, url: str) -> Session:
    if response.status_code != 200:
        if response.status_code == 429:
            raise ConnectorError("Login rate limit reached. Wait before signing in again.")
        if response.status_code >= 500:
            raise ConnectorError("Authentication service unavailable. Try again later.")
        raise ConnectorError("Session unavailable. Run verboflex-mcp login again.")
    try:
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError
        if body.get("must_change_password"):
            raise ConnectorError("Change your password in VerboFlex, then log in again.")
        token = body["access_token"]
        refresh = response.cookies[COOKIE]
        expiry = body["expires_in"]
        if not isinstance(token, str) or not token or not refresh or not 0 < expiry <= 3600:
            raise ValueError
        return Session(url, token, refresh, time.time() + expiry)
    except (ValueError, KeyError, TypeError, httpx.CookieConflict) as error:
        raise ConnectorError("Invalid authentication response from VerboFlex.") from error


class SessionStore:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().absolute()
        self.lock = FileLock(str(self.path) + ".lock", timeout=35, mode=0o600)

    def prepare(self) -> None:
        self.path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        if os.name != "nt":
            info = self.path.parent.stat()
            if info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise ConnectorError(
                    "Session directory must be owned by you and not writable by others."
                )

    def read(self) -> Session:
        try:
            info = self.path.lstat()
            if not stat.S_ISREG(info.st_mode) or (
                os.name != "nt" and (info.st_mode & 0o077 or info.st_uid != os.getuid())
            ):
                raise ConnectorError("Session file must be private (chmod 600) and owned by you.")
            data = json.loads(self.path.read_text())
            session = Session(**data)
            api_url(session.api_url)
            if (
                not isinstance(session.access_token, str)
                or not isinstance(session.refresh_token, str)
                or not isinstance(session.expires_at, (int, float))
                or not session.access_token
                or not session.refresh_token
            ):
                raise ValueError
            return session
        except (OSError, ValueError, TypeError) as error:
            raise ConnectorError("Session unavailable. Run verboflex-mcp login first.") from error

    def write(self, session: Session) -> None:
        descriptor, name = tempfile.mkstemp(prefix=".session-", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w") as stream:
                json.dump(asdict(session), stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def login(self, client: httpx.Client, url: str, username: str, password: str) -> None:
        url = api_url(url)
        self.prepare()
        with self.lock:
            if self.path.exists():
                raise ConnectorError(
                    "A session already exists. Log out or use another session file."
                )
            response = client.post(
                url + "/auth/token", data={"username": username, "password": password}
            )
            self.write(read_authority(response, url))

    def authority(self, client: httpx.Client) -> Session:
        self.prepare()
        # Re-read under the shared lock: simultaneous Codex/Claude processes must not
        # replay a rotated refresh token and revoke each other's session family.
        with self.lock:
            session = self.read()
            if session.expires_at <= time.time() + 30:
                response = client.post(
                    session.api_url + "/auth/refresh",
                    headers={"Cookie": f"{COOKIE}={session.refresh_token}"},
                )
                session = read_authority(response, session.api_url)
                self.write(session)
            return session

    def logout(self, client: httpx.Client) -> None:
        self.prepare()
        with self.lock:
            session = self.read()
            response = client.post(
                session.api_url + "/auth/logout",
                headers={"Cookie": f"{COOKIE}={session.refresh_token}"},
            )
            if response.status_code != 204:
                raise ConnectorError(
                    "Logout failed; session file retained so revocation can be retried."
                )
            self.path.unlink()
