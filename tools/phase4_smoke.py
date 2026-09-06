"""Isolated Phase 4 smoke fixture setup, TLS provider and queue assertions.

Runs only inside the disposable runner's containers. Never emits fixture content.
"""

from __future__ import annotations

import base64
import json
import os
import signal
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

FORMATS = ("android_xml", "qt_ts", "json", "ios_strings")


def bounded() -> None:
    """Bound external operations and reap the process group on timeout/signals."""
    child = subprocess.Popen(sys.argv[2:], start_new_session=True)

    def stop(_signum=None, _frame=None):
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        raise SystemExit(124)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        raise SystemExit(child.wait(timeout=600))
    except subprocess.TimeoutExpired:
        stop()


def fixture_files(format_name: str) -> dict[str, bytes]:
    if format_name == "android_xml":
        return {
            "res/values/strings.xml": b'<resources><string name="smoke">Smoke source</string></resources>',
            "res/values-it/strings.xml": b'<resources><string name="smoke">Smoke target</string></resources>',
        }
    if format_name == "qt_ts":
        return {
            "translations/app_it.ts": b'<TS version="2.1" language="it" sourcelanguage="en"><context><name>Smoke</name><message><source>Smoke source</source><translation>Smoke target</translation></message></context></TS>',
            "translations/app_en.ts": b'<TS version="2.1" language="en" sourcelanguage="en"><context><name>Smoke</name><message><source>Smoke source</source><translation>Smoke source</translation></message></context></TS>',
        }
    if format_name == "json":
        return {
            "locales/en.json": b'{"smoke":"Smoke source"}',
            "locales/it.json": b'{"smoke":"Smoke target"}',
        }
    if format_name == "ios_strings":
        return {
            "en.lproj/Localizable.strings": b'"smoke" = "Smoke source";',
            "it.lproj/Localizable.strings": b'"smoke" = "Smoke target";',
        }
    raise ValueError("Unknown fixture format")


def provider() -> None:
    import phase3_provider_base as base

    original = base.Handler.repository_read

    def read(self, workspace, slug, resource, query):
        if resource[:1] != ["src"]:
            return original(self, workspace, slug, resource, query)
        files = fixture_files(slug.removeprefix("phase4-"))
        path = "/".join(resource[2:]).strip("/")
        if "pagelen" in query:
            self.reply(
                200,
                {
                    "values": [
                        {"path": name, "size": len(content), "type": "commit_file"}
                        for name, content in files.items()
                    ]
                },
            )
        elif path in files:
            self.reply(200, files[path], media_type="application/octet-stream")
        else:
            self.reply(404, {"error": "not_found"})

    base.Handler.repository_read = read
    base.main()


def seed() -> None:
    from sqlalchemy import func, select
    from verboflex.auth.passwords import hash_password
    from verboflex.db.session import SessionFactory
    from verboflex.localization.preview.core import build_layout_candidate
    from verboflex.models.bitbucket_connection import BitbucketConnection
    from verboflex.models.preview_job import PreviewJob
    from verboflex.models.product import Product, ProductRevision
    from verboflex.models.product_mapping import (
        ProductMappingAllowedTarget,
        ProductMappingRepositorySide,
        ProductRepositoryMapping,
    )
    from verboflex.models.repository import Repository
    from verboflex.models.role import Role
    from verboflex.models.user import User
    from verboflex.services.preview_jobs import (
        PREVIEW_DETECTOR_VERSION,
        PREVIEW_LAYOUT_IDENTITY,
        _canonical_identity,
        _closed_result,
        _complete_preview_digest,
        _complete_sides,
        _identity,
    )

    assert os.environ.get("PHASE4_DISPOSABLE") == "1"
    fixture = {"users": {}, "mappings": []}
    admin_id = None
    with SessionFactory.begin() as session:
        assert session.scalar(select(func.count()).select_from(Product)) == 0
        assert session.scalar(select(func.count()).select_from(User)) == 0
        for role_name in ("admin", "product_manager_reviewer", "translator", "viewer"):
            role = session.scalar(select(Role).where(Role.name == role_name))
            assert role is not None
            password = f"Smoke {uuid4().hex}!"
            email = f"phase4-{uuid4().hex}@example.com"
            user_id = uuid4()
            if role_name == "admin":
                admin_id = user_id
            session.add(
                User(
                    id=user_id,
                    email=email,
                    display_name="Smoke principal",
                    hashed_password=hash_password(password),
                    is_active=True,
                    must_change_password=False,
                    roles=[role],
                )
            )
            fixture["users"][role_name] = {"email": email, "password": password}
        for format_name in FORMATS:
            product_id, revision_id, repo_id, mapping_id = (uuid4() for _ in range(4))
            product = Product(
                id=product_id,
                display_name=f"Smoke {format_name}",
                name_key=f"smoke {format_name}",
                is_active=True,
            )
            session.add(product)
            session.flush()
            revision = ProductRevision(
                id=revision_id,
                product_id=product_id,
                display_name=product.display_name,
                name_key=product.name_key,
                description="Disposable fixture",
                version=1,
                is_published=False,
            )
            session.add_all(
                [
                    revision,
                    Repository(
                        id=repo_id,
                        workspace="verboflex-smoke",
                        repository_slug=f"phase4-{format_name}",
                    ),
                ]
            )
            session.flush()
            mapping = ProductRepositoryMapping(
                id=mapping_id,
                revision_id=revision_id,
                topology="direct",
                identity_key=json.dumps(
                    ["direct", str(repo_id), "main"], separators=(",", ":")
                ),
                base_language="en",
                sides=[
                    ProductMappingRepositorySide(
                        role="direct", repository_id=repo_id, source_branch="main"
                    )
                ],
                allowed_targets=[
                    ProductMappingAllowedTarget(branch="main", is_default=True)
                ],
            )
            session.add(mapping)
            session.flush()
            connection = session.get_one(BitbucketConnection, 1)
            assert connection.access_token_ciphertext is None
            generation = (
                connection.generation + 1
            )  # The subsequent real Connect API call.
            sides = _complete_sides(mapping, {"direct": "1" * 40})
            _, digest = _canonical_identity(
                product_id=product_id,
                revision=revision,
                mapping=mapping,
                connection_generation=generation,
                repository_sides=sides,
            )
            now = datetime.now(UTC)
            job = PreviewJob(
                id=uuid4(),
                revision_scope="candidate",
                input_digest=digest,
                attempt=1,
                state="succeeded",
                product_id=product_id,
                candidate_revision_id=revision_id,
                candidate_revision_version=1,
                mapping_id=mapping_id,
                topology="direct",
                connection_generation=generation,
                detector_version=PREVIEW_DETECTOR_VERSION,
                layout_identity=PREVIEW_LAYOUT_IDENTITY,
                repository_sides=sides,
                result={},
                started_at=now,
                finished_at=now,
            )
            layout = {
                "android_xml": "res",
                "qt_ts": "qt-ts:translations/app_{locale}.ts",
                "json": "json:flat-per-locale:locales/{locale}.json",
                "ios_strings": "ios-strings:{locale}.lproj/Localizable.strings",
            }[format_name]
            candidate = build_layout_candidate(
                repository_side="direct",
                format=format_name,
                layout_identity=layout,
                files=tuple(fixture_files(format_name)),
                values={
                    "en": {"smoke": "Smoke source"},
                    "it": {"smoke": "Smoke target"},
                },
            ).to_mapping()
            job.result = _closed_result(
                _identity(job),
                {
                    "detector_version": PREVIEW_DETECTOR_VERSION,
                    "digest": digest,
                    "layout_candidates": [candidate],
                },
            )
            session.add(job)
            mapping.selected_layout_candidate_id = UUID(str(candidate["id"]))
            mapping.selected_layout_version = 1
            mapping.confirmed_preview_job_id = job.id
            mapping.confirmed_preview_digest = _complete_preview_digest(
                _identity(job), [candidate], base_language="en"
            )
            mapping.preview_confirmed_by = admin_id
            mapping.preview_confirmed_at = now
            session.flush()
            revision.is_published = True
            revision.published_at = datetime.now(UTC)
            session.flush()
            product.active_revision_id = revision_id
            fixture["mappings"].append(
                {
                    "format": format_name,
                    "product": str(product_id),
                    "mapping": str(mapping_id),
                }
            )
    # Captured directly into an owner-only file by the caller, never to the terminal.
    print(json.dumps(fixture))


def queue_check() -> None:
    from redis import Redis
    from verboflex.core.config import get_settings

    expected = set(json.load(sys.stdin))
    assert len(expected) == 4
    found = set()
    with Redis.from_url(str(get_settings().redis_url)) as redis:
        for key in redis.scan_iter():
            if redis.type(key) != b"list":
                continue
            for raw in redis.lrange(key, 0, -1):
                message = json.loads(raw)
                assert message["headers"]["task"] == "verboflex.import.run"
                args, kwargs, _embedded = json.loads(base64.b64decode(message["body"]))
                assert len(args) == 1 and kwargs == {}
                identity = str(UUID(args[0]))
                assert identity in expected and identity not in found
                found.add(identity)
    assert found == expected
    print("phase4 queued UUID-only jobs: PASS (count=4)")


def authority_check() -> None:
    from sqlalchemy import select
    from verboflex.db.session import SessionFactory
    from verboflex.models.product import ProductRevision
    from verboflex.models.product_mapping import ProductRepositoryMapping
    from verboflex.services.preview_jobs import is_current_preview_confirmation

    with SessionFactory() as session:
        mappings = list(session.scalars(select(ProductRepositoryMapping)))
        assert len(mappings) == 4
        assert all(
            is_current_preview_confirmation(
                session, session.get_one(ProductRevision, mapping.revision_id), mapping
            )
            for mapping in mappings
        )
    print("phase4 current preview authority: PASS (count=4)")


def redis_content_check() -> None:
    from redis import Redis
    from verboflex.core.config import get_settings

    forbidden = [b"Smoke target", b"Smoke source"]
    forbidden.extend(
        content for name in FORMATS for content in fixture_files(name).values()
    )
    with Redis.from_url(str(get_settings().redis_url)) as client:
        for key in client.scan_iter():
            kind = client.type(key)
            values = [key]
            if kind == b"string":
                values.append(client.get(key))
            elif kind == b"list":
                values.extend(client.lrange(key, 0, -1))
            elif kind == b"set":
                values.extend(client.smembers(key))
            elif kind == b"zset":
                values.extend(client.zrange(key, 0, -1))
            elif kind == b"hash":
                pairs = client.hgetall(key)
                values.extend([*pairs, *pairs.values()])
            assert all(
                not value or all(needle not in value for needle in forbidden)
                for value in values
            )
    print("phase4 Redis content boundary: PASS")


def audit(path: str) -> None:
    rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
    assert rows and all(
        set(row) == {"category", "method", "resource_family", "status"} for row in rows
    )
    oauth = [row for row in rows if row["category"] == "oauth-token-exchange"]
    assert all(row["category"] in {"oauth-token-exchange", "resource"} for row in rows)
    resources = [row for row in rows if row["category"] == "resource"]
    assert oauth and all(
        row["method"] == "POST" and row["status"] == 200 for row in oauth
    )
    assert resources and all(
        row["method"] == "GET"
        and row["status"] == 200
        and row["resource_family"]
        in {"repository-metadata", "branch-read", "source-read"}
        for row in resources
    )
    assert {"source-read", "branch-read"} <= {
        row["resource_family"] for row in resources
    }
    print(f"phase4 provider audit: PASS (resource_reads={len(resources)}, mutations=0)")


if __name__ == "__main__":
    try:
        mode = sys.argv[1] if len(sys.argv) > 1 else "provider"
        if mode == "bounded":
            bounded()
        elif mode == "provider":
            provider()
        elif mode == "seed":
            seed()
        elif mode == "queue":
            queue_check()
        elif mode == "authority":
            authority_check()
        elif mode == "redis-content":
            redis_content_check()
        elif mode == "audit":
            audit(sys.argv[2])
        else:
            raise ValueError("Unknown mode")
    except Exception:  # noqa: BLE001 - never expose provider or fixture details.
        print("phase4 smoke helper: bounded failure", file=sys.stderr)
        raise SystemExit(1) from None
