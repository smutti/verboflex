"""Disposable built-worker driver; no production routes, tasks or provider writes."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import sys
import traceback
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

HEAD = "1" * 40
FORMATS = ("android_xml", "qt_ts", "json", "ios_strings", "separate")
REPLACEMENT = "P6 revised è"
DUPLICATE_PATH = "res/values-it/duplicate.xml"
DUPLICATE = b'<resources><string name="same">one</string><string name="same">two</string></resources>'
STAGE = "startup"


def fixture_files(name: str) -> dict[str, bytes]:
    """Independent input/golden corpus: all edits replace explicit old tokens."""
    if name == "android_xml":
        target = (
            b'<?xml version="1.0" encoding="utf-8"?>\r\n<resources>\r\n<!-- retained -->\r\n'
            b'<plurals name="count"><item quantity="one">P6 old one</item>'
            b'<item quantity="other">P6 old other</item></plurals>\r\n'
            b'<string-array name="items"><item>P6 old first</item><item>P6 old second</item></string-array>\r\n'
            b'<string name="keep">P6 keep</string>\r\n</resources>\r\n'
        )
        markup = (
            b'<resources><string name="markup">P6 old <b>bold</b></string></resources>'
        )
        return {
            "res/values-en/strings.xml": target.replace(b"P6 old", b"P6 base"),
            "res/values-it/strings.xml": target,
            "res/values-en/markup.xml": markup.replace(b"P6 old", b"P6 base"),
            "res/values-it/markup.xml": markup,
        }
    if name == "qt_ts":
        target = (
            b'<?xml version="1.0"?>\r\n<!DOCTYPE TS>\r\n<TS version="2.1" language="it" sourcelanguage="en">'
            b"<context><name>Smoke</name><comment>retained</comment>"
            b'<message id="count" numerus="yes"><source>Count</source><translation>'
            b'<numerusform variants="yes"><lengthvariant priority="1">P6 old short</lengthvariant>'
            b'<lengthvariant priority="2">P6 old long</lengthvariant></numerusform>'
            b'<numerusform variants="yes"><lengthvariant priority="1">P6 old plural</lengthvariant>'
            b'<lengthvariant priority="2">P6 old plurallong</lengthvariant></numerusform></translation></message>'
            b'<message id="scalar"><source>Scalar</source><translation>P6 old scalar</translation></message>'
            b'<message id="keep"><source>Keep</source><translation>P6 keep</translation></message>'
            b"</context></TS>\r\n"
        )
        return {
            "translations/app_it.ts": target,
            "translations/app_en.ts": target.replace(
                b'language="it"', b'language="en"'
            ).replace(b"P6 old", b"P6 base"),
        }
    if name == "json":
        target = b'{\r\n  "nested": {"title": "P6 old nested"},\r\n  "literal.dot": "P6 old literal",\r\n  "keep": "P6 keep"\r\n}\r\n'
        return {
            "locales/it.json": target,
            "locales/en.json": target.replace(b"P6 old", b"P6 base"),
        }
    if name == "ios_strings":
        target = '// retained 🌍\r\n"smoke" = "P6 old ios";\r\n"keep" = "P6 keep";\r\n'
        return {
            "it.lproj/Localizable.strings": b"\xff\xfe" + target.encode("utf-16-le"),
            "en.lproj/Localizable.strings": b"\xff\xfe"
            + target.replace("P6 old", "P6 base").encode("utf-16-le"),
        }
    if name in {"separate", "keys"}:
        language = "en" if name == "keys" else "it"
        content = b'<resources><!-- retained --><string name="separate">P6 old separate</string><string name="keep">P6 keep</string></resources>'
        files = {"res/values-en/strings.xml": content.replace(b"P6 old", b"P6 base")}
        if name == "separate":
            files[f"res/values-{language}/strings.xml"] = content
        return files
    raise ValueError("Unknown fixture")


def expected_bytes(original: bytes) -> bytes:
    codec, prefix = (
        ("utf-16-le", b"\xff\xfe")
        if original.startswith(b"\xff\xfe")
        else ("utf-8", b"")
    )
    text = original[len(prefix) :].decode(codec)
    # This oracle knows only fixture tokens, not writer/parser implementation.
    changed, count = re.subn(r"P6 old [a-z]+", REPLACEMENT, text)
    assert count > 0
    return prefix + changed.encode(codec)


def provider() -> None:
    import phase3_provider_base as base

    original = base.Handler.repository_read

    def read(self, workspace, slug, resource, query):
        if not resource and slug in base.state().get("heads", {}):
            name = f"{workspace}/{slug}"
            self.reply(
                200,
                {
                    "type": "repository",
                    "full_name": name,
                    "scm": "git",
                    "uuid": str(uuid5(NAMESPACE_URL, name)),
                },
            )
            return
        if resource[:1] != ["src"]:
            return original(self, workspace, slug, resource, query)
        if len(resource) < 2 or resource[1] != HEAD:
            self.reply(404, {"error": "unknown_commit"})
            return
        files = fixture_files(slug.removeprefix("phase6-"))
        path = "/".join(resource[2:]).strip("/")
        if "pagelen" in query:
            self.reply(
                200,
                {
                    "values": [
                        {"path": p, "size": len(b), "type": "commit_file"}
                        for p, b in files.items()
                    ]
                },
            )
            return
        content = DUPLICATE if path == DUPLICATE_PATH else files.get(path)
        if content is None:
            self.reply(404, {"error": "not_found"})
        elif query == {"format": ["meta"]}:
            base.record(
                category="resource",
                method="GET",
                resource_family="source-metadata",
                status=200,
            )
            self.reply(
                200,
                {
                    "type": "commit_file",
                    "path": path,
                    "commit": {"hash": HEAD},
                    "size": len(content),
                    "attributes": ["binary"] if content.startswith(b"\xff\xfe") else [],
                },
            )
        else:
            if base.state().get("tamper") == slug and b"P6 old" in content:
                content = content.replace(b"P6 old", b"P6 bad")
            self.reply(200, content, media_type="application/octet-stream")

    base.Handler.repository_read = read
    base.main()


def adapter():
    from verboflex.core.config import get_settings
    from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter
    from verboflex.services.bitbucket_oauth import (
        BitbucketOAuthService,
        BitbucketOAuthTokenExchange,
    )

    settings = get_settings()
    service = BitbucketOAuthService(
        settings=settings, token_exchange=BitbucketOAuthTokenExchange()
    )
    return BitbucketHttpAdapter(settings=settings, credential_leases=service), service


def seed_http_configuration() -> None:
    """Bootstrap only the first account; configure all five products through HTTP."""
    import time
    import httpx
    from sqlalchemy import func, select
    from verboflex.auth.passwords import hash_password
    from verboflex.db.session import SessionFactory
    from verboflex.models.product import Product
    from verboflex.models.role import Role
    from verboflex.models.user import User

    global STAGE
    assert os.environ.get("PHASE4_DISPOSABLE") == "1"
    actor_id = uuid4()
    email, password = f"phase8-{uuid4().hex}@example.com", f"Smoke {uuid4().hex}!"
    with SessionFactory.begin() as session:
        assert session.scalar(select(func.count()).select_from(Product)) == 0
        assert session.scalar(select(func.count()).select_from(User)) == 0
        session.add(
            User(
                id=actor_id,
                email=email,
                display_name="Smoke principal",
                hashed_password=hash_password(password),
                is_active=True,
                must_change_password=False,
                roles=[session.scalars(select(Role).where(Role.name == "admin")).one()],
            )
        )
    fixture = {
        "users": {"admin": {"email": email, "password": password}},
        "actor_id": str(actor_id),
        "mappings": [],
        "http_configuration": True,
    }
    with httpx.Client(base_url="http://backend:8000/api/v1", timeout=30) as client:

        def request(method, path, *, expected=200, body=None):
            response = client.request(method, path, json=body)
            if response.status_code != expected:
                raise ValueError(f"http-setup-status-{response.status_code}")
            return response.json()

        STAGE = "http-login"
        response = client.post(
            "/auth/token", data={"username": email, "password": password}
        )
        assert response.status_code == 200
        client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        STAGE = "http-connect"
        request("POST", "/admin/bitbucket/connect")
        for name in FORMATS:
            STAGE = "http-product-" + name
            product = request(
                "POST",
                "/admin/products",
                expected=201,
                body={"name": f"Smoke {name}", "description": "Disposable fixture"},
            )
            product_id = product["id"]
            revision = product["candidate_revision"]
            side_specs = (
                [("keys", "keys"), ("translations", name)]
                if name == "separate"
                else [("direct", name)]
            )
            sides = []
            for role, slug in side_specs:
                STAGE = "http-repository-" + name
                repository = request(
                    "POST",
                    "/admin/repositories",
                    expected=201,
                    body={
                        "workspace": "verboflex-smoke",
                        "repository_slug": f"phase6-{slug}",
                    },
                )
                sides.append(
                    {
                        "role": role,
                        "repository_id": repository["id"],
                        "source_branch": "main",
                    }
                )
            payload = {
                "topology": "separate" if name == "separate" else "direct",
                "expected_candidate_version": revision["version"],
                "allowed_target_branches": ["main"],
                "default_target_branch": "main",
            }
            if name == "separate":
                payload["sides"] = sides
            else:
                payload.update(
                    {
                        "repository_id": sides[0]["repository_id"],
                        "source_branch": "main",
                    }
                )
            STAGE = "http-mapping-" + name
            mapping = request(
                "POST",
                f"/admin/products/{product_id}/candidate/mappings",
                expected=201,
                body=payload,
            )
            STAGE = "http-preview-" + name
            job = request(
                "POST",
                f"/admin/products/{product_id}/candidate/mappings/{mapping['id']}/preview-jobs",
                expected=202,
                body={
                    "expected_candidate_version": mapping["candidate_version"],
                    "commits": [
                        {"role": side["role"], "commit_hash": HEAD} for side in sides
                    ],
                },
            )
            deadline = time.monotonic() + 120
            while job["state"] in {"queued", "running"}:
                assert time.monotonic() < deadline
                time.sleep(0.2)
                job = request("GET", f"/admin/preview-jobs/{job['id']}")
            assert job["state"] == "succeeded"
            candidates = [
                c
                for c in job["result"]["layout_candidates"]
                if c["repository_side"]
                == ("translations" if name == "separate" else "direct")
            ]
            assert len(candidates) == 1
            STAGE = "http-confirm-" + name
            confirmed = request(
                "POST",
                f"/admin/preview-jobs/{job['id']}/confirmation",
                body={
                    "preview_digest": job["result"]["digest"],
                    "layout_candidate_id": candidates[0]["id"],
                    "layout_candidate_version": 1,
                    "base_language": "en",
                },
            )
            assert confirmed["confirmed_by"] == str(actor_id)
            STAGE = "http-publish-" + name
            published = request(
                "POST",
                f"/admin/products/{product_id}/publish",
                body={
                    "candidate_revision_id": revision["id"],
                    "expected_candidate_version": mapping["candidate_version"],
                },
            )
            assert (
                published["is_active"]
                and published["active_revision"]["id"] == revision["id"]
            )
            fixture["mappings"].append(
                {
                    "name": name,
                    "format": "android_xml" if name == "separate" else name,
                    "product": product_id,
                    "revision": revision["id"],
                    "mapping": mapping["id"],
                    "sides": [s["role"] for s in sides],
                }
            )
    print(json.dumps(fixture))


def seed() -> None:
    if os.environ.get("PHASE8_HTTP_SETUP") == "1":
        seed_http_configuration()
        return
    from sqlalchemy import func, select
    from verboflex.auth.passwords import hash_password
    from verboflex.db.session import SessionFactory
    from verboflex.models.product import Product, ProductRevision
    from verboflex.models.product_mapping import (
        ProductMappingAllowedTarget,
        ProductMappingRepositorySide,
        ProductRepositoryMapping,
    )
    from verboflex.models.repository import Repository
    from verboflex.models.role import Role
    from verboflex.models.user import User
    from verboflex.services import preview_jobs
    from verboflex.services.publication import publish_product_candidate
    from verboflex.worker.preview_tasks import production_preview_processor

    global STAGE
    assert os.environ.get("PHASE4_DISPOSABLE") == "1"
    fixture = {"users": {}, "mappings": []}
    actor_id = uuid4()
    with SessionFactory.begin() as session:
        assert session.scalar(select(func.count()).select_from(Product)) == 0
        assert session.scalar(select(func.count()).select_from(User)) == 0
        password, email = f"Smoke {uuid4().hex}!", f"phase6-{uuid4().hex}@example.com"
        role = session.scalars(select(Role).where(Role.name == "admin")).one()
        session.add(
            User(
                id=actor_id,
                email=email,
                display_name="Smoke principal",
                hashed_password=hash_password(password),
                is_active=True,
                must_change_password=False,
                roles=[role],
            )
        )
        fixture["users"]["admin"] = {"email": email, "password": password}
        fixture["actor_id"] = str(actor_id)
        for name in FORMATS:
            product_id, revision_id, mapping_id = (uuid4() for _ in range(3))
            product = Product(
                id=product_id,
                display_name=f"Smoke {name}",
                name_key=f"smoke {name}",
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
            session.add(revision)
            session.flush()
            side_specs = (
                [("keys", "keys"), ("translations", name)]
                if name == "separate"
                else [("direct", name)]
            )
            sides = []
            for role_name, slug in side_specs:
                repo = Repository(
                    id=uuid4(),
                    workspace="verboflex-smoke",
                    repository_slug=f"phase6-{slug}",
                )
                session.add(repo)
                session.flush()
                sides.append(
                    ProductMappingRepositorySide(
                        role=role_name, repository_id=repo.id, source_branch="main"
                    )
                )
            mapping = ProductRepositoryMapping(
                id=mapping_id,
                revision_id=revision_id,
                topology="separate" if name == "separate" else "direct",
                identity_key=json.dumps(
                    [[s.role, str(s.repository_id), "main"] for s in sides],
                    separators=(",", ":"),
                ),
                base_language="en",
                sides=sides,
                allowed_targets=[
                    ProductMappingAllowedTarget(branch="main", is_default=True)
                ],
            )
            session.add(mapping)
            product.candidate_revision_id = revision_id
            fixture["mappings"].append(
                {
                    "name": name,
                    "format": "android_xml" if name == "separate" else name,
                    "product": str(product_id),
                    "revision": str(revision_id),
                    "mapping": str(mapping_id),
                    "sides": [s.role for s in sides],
                }
            )
    client, oauth = adapter()
    with SessionFactory() as session:
        oauth.acquire_client_credentials(session, actor_id=actor_id)
    asyncio.run(client.aclose())
    for item in fixture["mappings"]:
        STAGE = "preview-" + item["name"]
        with SessionFactory() as session:
            job = preview_jobs.create_or_reuse_preview_job(
                session,
                product_id=UUID(item["product"]),
                mapping_id=UUID(item["mapping"]),
                expected_candidate_version=1,
                commits={side: HEAD for side in item["sides"]},
                enqueuer=lambda _: None,
                actor_id=None,
            )
        preview_jobs.execute_preview_job(
            SessionFactory, job_id=job.id, processor=production_preview_processor
        )
        with SessionFactory() as session:
            completed = preview_jobs.get_preview_job(session, job_id=job.id)
            assert completed.state == "succeeded"
            candidates = [
                c
                for c in completed.result["layout_candidates"]
                if c["repository_side"]
                == ("translations" if item["name"] == "separate" else "direct")
            ]
            assert len(candidates) == 1
            preview_jobs.confirm_preview_job(
                session,
                job_id=job.id,
                preview_digest=completed.result["digest"],
                layout_candidate_id=UUID(candidates[0]["id"]),
                layout_candidate_version=1,
                base_language="en",
                actor_id=actor_id,
            )
        STAGE = "publish-" + item["name"]
        with SessionFactory() as session:
            publish_product_candidate(
                session,
                product_id=UUID(item["product"]),
                candidate_revision_id=UUID(item["revision"]),
                expected_candidate_version=1,
                actor_id=None,
            )
    print(json.dumps(fixture))


def queue_check() -> None:
    from redis import Redis
    from verboflex.core.config import get_settings

    expected = set(json.load(sys.stdin))
    assert len(expected) == 5
    found = set()
    with Redis.from_url(str(get_settings().redis_url)) as redis:
        for key in redis.scan_iter():
            if redis.type(key) != b"list":
                continue
            for raw in redis.lrange(key, 0, -1):
                message = json.loads(raw)
                assert message["headers"]["task"] == "verboflex.import.run"
                args, kwargs, _ = json.loads(base64.b64decode(message["body"]))
                assert len(args) == 1 and kwargs == {}
                identity = str(UUID(args[0]))
                assert identity in expected and identity not in found
                found.add(identity)
    assert found == expected


def authority_check() -> None:
    from sqlalchemy import select
    from verboflex.db.session import SessionFactory
    from verboflex.models.product import ProductRevision
    from verboflex.models.product_mapping import ProductRepositoryMapping
    from verboflex.services.preview_jobs import is_current_preview_confirmation

    with SessionFactory() as session:
        mappings = list(session.scalars(select(ProductRepositoryMapping)))
        assert len(mappings) == 5
        assert all(
            is_current_preview_confirmation(
                session, session.get_one(ProductRevision, m.revision_id), m
            )
            for m in mappings
        )


def database_digest() -> str:
    """Full localization/import/proposal tables, excluding normal OAuth lifecycle."""
    from sqlalchemy import text
    from verboflex.db.session import SessionFactory

    tables = (
        "localization_scopes",
        "translation_keys",
        "translation_values",
        "translation_value_revisions",
        "translation_value_locators",
        "translation_proposals",
        "translation_proposal_values",
        "translation_constraints",
        "staged_translation_values",
        "translation_parse_issues",
        "review_activities",
        "import_jobs",
        "import_executions",
        "import_source_references",
    )
    with SessionFactory() as session:
        rows = []
        for table in tables:
            rows.append(
                (
                    table,
                    sorted(
                        session.scalars(
                            text(f"SELECT row_to_json(t)::text FROM {table} t")
                        )
                    ),
                )
            )
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


async def verify_worker(mode: str, fixture: dict) -> dict:
    from sqlalchemy import select
    from verboflex.db.session import SessionFactory
    from verboflex.localization.writing.core import WritebackReason, WritebackRejected
    from verboflex.models.review import TranslationProposal
    from verboflex.models.translation import TranslationKey, TranslationValue
    from verboflex.services.writeback import (
        ProposalSelection,
        WritebackSelection,
        prepare_writeback,
        revalidate_writeback_authority,
    )

    global STAGE
    STAGE = "worker-" + mode
    before = database_digest()
    receipts = {
        UUID(group["id"]): group["version"]
        for mapping in fixture["mappings"]
        for group in mapping["groups"]
    }
    assert len(receipts) == 9
    with SessionFactory() as session:
        proposals = tuple(
            session.execute(
                select(TranslationProposal, TranslationKey.raw_key, TranslationValue.id)
                .join(
                    TranslationKey,
                    TranslationKey.id == TranslationProposal.translation_key_id,
                )
                .join(
                    TranslationValue,
                    TranslationValue.translation_key_id == TranslationKey.id,
                )
                .where(
                    TranslationValue.id.in_(receipts),
                    TranslationProposal.language == "it",
                )
            ).all()
        )
        assert len(proposals) == 9 and all(
            p.state == "approved" and p.version == receipts[group]
            for p, _, group in proposals
        )
        regular = tuple(
            ProposalSelection(p.id, p.version)
            for p, key, _ in proposals
            if key != "markup"
        )
        mixed = tuple(
            ProposalSelection(p.id, p.version)
            for p, key, _ in proposals
            if key == "markup"
        )
    assert len(regular) == 8 and len(mixed) == 1
    selection = WritebackSelection(
        UUID(fixture["actor_id"]), mixed if mode == "markup" else regular
    )
    client, _ = adapter()
    try:
        expected_reason = {
            "stale-direct": WritebackReason.SOURCE_BRANCH_CHANGED,
            "stale-keys": WritebackReason.SOURCE_BRANCH_CHANGED,
            "tamper": WritebackReason.SOURCE_FILE_CHANGED,
            "markup": WritebackReason.UNSUPPORTED_SHAPE,
        }.get(mode)
        if expected_reason:
            try:
                await prepare_writeback(
                    SessionFactory, selection=selection, adapter=client
                )
            except WritebackRejected as error:
                assert error.reason == expected_reason
                assert "P6" not in str(error) and "https" not in str(error)
            else:
                raise AssertionError("Expected writeback refusal")
            result = {mode: True}
        else:
            prepared = await prepare_writeback(
                SessionFactory, selection=selection, adapter=client
            )
            assert len(prepared.files) == 5
            by_repo = {
                s.repository_id: s.repository_slug
                for m in prepared.authority.mappings
                for s in m.sides
            }
            for file in prepared.files:
                original = fixture_files(
                    by_repo[file.authority.repository_id].removeprefix("phase6-")
                )[file.authority.path]
                assert file.original_bytes == original
                assert file.content == expected_bytes(original)
                assert file.before_sha256 == hashlib.sha256(original).hexdigest()
                assert file.after_sha256 == hashlib.sha256(file.content).hexdigest()
                assert file.changed_edits
            await revalidate_writeback_authority(
                SessionFactory, prepared=prepared, adapter=client
            )
            result = {
                "formats": 4,
                "approved_groups": 8,
                "prepared_files": 5,
                "revalidated": True,
            }
        assert database_digest() == before
        result["localization_unchanged"] = True
        return result
    finally:
        await client.aclose()


async def duplicate_snapshot() -> None:
    from verboflex.db.session import SessionFactory
    from verboflex.localization.importing.core import CanonicalParserInput
    from verboflex.localization.writing.core import (
        SourceFileAuthority,
        WritebackReason,
        WritebackRejected,
    )
    from verboflex.services.writeback_authority import build_source_file_snapshot

    client, _ = adapter()
    kwargs = {
        "workspace": "verboflex-smoke",
        "repository_slug": "phase6-android_xml",
        "commit_hash": HEAD,
        "path": DUPLICATE_PATH,
    }
    try:
        with SessionFactory() as session:
            metadata = await client.read_repository_source_metadata(session, **kwargs)
        with SessionFactory() as session:
            content = await client.read_repository_source_file(
                session, **kwargs, max_bytes=len(DUPLICATE)
            )
        assert content == DUPLICATE
        authority = SourceFileAuthority(
            uuid4(),
            0,
            uuid4(),
            "direct",
            "main",
            HEAD,
            DUPLICATE_PATH,
            len(content),
            hashlib.sha256(content).hexdigest(),
        )
        parser = CanonicalParserInput(
            format="android_xml",
            repository_side="direct",
            path=DUPLICATE_PATH,
            content=content,
            layout_identity="res",
            layout_version=1,
            base_language="en",
        )
        try:
            build_source_file_snapshot(authority, parser, metadata)
        except WritebackRejected as error:
            assert error.reason == WritebackReason.UNSUPPORTED_SHAPE
        else:
            raise AssertionError("Duplicate snapshot was accepted")
    finally:
        await client.aclose()


def audit(path: str) -> None:
    rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
    assert rows and all(
        set(r) == {"category", "method", "resource_family", "status"} for r in rows
    )
    oauth = [r for r in rows if r["category"] == "oauth-token-exchange"]
    resources = [r for r in rows if r["category"] == "resource"]
    assert len(oauth) + len(resources) == len(rows) and oauth and resources
    assert all(r["method"] == "POST" and r["status"] == 200 for r in oauth)
    assert all(r["method"] == "GET" and r["status"] == 200 for r in resources)
    assert {"source-read", "source-metadata", "branch-read"} <= {
        r["resource_family"] for r in resources
    }
    print("phase6 provider audit: PASS resource_mutations=0")


def redis_content() -> None:
    from redis import Redis
    from verboflex.core.config import get_settings

    forbidden = [
        b"P6 old",
        b"P6 base",
        REPLACEMENT.encode(),
        REPLACEMENT.encode("utf-16-le"),
    ]
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


def main() -> None:
    global STAGE
    mode = sys.argv[1] if len(sys.argv) > 1 else "provider"
    STAGE = mode
    if mode == "provider":
        provider()
    elif mode == "seed":
        seed()
    elif mode == "control":
        path, fault = Path(sys.argv[2]), sys.argv[3]
        state = {
            "faults": {},
            "heads": {f"phase6-{name}": HEAD for name in (*FORMATS, "keys")},
        }
        if fault in {"stale-direct", "stale-keys"}:
            state["heads"][
                "phase6-" + ("keys" if fault == "stale-keys" else "json")
            ] = "2" * 40
        if fault == "tamper":
            state["tamper"] = "phase6-json"
        temporary = path.with_suffix(".next")
        temporary.write_text(json.dumps(state))
        temporary.replace(path)
    elif mode == "queue":
        queue_check()
    elif mode == "authority":
        authority_check()
    elif mode == "audit":
        audit(sys.argv[2])
    elif mode == "redis-content":
        redis_content()
    elif mode == "duplicate":
        asyncio.run(duplicate_snapshot())
    elif mode in {"prepare", "stale-direct", "stale-keys", "tamper", "markup"}:
        print(json.dumps(asyncio.run(verify_worker(mode, json.load(sys.stdin)))))
    else:
        raise ValueError("Unknown smoke operation")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 - never emit provider/text payloads
        line = traceback.extract_tb(error.__traceback__)[-1].lineno
        print(
            f"phase6 driver failed: {STAGE}-{type(error).__name__}-line{line}",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
