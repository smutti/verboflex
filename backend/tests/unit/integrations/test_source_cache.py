"""Synthetic immutable-source cache boundaries."""

import os
import sqlite3

from verboflex.integrations.bitbucket.source_cache import SourceFileCache


def test_shared_cache_expiry_and_private_permissions(tmp_path):
    now = [100.0]
    directory = tmp_path / "cache"
    first = SourceFileCache(directory, ttl_seconds=10, clock=lambda: now[0])
    first.put("key", b"synthetic source")
    second = SourceFileCache(directory, ttl_seconds=10, clock=lambda: now[0])
    assert second.get("key") == b"synthetic source"
    assert directory.stat().st_mode & 0o777 == 0o700
    assert (directory / "sources.sqlite3").stat().st_mode & 0o777 == 0o600
    now[0] = 110
    assert second.get("key") is None


def test_cache_evicts_oldest_files_at_byte_and_entry_limits(tmp_path):
    now = [1.0]
    cache = SourceFileCache(tmp_path / "cache", max_bytes=5, max_entries=2, clock=lambda: now[0])
    cache.put("first", b"aaa")
    now[0] += 1
    cache.put("second", b"bbb")
    assert cache.get("first") is None
    assert cache.get("second") == b"bbb"
    now[0] += 1
    cache.put("third", b"c")
    now[0] += 1
    cache.put("fourth", b"d")
    assert cache.get("second") is None
    assert cache.get("third") == b"c"
    assert cache.get("fourth") == b"d"
    cache.put("oversized", b"x" * 6)
    assert cache.get("oversized") is None


def test_corrupt_cache_content_is_not_served(tmp_path):
    cache = SourceFileCache(tmp_path / "cache")
    cache.put("key", b"synthetic")
    with sqlite3.connect(cache.directory / "sources.sqlite3") as db:
        db.execute("UPDATE source_files SET content = ?", (b"corrupt",))
    assert cache.get("key") is None


def test_unavailable_or_public_cache_falls_back_without_writing(tmp_path):
    directory = tmp_path / "public"
    directory.mkdir(mode=0o755)
    os.chmod(directory, 0o755)
    cache = SourceFileCache(directory)
    cache.put("key", b"synthetic")
    assert cache.get("key") is None
    assert not (directory / "sources.sqlite3").exists()
    blocked = tmp_path / "file"
    blocked.write_text("not a directory")
    cache = SourceFileCache(blocked)
    cache.put("key", b"synthetic")
    assert cache.get("key") is None


def test_cache_does_not_follow_database_symlinks(tmp_path):
    target = tmp_path / "unrelated"
    target.write_text("preserve me")
    directory = tmp_path / "cache"
    directory.mkdir(mode=0o700)
    (directory / "sources.sqlite3").symlink_to(target)
    cache = SourceFileCache(directory)
    cache.put("key", b"synthetic")
    assert cache.get("key") is None
    assert target.read_text() == "preserve me"
