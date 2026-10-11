"""Private PostgreSQL backups; every published bundle has passed a full restore."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

BUNDLE = re.compile(r"vf-\d{8}T\d{6}Z-[a-f0-9]{8}")
TARGET = re.compile(r"vf_restore_[a-z0-9_]{1,40}")


class BackupError(Exception):
    """Only fixed, non-sensitive reason codes may reach logs."""


def now():
    return datetime.now(timezone.utc)


def timestamp(value=None):
    return (value or now()).isoformat()


def root():
    path = Path(os.environ.get("BACKUP_DIRECTORY", "/backups"))
    if path.is_symlink():
        raise BackupError("invalid_backup_directory")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def integer(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, str(default)))
        if not minimum <= value <= maximum:
            raise ValueError
        return value
    except ValueError:
        raise BackupError("invalid_configuration") from None


def connection_database():
    value = os.environ.get("PGDATABASE", "verboflex")
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,62}", value):
        raise BackupError("invalid_source_database")
    return value


def command(args, *, database=None):
    env = os.environ.copy()
    env["PGDATABASE"] = database or connection_database()
    env["PGCONNECT_TIMEOUT"] = "10"
    # Password is inherited via environment, never interpolated into argv or logs.
    try:
        result = subprocess.run(
            args,
            env=env,
            capture_output=True,
            check=False,
            timeout=integer("BACKUP_COMMAND_TIMEOUT_SECONDS", 1800, 10, 7200),
        )
    except subprocess.TimeoutExpired:
        raise BackupError("database_command_timeout") from None
    except OSError:
        raise BackupError("database_command_unavailable") from None
    if result.returncode:
        raise BackupError("database_command_failed")
    return result.stdout.decode("utf-8")


def sql(query, database):
    return command(
        ["psql", "-X", "-w", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", query],
        database=database,
    ).strip()


def inventory(database):
    names = json.loads(
        sql(
            "SELECT coalesce(json_agg(tablename ORDER BY tablename), '[]') "
            "FROM pg_tables WHERE schemaname = 'public'",
            database,
        )
    )
    if "alembic_version" not in names:
        raise BackupError("missing_application_schema")
    # Names are database identifiers, quoted independently of SQL literals.
    counts = {}
    for name in names:
        identifier = '"' + name.replace('"', '""') + '"'
        counts[name] = int(sql(f"SELECT count(*) FROM public.{identifier}", database))
    revisions = sql(
        "SELECT version_num FROM public.alembic_version ORDER BY version_num", database
    )
    if not revisions:
        raise BackupError("missing_schema_revision")
    return {"schema_revisions": revisions.splitlines(), "row_counts": counts}


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return {"sha256": hasher.hexdigest(), "bytes": path.stat().st_size}


def atomic_json(path, data):
    temporary = path.with_name(f".{path.name}-{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(data, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def operation_lock(directory):
    with (directory / ".operation.lock").open("a") as stream:
        os.chmod(stream.name, 0o600)
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BackupError("operation_already_running") from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def metadata(path, *, checksums=False):
    if not BUNDLE.fullmatch(path.name) or path.is_symlink() or not path.is_dir():
        raise BackupError("invalid_bundle")
    try:
        manifest = path / "manifest.json"
        if manifest.is_symlink() or manifest.stat().st_size > 1_048_576:
            raise ValueError
        data = json.loads(manifest.read_text())
        if (
            data["format_version"] != 1
            or data["id"] != path.name
            or data["verified"] is not True
        ):
            raise ValueError
        created = datetime.fromisoformat(data["created_at"])
        if created.tzinfo is None:
            raise ValueError
        if not isinstance(data["files"], dict) or set(data["files"]) != {
            "database.dump",
            "deployment.env",
        }:
            raise ValueError
        for filename, expected in data["files"].items():
            if not isinstance(expected, dict) or not re.fullmatch(
                r"[a-f0-9]{64}", str(expected.get("sha256", ""))
            ):
                raise ValueError
            file = path / filename
            if (
                file.is_symlink()
                or not file.is_file()
                or file.stat().st_size != expected["bytes"]
            ):
                raise ValueError
            if checksums and digest(file) != expected:
                raise ValueError
        if not isinstance(data["inventory"]["row_counts"], dict):
            raise TypeError
        return data
    except (OSError, ValueError, TypeError, KeyError):
        raise BackupError("invalid_or_corrupt_bundle") from None


def bundles(directory):
    found = []
    for path in directory.iterdir():
        if not BUNDLE.fullmatch(path.name):
            continue
        try:
            found.append(metadata(path))
        except BackupError:
            # Unknown, incomplete and damaged entries are never retention targets.
            continue
    return sorted(found, key=lambda entry: (entry["created_at"], entry["id"]))


def prune(directory, keep):
    if keep < 1:
        raise BackupError("invalid_retention")
    for data in bundles(directory)[:-keep]:
        path = directory / data["id"]
        metadata(path, checksums=True)
        # Never remove extra files placed by an operator in a bundle directory.
        if {file.name for file in path.iterdir()} != {
            "manifest.json",
            "database.dump",
            "deployment.env",
        }:
            continue
        for name in ("database.dump", "deployment.env", "manifest.json"):
            (path / name).unlink()
        path.rmdir()


def restore_archive(archive, database, *, expected=None, disposable=False):
    if not TARGET.fullmatch(database) or database == connection_database():
        raise BackupError("invalid_restore_target")
    created = False
    try:
        # createdb fails if the target already exists. No --clean, DROP or overwrite path.
        command(
            [
                "createdb",
                "-w",
                "--maintenance-db=postgres",
                "--template=template0",
                database,
            ]
        )
        created = True
        command(
            [
                "pg_restore",
                "-w",
                "--exit-on-error",
                "--single-transaction",
                "--no-owner",
                "--no-privileges",
                "--dbname",
                database,
                str(archive),
            ],
            database=database,
        )
        result = inventory(database)
        if expected is not None and result != expected:
            raise BackupError("restore_inventory_mismatch")
        return result
    finally:
        if created and disposable:
            # Only the random database just created by this invocation can be removed.
            command(["dropdb", "-w", "--maintenance-db=postgres", database])


def verified_restore(path, database=None):
    data = metadata(path, checksums=True)
    return restore_archive(
        path / "database.dump",
        database or "vf_restore_" + uuid4().hex,
        expected=data["inventory"],
        disposable=database is None,
    )


def backup(directory):
    keep = integer("BACKUP_KEEP_COUNT", 14, 1, 365)
    source = Path(os.environ.get("BACKUP_CONFIG_FILE", "/run/backup/deployment.env"))
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 1_048_576:
        raise BackupError("deployment_config_unavailable")
    content = source.read_text()
    required = {
        "VERBOFLEX_POSTGRES_PASSWORD",
        "VERBOFLEX_JWT_SECRET_KEY",
        "VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING",
    }
    configured = {
        line.split("=", 1)[0].strip()
        for line in content.splitlines()
        if "=" in line and line.split("=", 1)[1].strip().strip("\"'")
    }
    if not required <= configured:
        raise BackupError("deployment_config_incomplete")
    identifier = "vf-" + now().strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    pending = directory / (".partial-" + identifier)
    pending.mkdir(mode=0o700)
    try:
        shutil.copyfile(source, pending / "deployment.env")
        (pending / "deployment.env").chmod(0o600)
        archive = pending / "database.dump"
        command(
            [
                "pg_dump",
                "-w",
                "--format=custom",
                "--compress=6",
                "--lock-wait-timeout=30s",
                "--file",
                str(archive),
            ]
        )
        archive.chmod(0o600)
        # Rehearsal validates all data, indexes, FK/check constraints and schema, not just the TOC.
        restored = restore_archive(
            archive, "vf_restore_" + uuid4().hex, disposable=True
        )
        if digest(source) != digest(pending / "deployment.env"):
            raise BackupError("deployment_config_changed_during_backup")
        data = {
            "format_version": 1,
            "id": identifier,
            "created_at": timestamp(),
            "source_database": connection_database(),
            "verified": True,
            "files": {
                name: digest(pending / name)
                for name in ("database.dump", "deployment.env")
            },
            "inventory": restored,
        }
        for filename in data["files"]:
            with (pending / filename).open("rb") as stream:
                os.fsync(stream.fileno())
        atomic_json(pending / "manifest.json", data)
        # Persist all file entries before publishing, then the parent entry before pruning.
        descriptor = os.open(pending, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        pending.rename(directory / identifier)
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        prune(directory, keep)
        return data
    finally:
        # Only our unfinished bundle. SIGKILL leftovers remain visibly .partial and are ignored.
        if pending.exists():
            shutil.rmtree(pending)


def run_backup(directory):
    with operation_lock(directory):
        try:
            data = backup(directory)
        except Exception as exc:  # noqa: BLE001 — operator boundary must redact unexpected errors
            reason = (
                str(exc) if isinstance(exc, BackupError) else "backup_internal_error"
            )
            atomic_json(
                directory / "status.json",
                {"last_attempt": timestamp(), "ok": False, "reason": reason},
            )
            raise BackupError(reason) from None
        atomic_json(
            directory / "status.json",
            {"last_attempt": timestamp(), "ok": True, "id": data["id"]},
        )
        return data


def due(entries, moment, hour):
    scheduled = moment.replace(hour=hour, minute=0, second=0, microsecond=0)
    if moment < scheduled:
        scheduled -= timedelta(days=1)
    return not entries or datetime.fromisoformat(entries[-1]["created_at"]) < scheduled


def health(directory):
    try:
        status = json.loads((directory / "status.json").read_text())
        entries = bundles(directory)
        if not status["ok"] or not entries:
            return False
        age = now() - datetime.fromisoformat(entries[-1]["created_at"])
        return timedelta(0) <= age <= timedelta(hours=36)
    except (OSError, ValueError, TypeError, KeyError):
        return False


def serve(directory):
    hour = integer("BACKUP_HOUR_UTC", 3, 0, 23)
    retry_at = 0.0
    print(
        json.dumps({"event": "backup_scheduler_started", "hour_utc": hour}), flush=True
    )
    while True:
        if time.monotonic() >= retry_at and (
            due(bundles(directory), now(), hour) or not health(directory)
        ):
            try:
                result = run_backup(directory)
                print(
                    json.dumps({"event": "backup_verified", "id": result["id"]}),
                    flush=True,
                )
            except BackupError as exc:
                print(
                    json.dumps({"event": "backup_failed", "reason": str(exc)}),
                    flush=True,
                )
            retry_at = time.monotonic() + 900
        time.sleep(30)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "serve", "list", "health"):
        commands.add_parser(name)
    for name in ("verify", "restore"):
        sub = commands.add_parser(name)
        sub.add_argument("bundle", help="Exact vf-... directory name, from list")
        if name == "restore":
            sub.add_argument(
                "--database",
                required=True,
                help="NEW vf_restore_... database; never overwritten",
            )
    args = parser.parse_args()
    try:
        directory = root()
        if args.command == "health":
            return 0 if health(directory) else 1
        if args.command == "serve":
            serve(directory)
        elif args.command == "run":
            print(json.dumps(run_backup(directory), indent=2))
        elif args.command == "list":
            print(json.dumps(bundles(directory), indent=2))
        else:
            if not BUNDLE.fullmatch(args.bundle):
                raise BackupError("invalid_bundle")
            with operation_lock(directory):
                result = verified_restore(
                    directory / args.bundle, getattr(args, "database", None)
                )
            print(
                json.dumps(
                    {
                        "verified": True,
                        "database": getattr(args, "database", None),
                        "inventory": result,
                    },
                    indent=2,
                )
            )
        return 0
    except (BackupError, OSError) as exc:
        print(
            json.dumps(
                {
                    "error": str(exc)
                    if isinstance(exc, BackupError)
                    else "filesystem_error"
                }
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
