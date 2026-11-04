"""Optional private, bounded cache of validated immutable source bytes."""

import hashlib
import os
import sqlite3
import stat
import time
from collections.abc import Callable
from contextlib import closing
from pathlib import Path


class SourceFileCache:
    """Share commit-pinned files between worker processes; failures remain cache misses."""

    def __init__(
        self,
        directory: str | Path,
        *,
        max_bytes: int = 64 * 1024 * 1024,
        max_entries: int = 6_000,
        ttl_seconds: int = 900,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if min(max_bytes, max_entries, ttl_seconds) < 1:
            raise ValueError("Source cache bounds must be positive")
        self.directory = Path(directory)
        self.max_bytes = max_bytes
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.clock = clock

    def _connect(self) -> sqlite3.Connection:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.directory.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077
        ):
            raise OSError("Source cache directory must be private")
        path = self.directory / "sources.sqlite3"
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077
        ):
            raise OSError("Source cache database must be private")
        db = sqlite3.connect(path, timeout=0.1)
        try:
            db.execute("PRAGMA secure_delete=ON")
            db.execute("PRAGMA max_page_count=32768")
            db.execute(
                "CREATE TABLE IF NOT EXISTS source_files "
                "(key TEXT PRIMARY KEY, expires REAL NOT NULL, digest TEXT NOT NULL, "
                "content BLOB NOT NULL)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS source_expiry ON source_files(expires)")
        except BaseException:
            db.close()
            raise
        return db

    def get(self, key: str) -> bytes | None:
        try:
            with closing(self._connect()) as db, db:
                db.execute("DELETE FROM source_files WHERE expires <= ?", (self.clock(),))
                row = db.execute(
                    "SELECT digest, content FROM source_files "
                    "WHERE key = ? AND length(content) <= 1048576",
                    (key,),
                ).fetchone()
                if row is not None and hashlib.sha256(row[1]).hexdigest() == row[0]:
                    return bytes(row[1])
        except OSError, sqlite3.Error:
            pass
        return None

    def put(self, key: str, content: bytes) -> None:
        if len(content) > min(self.max_bytes, 1_048_576):
            return
        try:
            with closing(self._connect()) as db, db:
                now = self.clock()
                db.execute("DELETE FROM source_files WHERE expires <= ?", (now,))
                db.execute(
                    "INSERT OR REPLACE INTO source_files VALUES (?, ?, ?, ?)",
                    (key, now + self.ttl_seconds, hashlib.sha256(content).hexdigest(), content),
                )
                while True:
                    count, size = db.execute(
                        "SELECT count(*), coalesce(sum(length(content)), 0) FROM source_files"
                    ).fetchone()
                    if count <= self.max_entries and size <= self.max_bytes:
                        break
                    db.execute(
                        "DELETE FROM source_files WHERE key IN "
                        "(SELECT key FROM source_files ORDER BY expires, key LIMIT 1)"
                    )
        except OSError, sqlite3.Error:
            pass
