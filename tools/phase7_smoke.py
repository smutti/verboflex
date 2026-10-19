"""Private disposable-stack driver and independent provider-effect oracle.

Only fixture setup, clock-expiry fault injection and read-only evidence use the
container helper. Imports, proposals, reviews, intake and recovery use public APIs.
No production route, source implementation or shared Compose project is changed.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from uuid import UUID, uuid4

import phase6_smoke as p6

ROOT = Path(__file__).resolve().parent.parent
STAGE = "startup"
LONG_KEY = "translation_" + "long_readable_key_" * 9
LONG_DIR = "context-" + "long-path-" * 12
LONG_BRANCH = "release/" + "long-target-" * 12
RTL_TEXT = "مرحبا بالعالم\nתרגום לבדיקה — testo multilinea è"


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(".next")
    descriptor = os.open(temporary, os.O_CREAT | os.O_RDWR | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def configure(path: Path, args: list[str]) -> None:
    project, envfile, override, backend, frontend = args
    assert project.startswith("verboflex_phase03_14_")
    fixture = json.loads(path.read_text())
    fixture.update(profile=7, backend=backend, frontend=frontend)
    fixture["compose"] = [
        "docker",
        "compose",
        "--project-name",
        project,
        "--env-file",
        envfile,
        "-f",
        str(ROOT / "docker-compose.yml"),
        "-f",
        override,
    ]
    fixture["evidence_dir"] = os.environ.get(
        "PHASE7_EVIDENCE_DIR",
        str(ROOT / ".planning/phases/07-change-sets-and-pull-requests/evidence"),
    )
    write_json(path, fixture)
    fixture["localization_digest"] = Harness(path).db("localization-digest")["digest"]
    write_json(path, fixture)


def seed_extra(spec: dict) -> dict:
    from sqlalchemy import select
    from verboflex.auth.passwords import hash_password
    from verboflex.db.session import SessionFactory
    from verboflex.models.product import Product, ProductRevision
    from verboflex.models.product_member import ProductMember
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

    assert os.environ.get("PHASE4_DISPOSABLE") == "1"
    actor_id = UUID(spec["actor_id"])
    viewer = {
        "email": f"phase7-viewer-{uuid4().hex}@example.com",
        "password": f"Smoke {uuid4().hex}!",
    }
    viewer_id = uuid4()
    with SessionFactory.begin() as session:
        session.add(
            User(
                id=viewer_id,
                email=viewer["email"],
                display_name="Smoke viewer",
                hashed_password=hash_password(viewer["password"]),
                is_active=True,
                must_change_password=False,
                roles=[
                    session.scalars(select(Role).where(Role.name == "viewer")).one()
                ],
            )
        )
    products = []
    for scenario in spec["scenarios"]:
        product_id, revision_id = uuid4(), uuid4()
        item = {"name": scenario["name"], "product": str(product_id), "mappings": []}
        with SessionFactory.begin() as session:
            product = Product(
                id=product_id,
                display_name="Smoke " + scenario["name"],
                name_key="smoke " + scenario["name"],
                is_active=True,
            )
            session.add(product)
            session.flush()
            session.add(ProductMember(product_id=product_id, user_id=viewer_id, role="viewer"))
            session.add(
                ProductRevision(
                    id=revision_id,
                    product_id=product_id,
                    display_name=product.display_name,
                    name_key=product.name_key,
                    description="Disposable fault fixture",
                    version=1,
                    is_published=False,
                )
            )
            session.flush()
            for mapping_spec in scenario["mappings"]:
                branch = mapping_spec.get("branch", "main")
                side_specs = mapping_spec.get("sides", {"direct": mapping_spec["slug"]})
                sides = []
                for role, slug in side_specs.items():
                    repo = session.scalar(
                        select(Repository).where(
                            Repository.workspace == "verboflex-smoke",
                            Repository.repository_slug == slug,
                        )
                    )
                    if repo is None:
                        repo = Repository(
                            id=uuid4(),
                            workspace="verboflex-smoke",
                            repository_slug=slug,
                        )
                        session.add(repo)
                        session.flush()
                    sides.append(
                        ProductMappingRepositorySide(
                            role=role,
                            repository_id=repo.id,
                            source_branch=branch,
                        )
                    )
                mapping_id = uuid4()
                session.add(
                    ProductRepositoryMapping(
                        id=mapping_id,
                        revision_id=revision_id,
                        topology="separate" if "keys" in side_specs else "direct",
                        identity_key=json.dumps(
                            [[s.role, str(s.repository_id), branch] for s in sides],
                            separators=(",", ":"),
                        ),
                        base_language="en",
                        sides=sides,
                        allowed_targets=[
                            ProductMappingAllowedTarget(
                                branch=target, is_default=target == branch
                            )
                            for target in mapping_spec.get("targets", [branch])
                        ],
                    )
                )
                item["mappings"].append(
                    {
                        "mapping": str(mapping_id),
                        "branch": branch,
                        "sides": list(side_specs),
                        "head": p6.HEAD if branch == "main" else "2" * 40,
                    }
                )
            product.candidate_revision_id = revision_id
        for mapping in item["mappings"]:
            with SessionFactory() as session:
                job = preview_jobs.create_or_reuse_preview_job(
                    session,
                    product_id=product_id,
                    mapping_id=UUID(mapping["mapping"]),
                    expected_candidate_version=1,
                    commits={side: mapping["head"] for side in mapping["sides"]},
                    enqueuer=lambda _: None,
                    actor_id=None,
                )
            preview_jobs.execute_preview_job(
                SessionFactory, job_id=job.id, processor=production_preview_processor
            )
            with SessionFactory() as session:
                ready = preview_jobs.get_preview_job(session, job_id=job.id)
                assert ready.state == "succeeded"
                candidates = [
                    c
                    for c in ready.result["layout_candidates"]
                    if c["repository_side"]
                    == ("translations" if "keys" in mapping["sides"] else "direct")
                ]
                assert len(candidates) == 1
                preview_jobs.confirm_preview_job(
                    session,
                    job_id=job.id,
                    preview_digest=ready.result["digest"],
                    layout_candidate_id=UUID(candidates[0]["id"]),
                    layout_candidate_version=1,
                    base_language="en",
                    actor_id=actor_id,
                )
        with SessionFactory() as session:
            publish_product_candidate(
                session,
                product_id=product_id,
                candidate_revision_id=revision_id,
                expected_candidate_version=1,
                actor_id=None,
            )
        products.append(item)
    return {"scenarios": products, "viewer": viewer}


def database_facts() -> dict:
    from verboflex.models.audit import AuditEntry
    from sqlalchemy import select
    from verboflex.db.session import SessionFactory
    from verboflex.models.submission import (
        ChangeSet,
        ChangeSetEvent,
        ChangeSetFile,
        ChangeSetItem,
        ChangeSetProof,
    )

    with SessionFactory() as session:
        groups = []
        for group in session.scalars(select(ChangeSet).order_by(ChangeSet.created_at)):
            files = []
            for file in session.scalars(
                select(ChangeSetFile).where(ChangeSetFile.change_set_id == group.id)
            ):
                files.append(
                    {
                        "path": file.path,
                        "before": base64.b64encode(file.original_bytes).decode(),
                        "after": base64.b64encode(file.content).decode(),
                        "attributes": file.attributes,
                        "active": file.active_claim,
                    }
                )
            events = [
                {
                    "kind": e.event_kind,
                    "step": e.step,
                    "outcome": e.outcome,
                    "attempt": e.attempt,
                    "fence": e.execution_fence,
                    "receipt": e.receipt,
                }
                for e in session.scalars(
                    select(ChangeSetEvent).where(
                        ChangeSetEvent.change_set_id == group.id
                    )
                )
            ]
            groups.append(
                {
                    "id": str(group.id),
                    "batch_id": str(group.batch_id),
                    "slug": group.repository_slug,
                    "provider_uuid": str(group.provider_repository_id),
                    "target": group.target_branch,
                    "target_head": group.target_head,
                    "branch": group.source_branch,
                    "commit": group.commit_hash,
                    "pr_id": group.pr_id,
                    "status": group.status,
                    "stage": group.stage,
                    "attempt": group.attempt,
                    "proof_sequence": group.current_proof_sequence,
                    "proofs": len(
                        list(
                            session.scalars(
                                select(ChangeSetProof.sequence).where(
                                    ChangeSetProof.change_set_id == group.id
                                )
                            )
                        )
                    ),
                    "items": [
                        {"proposal": str(i.proposal_id), "version": i.proposal_version}
                        for i in session.scalars(
                            select(ChangeSetItem).where(
                                ChangeSetItem.change_set_id == group.id
                            )
                        )
                    ],
                    "files": files,
                    "events": events,
                    "original_digest": hashlib.sha256(
                        group.original_prepared_payload
                    ).hexdigest(),
                    "expected_original_digest": group.original_proof_digest,
                }
            )
        audit_events = [
            {
                "action": e.action,
                "actor": str(e.actor_id),
                "entity": str(e.entity_id),
                "at": e.occurred_at.isoformat(),
            }
            for e in session.scalars(select(AuditEntry))
        ]
    return {"groups": groups, "audit_events": audit_events}


def queue_submissions(data: dict) -> dict:
    from redis import Redis
    from verboflex.core.config import get_settings

    expected = {str(UUID(value)) for value in data["ids"]}
    found = set()
    with Redis.from_url(str(get_settings().redis_url)) as client:
        for key in client.scan_iter():
            if client.type(key) != b"list":
                continue
            for raw in client.lrange(key, 0, -1):
                message = json.loads(raw)
                if message["headers"].get("task") != "verboflex.submission.run":
                    continue
                args, kwargs, _ = json.loads(base64.b64decode(message["body"]))
                assert len(args) == 1 and kwargs == {}
                identity = str(UUID(args[0]))
                assert identity in expected
                found.add(identity)
    assert found == expected
    return {"uuid_only": True, "groups": len(found)}


def inject_fault(mode: str, data: dict) -> dict:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select
    from verboflex.db.session import SessionFactory
    from verboflex.models.submission import ChangeSet

    assert os.environ.get("PHASE4_DISPOSABLE") == "1"
    if mode == "expire-owner":
        with SessionFactory.begin() as session:
            group = session.get_one(ChangeSet, UUID(data["id"]))
            assert group.status == "running" and group.owner_id is not None
            group.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        return {"expired": True}
    if mode == "expire-credential":
        from verboflex.models.bitbucket_connection import BitbucketConnection

        with SessionFactory.begin() as session:
            connection = session.scalars(select(BitbucketConnection)).one()
            connection.provider_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        return {"expired": True}
    if mode == "duplicate":
        from verboflex.worker.submission_tasks import run_submission

        run_submission.delay(str(UUID(data["id"])))
        return {"queued": True}
    raise ValueError("Unknown private injection")


class Harness:
    def __init__(self, path: Path):
        import httpx

        self.path = path
        self.fixture = json.loads(path.read_text())
        self.runtime = path.parent
        self.control_path = self.runtime / "provider-control.json"
        self.graph_path = self.runtime / "provider-graph.json"
        self.client = httpx.Client(
            base_url=self.fixture["backend"] + "/api/v1", timeout=30, trust_env=False
        )

    def login(self) -> None:
        user = self.fixture["users"]["admin"]
        for attempt in range(2):
            login = self.client.post(
                "/auth/token",
                data={"username": user["email"], "password": user["password"]},
            )
            if login.status_code == 429 and attempt == 0:
                delay = int(login.headers["Retry-After"])
                assert 1 <= delay <= 60
                time.sleep(delay)
                time.sleep(
                    1
                )  # Redis TTL is integral; allow its final fractional second.
                continue
            if login.status_code != 200:
                raise AssertionError(f"login_http_{login.status_code}")
            self.client.headers["Authorization"] = (
                "Bearer " + login.json()["access_token"]
            )
            return
        raise AssertionError("login_window")

    def api(
        self,
        path: str,
        method: str = "GET",
        body: object = None,
        *,
        expected: int | None = None,
    ) -> dict:
        if "Authorization" not in self.client.headers:
            self.login()
        response = self.client.request(
            method, path, **({"json": body} if body is not None else {})
        )
        if not (
            response.status_code == expected
            if expected is not None
            else response.is_success
        ):
            raise AssertionError(f"http_{response.status_code}")
        return response.json()

    def compose(self, *args: str, data: dict | None = None, timeout: int = 120) -> str:
        result = subprocess.run(
            [*self.fixture["compose"], *args],
            input=json.dumps(data) if data is not None else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode:
            # Raw command output can contain private fixture text or credentials.
            labels = re.findall(r"phase7 smoke failed: ([a-zA-Z0-9_-]+)", result.stderr)
            raise AssertionError(
                "helper_" + labels[-1] if labels else "owned_compose_failed"
            )
        return result.stdout

    def db(self, mode: str, data: dict | None = None) -> dict:
        return json.loads(
            self.compose(
                "exec",
                "-T",
                "-e",
                "PHASE4_DISPOSABLE=1",
                "backend",
                "python",
                "/tmp/phase7_smoke.py",
                mode,
                data=data or {},
            )
        )

    def control(self, **updates: object) -> None:
        current = json.loads(self.control_path.read_text())
        current.update(updates)
        write_json(self.control_path, current)

    def graph(self) -> dict:
        return json.loads(self.graph_path.read_text())

    def wait(self, callback, predicate, seconds: int = 100):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = callback()
            if predicate(value):
                return value
            time.sleep(0.25)
        raise AssertionError("bounded wait expired")

    def group(self, product: str, identity: str) -> dict:
        return self.api(f"/products/{product}/change-sets/{identity}")

    def settled(
        self, product: str, identity: str, statuses=("succeeded",), *, seconds=100
    ) -> dict:
        return self.wait(
            lambda: self.group(product, identity),
            lambda g: g["status"] in statuses,
            seconds=seconds,
        )

    def action(self, product: str, identity: str, action: str) -> dict:
        group = self.group(product, identity)
        return self.api(
            f"/products/{product}/change-sets/{identity}/{action}",
            "POST",
            {"expected_attempt": group["attempt"]},
        )

    def review(self, product: str) -> dict:
        candidates = self.api(f"/products/{product}/change-set-candidates")
        proposals = [
            {"proposal_id": c["proposal_id"], "expected_version": c["version"]}
            for c in candidates["items"]
            if c["can_review"] and not c["blocker"]
        ]
        assert proposals
        review = self.api(
            f"/products/{product}/submission-reviews",
            "POST",
            {"proposals": proposals, "targets": []},
        )
        return self.wait(
            lambda: self.api(f"/products/{product}/submission-reviews/{review['id']}"),
            lambda r: r["state"] not in ("queued", "running"),
        )

    def submit(self, product: str, review: dict) -> dict:
        assert review["state"] == "ready"
        body = {
            "review_id": review["id"],
            "expected_review_attempt": review["attempt"],
            "expected_content_digest": review["manifest_digest"],
            "request_key": str(uuid4()),
        }
        batch = self.api(f"/products/{product}/submission-batches", "POST", body)
        # Repeat the same accepted logical request over real HTTP: same IDs.
        assert (
            self.api(f"/products/{product}/submission-batches", "POST", body)["id"]
            == batch["id"]
        )
        return batch

    def prepare(self, scenario: dict, *, replacement: str = p6.REPLACEMENT) -> None:
        product = scenario["product"]
        for mapping in scenario["mappings"]:
            job = self.api(
                f"/admin/products/{product}/published/mappings/{mapping['mapping']}/imports",
                "POST",
            )
            result = self.wait(
                lambda job=job: self.api(
                    f"/admin/products/{product}/imports/{job['id']}"
                ),
                lambda j: j["state"] not in ("queued", "running"),
            )
            if result["state"] != "current":
                label = (
                    "import_"
                    + str(result["state"])
                    + "_"
                    + str(result.get("error_category"))
                )
                assert re.fullmatch(r"[a-zA-Z0-9_]{1,90}", label)
                raise AssertionError(label)
        groups = self.api(
            f"/translations?product_id={product}&language=it&page_size=50&q=P6%20old"
        )["items"]
        assert groups
        saved_count = 0
        for item in groups:
            detail = self.api(f"/translations/{item['id']}")
            if scenario["name"] == "split":
                branch = detail["values"][0]["provenance"]["branch"]
                if detail["raw_key"] != (
                    "title" if branch == "main" else "literal.dot"
                ):
                    continue
            pending = detail.get("pending_change")
            values = [
                {
                    "translation_value_id": v["id"],
                    "proposed_text": replacement,
                    "selector_version": v["selector_version"],
                    "selector_digest": v["selector_digest"],
                    "basis_revision_number": v["history"][0]["revision_number"],
                    "basis_digest": v["history"][0]["revision_digest"],
                }
                for v in detail["values"]
            ]
            saved = self.api(
                f"/translations/{item['id']}/proposal",
                "PUT",
                {
                    "expected_version": pending["version"] if pending else 0,
                    "values": values,
                },
            )
            self.api(
                f"/translations/{item['id']}/proposal/state",
                "POST",
                {"expected_version": saved["version"], "target_state": "approved"},
            )
            saved_count += 1
        assert saved_count == 2 if scenario["name"] == "split" else saved_count > 0

    def browser(self, scenario: dict) -> None:
        from phase6_gate import run_stage

        fixture = json.loads(self.path.read_text())
        fixture["scenario"] = scenario
        write_json(self.path, fixture)
        command = [
            "node",
            str(ROOT / "tools/phase7_smoke_browser.mjs"),
            "scenario",
            str(self.path),
            self.fixture["backend"],
            self.fixture["frontend"],
        ]
        with tempfile.TemporaryFile(mode="w+") as output:
            returncode = run_stage(command, cwd=ROOT, log=output, timeout=180, grace=30)
            output.seek(0)
            diagnostics = output.read()
        if returncode:
            labels = re.findall(r"phase7 smoke failed: ([a-zA-Z0-9_-]+)", diagnostics)
            raise AssertionError(
                "browser_" + labels[-1] if labels else "bounded_browser_failed"
            )


def validate_graph(graph: dict, facts: dict, *, happy_only: bool = False) -> dict:
    """Check exact persisted effects and bytes independently from worker status."""
    groups = [
        g for g in facts["groups"] if not happy_only or g["slug"].startswith("phase6-")
    ]
    assert groups
    totals = {"branch": 0, "commit": 0, "pull_request": 0}
    for group in groups:
        slug = group["slug"]
        if slug == "phase7-presentation":
            expected_path = f"locales/{LONG_DIR}/it.json"
            expected_before = (
                json.dumps(
                    {LONG_KEY: "P6 old presentation"}, ensure_ascii=False, indent=2
                ).encode()
                + b"\n"
            )
        else:
            if slug.startswith("phase6-"):
                fixture = slug.removeprefix("phase6-")
            elif slug == "phase7-source":
                fixture = "separate"
            else:
                assert slug in {
                    "phase7-enqueue",
                    "phase7-late",
                    "phase7-renew",
                    "phase7-split",
                    "phase7-partial-a",
                    "phase7-partial-b",
                    "phase7-drift",
                    "phase7-advance",
                }
                fixture = "json"
            expected_path = {
                "android_xml": "res/values-it/strings.xml",
                "qt_ts": "translations/app_it.ts",
                "json": "locales/it.json",
                "ios_strings": "it.lproj/Localizable.strings",
                "separate": "res/values-it/strings.xml",
            }[fixture]
            expected_before = p6.fixture_files(fixture)[expected_path]
        assert len(group["files"]) == 1
        assert group["files"][0]["path"] == expected_path
        assert base64.b64decode(group["files"][0]["before"]) == expected_before
        assert group["original_digest"] == group["expected_original_digest"]
        assert group["branch"] == "verboflex/change-set-" + group["id"]
        repository = graph["repositories"][group["slug"]]
        assert UUID(repository["uuid"].strip("{}")) == UUID(group["provider_uuid"])
        if group["status"] == "succeeded" or group["pr_id"] is not None:
            assert group["commit"] and group["pr_id"]
            # Exact graph structures are intentionally independent provider facts.
            commit = repository["commits"][group["commit"]]
            assert commit["parents"] == [group["target_head"]]
            parent_files = repository["commits"][group["target_head"]]["files"]
            expected_files = dict(parent_files)
            for file in group["files"]:
                before, after = (
                    base64.b64decode(file["before"]),
                    base64.b64decode(file["after"]),
                )
                assert base64.b64decode(commit["files"][file["path"]]) == after
                assert base64.b64decode(parent_files[file["path"]]) == before
                expected_files[file["path"]] = file["after"]
                assert file["attributes"] == (
                    ["binary"] if before.startswith(b"\xff\xfe") else []
                )
                if group["slug"] == "phase7-split":
                    old = (
                        b"P6 old nested"
                        if group["target"] == "main"
                        else b"P6 old literal"
                    )
                    assert after == before.replace(old, p6.REPLACEMENT.encode())
                elif group["slug"] != "phase7-presentation":
                    assert after == p6.expected_bytes(before)
                else:
                    assert json.loads(after) == {LONG_KEY: RTL_TEXT}
                    assert json.loads(before) == {LONG_KEY: "P6 old presentation"}
            assert commit["files"] == expected_files
            pr = repository["pull_requests"][str(group["pr_id"])]
            assert pr["source"]["branch"]["name"] == group["branch"]
            assert pr["source"]["commit"]["hash"] == group["commit"]
            assert pr["destination"]["branch"]["name"] == group["target"]
            assert pr["destination"]["commit"]["hash"] == group["target_head"]
            for side in ("source", "destination"):
                assert UUID(pr[side]["repository"]["uuid"].strip("{}")) == UUID(
                    group["provider_uuid"]
                )
            assert any(
                e["outcome"] == "verified" and e["step"] == "pull_request"
                for e in group["events"]
            )
    for slug, repo in graph["repositories"].items():
        if happy_only and not slug.startswith("phase6-"):
            continue
        for operation in totals:
            totals[operation] += repo["counters"][operation]["effects"]
            if happy_only:
                assert (
                    repo["counters"][operation]["attempts"]
                    == repo["counters"][operation]["effects"]
                )
        if slug.endswith("-keys"):
            assert all(repo["counters"][op]["attempts"] == 0 for op in totals)
    if happy_only:
        assert len(groups) == 5
        assert totals == {"branch": 5, "commit": 5, "pull_request": 5}
        assert sum(len(g["items"]) for g in groups) == 8
        assert sum(len(g["files"]) for g in groups) == 5
    return {
        "groups": len(groups),
        "effects": totals,
        "exact_bytes": True,
        "immutable_receipts": True,
    }


def run_faults(h: Harness) -> None:
    global STAGE
    STAGE = "fault-setup"
    h.compose("cp", str(ROOT / "tools/phase7_smoke.py"), "backend:/tmp/phase7_smoke.py")
    names = (
        "enqueue",
        "late",
        "renew",
        "split",
        "partial-a",
        "partial-b",
        "drift",
        "advance",
        "source",
        "source-keys",
    )
    repositories = {"phase7-" + name: {"fixture": "json"} for name in names}
    repositories["phase7-source"] = {"fixture": "separate"}
    repositories["phase7-source-keys"] = {"fixture": "keys"}
    presentation_files = {}
    for language in ("en", "it"):
        value = "P6 base presentation" if language == "en" else "P6 old presentation"
        content = (
            json.dumps({LONG_KEY: value}, ensure_ascii=False, indent=2).encode() + b"\n"
        )
        presentation_files[f"locales/{LONG_DIR}/{language}.json"] = base64.b64encode(
            content
        ).decode()
    repositories["phase7-presentation"] = {
        "fixture": "json",
        "files": presentation_files,
    }
    h.control(
        repositories=repositories,
        branches={"phase7-presentation": {LONG_BRANCH: "2" * 40}},
    )
    specs = [
        {"name": name, "mappings": [{"slug": "phase7-" + name}]}
        for name in ("enqueue", "late", "renew", "drift", "advance")
    ]
    specs += [
        {
            "name": "split",
            "mappings": [
                {"slug": "phase7-split"},
                {"slug": "phase7-split", "branch": "release"},
            ],
        },
        {
            "name": "partial",
            "mappings": [{"slug": "phase7-partial-a"}, {"slug": "phase7-partial-b"}],
        },
        {
            "name": "source",
            "mappings": [
                {
                    "slug": "phase7-source",
                    "sides": {
                        "keys": "phase7-source-keys",
                        "translations": "phase7-source",
                    },
                }
            ],
        },
        {
            "name": "presentation",
            "mappings": [
                {"slug": "phase7-presentation", "targets": ["main", LONG_BRANCH]}
            ],
        },
    ]
    seeded = h.db("seed-extra", {"actor_id": h.fixture["actor_id"], "scenarios": specs})
    scenarios = {s["name"]: s for s in seeded["scenarios"]}
    fixture = json.loads(h.path.read_text())
    fixture["users"]["viewer"] = seeded["viewer"]
    write_json(h.path, fixture)
    h.browser(
        {
            "name": "empty-workspace",
            "product": scenarios["presentation"]["product"],
            "action": "inspect-workspace",
            "expected_empty": True,
            "expected_history_empty": True,
            "visual": False,
        }
    )
    h.browser(
        {
            "name": "readonly-workspace",
            "product": scenarios["presentation"]["product"],
            "action": "inspect-workspace",
            "role": "viewer",
            "expected_read_only": True,
            "expected_empty": True,
            "expected_history_empty": True,
            "visual": False,
        }
    )
    for name, scenario in scenarios.items():
        STAGE = "prepare-" + name
        h.prepare(
            scenario, replacement=RTL_TEXT if name == "presentation" else p6.REPLACEMENT
        )
    evidence = {}

    def create(name):
        scenario = scenarios[name]
        review = h.review(scenario["product"])
        assert review["state"] == "ready"
        return scenario["product"], review

    def counters(slug):
        return h.graph()["repositories"][slug]["counters"]

    def fault(slug, operation, action):
        h.control(
            write_faults={
                slug: {
                    "operation": operation,
                    "action": action,
                    "token": str(uuid4()),
                    "seconds": 120,
                }
            }
        )

    def marker(slug, operation):
        p = h.runtime / ("provider-block-started." + slug + "." + operation)
        h.wait(lambda: p.exists(), bool, seconds=20)

    STAGE = "lost-enqueue"
    product, review = create("enqueue")
    h.compose("stop", "--timeout", "2", "redis")
    try:
        batch = h.submit(product, review)
        group = batch["groups"][0]
        assert h.group(product, group["id"])["status"] == "queued"
        assert counters("phase7-enqueue")["branch"]["effects"] == 0
    finally:
        h.compose("start", "redis")
    h.settled(product, group["id"])
    before = counters("phase7-enqueue")
    h.db("duplicate", {"id": group["id"]})
    time.sleep(1)
    assert counters("phase7-enqueue") == before
    evidence["lost_enqueue_same_id"] = evidence["duplicate_delivery_no_effect"] = True

    STAGE = "worker-kill-delayed-effect"
    product, review = create("late")
    fault("phase7-late", "commit", "block_before_apply")
    batch = h.submit(product, review)
    group = batch["groups"][0]
    marker("phase7-late", "commit")
    provider_container = h.compose("ps", "-q", "mock-bitbucket").strip()
    assert re.fullmatch(r"[0-9a-f]{64}", provider_container)

    def provider_started():
        return subprocess.check_output(
            [
                "docker",
                "inspect",
                "--format",
                "{{.State.StartedAt}}",
                provider_container,
            ],
            text=True,
            timeout=10,
        ).strip()

    original_provider_start = provider_started()
    h.compose("kill", "--signal", "SIGKILL", "worker")
    h.control(
        branches={
            "phase7-presentation": {LONG_BRANCH: "2" * 40},
            "phase7-late": {group["source_branch"]: None},
        }
    )
    h.db("expire-owner", {"id": group["id"]})
    h.compose("start", "worker")
    assert provider_started() == original_provider_start, "provider_restarted"
    h.wait(
        lambda: next(g for g in h.db("facts")["groups"] if g["id"] == group["id"]),
        lambda g: (
            g["status"] in {"reconciling", "needs_attention"}
            and any(
                e["kind"] == "observation"
                and e["step"] == "commit"
                and e["outcome"] == "unknown"
                for e in g["events"]
            )
        ),
        seconds=40,
    )
    recovered = h.group(product, group["id"])
    assert recovered["can_reconcile"] and not recovered["can_retry"]
    assert counters("phase7-late")["commit"] == {"attempts": 1, "effects": 0}
    STAGE = "late-original-apply"
    audit_start = len((h.runtime / "provider-audit.jsonl").read_text().splitlines())
    # Read-only reconciliation saw a missing branch; the original delayed send
    # can still arrive. Restore its original branch and release that same POST.
    h.control(
        branches={"phase7-presentation": {LONG_BRANCH: "2" * 40}}, write_faults={}
    )
    # The provider's absent-branch semantics applies its original parents CAS.
    try:
        h.wait(
            lambda: counters("phase7-late")["commit"]["effects"],
            lambda n: n == 1,
            seconds=30,
        )
    except AssertionError:
        rows = [
            json.loads(line)
            for line in (h.runtime / "provider-audit.jsonl")
            .read_text()
            .splitlines()[audit_start:]
        ]
        codes = [
            r["status"]
            for r in rows
            if r["method"] == "POST" and r["resource_family"] == "commit"
        ]
        progress = (
            h.graph().get("fault_progress", {}).get("phase7-late", {}).get("commit", {})
        )
        phase = progress.get("phase", "absent")
        assert phase in {
            "absent",
            "waiting_before_apply",
            "released_before_apply",
            "applied",
            "rejected",
        }
        raise AssertionError(
            f"late_{phase}_status_{progress.get('apply_status', codes[-1] if codes else 0)}"
        ) from None
    STAGE = "late-reconcile"
    h.action(product, group["id"], "reconcile")
    h.settled(product, group["id"], ("blocked",))
    STAGE = "late-explicit-retry"
    h.action(product, group["id"], "retry")
    h.settled(product, group["id"])
    assert counters("phase7-late")["commit"] == {"attempts": 1, "effects": 1}
    evidence["killed_worker_readonly_recovery"] = evidence[
        "missing_branch_no_resend"
    ] = evidence["delayed_original_effect_adopted"] = True

    STAGE = "split-targets"
    product, review = create("split")
    assert {g["target_branch"] for g in review["groups"]} == {"main", "release"}
    assert {g["target_head"] for g in review["groups"]} == {p6.HEAD, "2" * 40}
    h.compose("stop", "--timeout", "10", "worker")
    try:
        batch = h.submit(product, review)
        assert len(batch["groups"]) == 2
        assert h.db(
            "queue-submissions", {"ids": [g["id"] for g in batch["groups"]]}
        ) == {"uuid_only": True, "groups": 2}
    finally:
        h.compose("start", "worker")
    for group in batch["groups"]:
        h.settled(product, group["id"])
    assert counters("phase7-split")["commit"] == {"attempts": 2, "effects": 2}
    evidence["same_path_distinct_targets"] = True
    evidence["uuid_only_submission_queue"] = True

    STAGE = "partial-lost-pr-response"
    product, review = create("partial")
    fault("phase7-partial-b", "pull_request", "drop_after_apply")
    batch = h.submit(product, review)
    success = next(g for g in batch["groups"] if g["repository_slug"].endswith("-a"))
    unknown = next(g for g in batch["groups"] if g["repository_slug"].endswith("-b"))
    h.settled(product, success["id"])
    result = h.settled(product, unknown["id"], ("reconciling", "needs_attention"))
    assert result["can_reconcile"] and not result["can_retry"]
    before = counters("phase7-partial-a")
    h.browser(
        {
            "name": "partial-recovery",
            "product": product,
            "group_id": unknown["id"],
            "action": "reconcile",
            "wait": True,
            "expected_status": "succeeded",
            "expected_can_retry": False,
        }
    )
    h.settled(product, unknown["id"])
    assert counters("phase7-partial-a") == before
    assert counters("phase7-partial-b")["pull_request"] == {"attempts": 1, "effects": 1}
    h.control(write_faults={})
    evidence["partial_success_preserved"] = evidence["lost_pr_reply_one_effect"] = True

    STAGE = "source-target-drift"
    for name, slug in (("drift", "phase7-drift"), ("source", "phase7-source-keys")):
        product, review = create(name)
        original_control = json.loads(h.control_path.read_text())
        h.control(heads={**original_control["heads"], slug: "3" * 40})
        group = h.submit(product, review)["groups"][0]
        result = h.settled(product, group["id"], ("blocked", "failed"))
        assert all(c["effects"] == 0 for c in counters("phase7-" + name).values())
        h.control(heads={**original_control["heads"], slug: p6.HEAD})
        evidence[name + "_drift_refused"] = True
        if name == "source":
            h.browser(
                {
                    "name": "blocked-source",
                    "product": product,
                    "group_id": group["id"],
                    "action": "inspect",
                    "expected_status": result["status"],
                    "visual": False,
                }
            )
            h.browser(
                {
                    "name": "readonly-source",
                    "product": product,
                    "group_id": group["id"],
                    "action": "inspect",
                    "role": "viewer",
                    "expected_status": result["status"],
                    "expected_can_retry": False,
                    "expected_can_reconcile": False,
                    "visual": False,
                }
            )
            evidence["readonly_and_blocked_built_ui"] = True
        if name == "drift":
            assert result["can_finalize"]
            h.action(product, group["id"], "finalize")
            h.prepare(scenarios[name])
            fresh = h.submit(product, h.review(product))["groups"][0]
            assert fresh["id"] != group["id"]
            h.settled(product, fresh["id"])
            evidence["known_pre_pr_finalize_new_version"] = True

    STAGE = "external-generated-branch-advance"
    product, review = create("advance")
    fault("phase7-advance", "branch", "block_after_apply")
    group = h.submit(product, review)["groups"][0]
    marker("phase7-advance", "branch")
    h.control(
        branches={
            "phase7-presentation": {LONG_BRANCH: "2" * 40},
            "phase7-advance": {group["source_branch"]: "3" * 40},
        },
        write_faults={},
    )
    h.settled(product, group["id"], ("blocked", "failed", "needs_attention"))
    assert counters("phase7-advance")["branch"]["effects"] == 1
    assert counters("phase7-advance")["commit"]["effects"] == 0
    evidence["foreign_branch_never_reset"] = True

    STAGE = "terminal-pr-deleted-branch"
    facts = h.db("facts")
    states = {
        "phase6-android_xml": "MERGED",
        "phase6-qt_ts": "DECLINED",
        "phase6-json": "SUPERSEDED",
        "phase6-ios_strings": "OPEN",
    }
    pr_states, branches = {}, {"phase7-presentation": {LONG_BRANCH: "2" * 40}}
    for group in facts["groups"]:
        if group["slug"] not in states:
            continue
        slug = group["slug"]
        pr_states[slug] = {str(group["pr_id"]): states[slug]}
        branches[slug] = {group["branch"]: None}
    h.control(pr_states=pr_states, branches=branches)
    for mapping in h.fixture["mappings"]:
        slug = "phase6-" + mapping["name"]
        if slug not in states:
            continue
        group = next(g for g in facts["groups"] if g["slug"] == slug)
        h.action(mapping["product"], group["id"], "reconcile")
        result = h.settled(mapping["product"], group["id"], ("succeeded", "resolved"))
        assert result["pr_state"] == states[slug]
        assert result["status"] == (
            "succeeded" if states[slug] == "OPEN" else "resolved"
        )
    evidence["four_pr_states_without_source_branch"] = True

    STAGE = "presentation-browser"
    presentation = scenarios["presentation"]
    h.browser(
        {
            "name": "presentation",
            "product": presentation["product"],
            "action": "submit",
            "expected_status": "succeeded",
            "select_keys": [LONG_KEY],
            "targets": [
                {
                    "mapping_id": presentation["mappings"][0]["mapping"],
                    "target_branch": LONG_BRANCH,
                }
            ],
        }
    )
    history = h.api(f"/products/{presentation['product']}/change-sets")["items"]
    assert len(history) == 1
    h.settled(presentation["product"], history[0]["id"])
    assert history[0]["target_head"] == "2" * 40
    assert history[0]["sources"][0]["commit_hash"] == p6.HEAD
    evidence["long_rtl_multiline_built_browser"] = True
    evidence["different_target_head_same_selected_bytes"] = True
    # Renewal rotates the organization-wide credential. Existing published
    # import confirmations intentionally require active revalidation afterward,
    # so run this independent write-proof scenario after all fresh imports.
    STAGE = "credential-renewal"
    product, review = create("renew")
    fault("phase7-renew", "commit", "block_after_apply")
    group = h.submit(product, review)["groups"][0]
    marker("phase7-renew", "commit")
    h.db("expire-credential")
    h.control(write_faults={})
    result = h.settled(
        product, group["id"], ("blocked", "failed", "reconciling", "needs_attention")
    )
    if result["can_reconcile"]:
        h.action(product, group["id"], "reconcile")
        result = h.settled(product, group["id"], ("blocked",))
    assert result["can_retry"]
    original = next(g for g in h.db("facts")["groups"] if g["id"] == group["id"])
    h.action(product, group["id"], "retry")
    h.settled(product, group["id"])
    renewed = next(g for g in h.db("facts")["groups"] if g["id"] == group["id"])
    assert (
        renewed["original_digest"] == original["original_digest"]
        and renewed["files"] == original["files"]
    )
    assert renewed["proofs"] == 2 and renewed["proof_sequence"] == 2
    assert counters("phase7-renew")["commit"] == {"attempts": 1, "effects": 1}
    assert counters("phase7-renew")["pull_request"] == {"attempts": 1, "effects": 1}
    evidence["renewed_credentials_same_frozen_commit"] = True

    STAGE = "fault-independent-oracle"
    result = validate_graph(h.graph(), h.db("facts"))
    assert result["effects"] == {"branch": 15, "commit": 14, "pull_request": 14}
    assert result["groups"] == 17
    for slug, repo in h.graph()["repositories"].items():
        count = (
            2
            if slug == "phase7-split"
            else 0
            if slug.endswith("-keys") or slug == "phase7-source"
            else 1
        )
        expected = {
            op: {"attempts": count, "effects": count}
            for op in ("branch", "commit", "pull_request")
        }
        if slug == "phase7-advance":
            expected["commit"] = expected["pull_request"] = {
                "attempts": 0,
                "effects": 0,
            }
        assert repo["counters"] == expected
    evidence.update(result)
    write_json(h.runtime / "fault-evidence.json", evidence)


def audit(h: Harness) -> None:
    rows = [
        json.loads(line)
        for line in (h.runtime / "provider-audit.jsonl").read_text().splitlines()
    ]
    assert rows and all(
        set(r) == {"category", "method", "resource_family", "status"} for r in rows
    )
    assert all(
        r["method"] in {"GET", "POST"} and isinstance(r["status"], int) for r in rows
    )
    graph, facts = h.graph(), h.db("facts")
    validate_graph(graph, facts)
    if h.fixture.get("http_configuration"):
        assert len({mapping["comment_id"] for mapping in h.fixture["mappings"]}) == 5
        browser_proof = json.loads(
            (Path(h.fixture["evidence_dir"]) / "phase7-browser-verify.json").read_text()
        )
        assert browser_proof["revoked_session"] == {
            "http_status": 401,
            "editor_removed": True,
            "dirty_overlay_removed": True,
            "proposal_unchanged": True,
        }
        for mapping in h.fixture["mappings"]:
            for action, entity in [
                ("product.created", mapping["product"]),
                ("product.published", mapping["product"]),
                ("mapping.created", mapping["mapping"]),
            ]:
                matches = [
                    row
                    for row in facts["audit_events"]
                    if row["action"] == action and row["entity"] == entity
                ]
                assert (
                    len(matches) == 1 and matches[0]["actor"] == h.fixture["actor_id"]
                )
                assert matches[0]["at"]
        evidence = h.runtime / "fault-evidence.json"
        result = json.loads(evidence.read_text())
        result["http_configuration_and_audit"] = {
            "products": 5,
            "actor_verified": True,
            "comments": 5,
            "revoked_session_save_denied": True,
        }
        write_json(evidence, result)
    oauth = [r for r in rows if r["category"] == "oauth-token-exchange"]
    resources = [r for r in rows if r["category"] == "resource"]
    assert oauth and resources and len(oauth) + len(resources) == len(rows)
    assert all(r["method"] == "POST" and r["status"] == 200 for r in oauth)
    for operation in ("branch", "commit", "pull_request"):
        observed = sum(
            r["method"] == "POST" and r["resource_family"] == operation
            for r in resources
        )
        expected = sum(
            repo["counters"][operation]["attempts"]
            for repo in graph["repositories"].values()
        )
        assert observed == expected and expected > 0



def branch_workflow_smoke(h: Harness) -> None:
    """Real API, worker and TLS provider: commits first, PR only from the browser."""
    slug = "phase7-approval-branch"
    control = json.loads(h.control_path.read_text())
    repositories = dict(control.get("repositories", {}))
    repositories[slug] = {"fixture": "json"}
    branches = dict(control.get("branches", {}))
    branches[slug] = {"feature/verboflex": "2" * 40, "master": p6.HEAD}
    h.control(repositories=repositories, branches=branches, write_faults={})
    seeded = h.db("seed-extra", {"actor_id": h.fixture["actor_id"], "scenarios": [
        {"name": "approval-branch", "mappings": [{"slug": slug, "branch": "feature/verboflex"}]}
    ]})
    scenario = seeded["scenarios"][0]
    # The control is an external-force override on every read; seed once, then
    # allow ordinary commits to advance the persistent fixture branch.
    branches.pop(slug)
    h.control(branches=branches)
    product = scenario["product"]
    h.browser({"name": "approval-branch-config", "action": "configure-branches", "product": product,
        "mapping": scenario["mappings"][0]["mapping"], "work_branch": "feature/verboflex", "target_branch": "master"})
    h.compose("up", "-d", "scheduler")
    h.prepare(scenario, replacement="First approved translation")
    endpoint = f"/products/{product}/branch-workflow"
    first = h.wait(lambda: h.api(endpoint), lambda d: d["items"] and (any(i["state"] == "blocked" for i in d["items"]) or all(
        item["state"] == "committed" for item in d["items"])), seconds=120)
    assert all(i["state"] == "committed" for i in first["items"]), first
    assert h.graph()["repositories"][slug]["counters"]["pull_request"]["effects"] == 0
    group = h.api(f"/translations?product_id={product}&language=it&page_size=50&q=P6%20old")["items"][0]
    # Reimport the approval from the same branch used for review and commits.
    refreshed = h.api(f"/admin/products/{product}/published/mappings/{scenario['mappings'][0]['mapping']}/imports", "POST")
    refreshed = h.wait(lambda: h.api(f"/admin/products/{product}/imports/{refreshed['id']}"),
        lambda j: j["state"] not in ("queued", "running"), seconds=120)
    assert refreshed["state"] == "current", refreshed
    detail = h.api(f"/translations/{group['id']}")
    assert detail["pending_change"]["state"] == "approved"
    assert not detail["pending_change"]["reconciliation_required"]
    assert not detail["pending_change"]["target_integrated"]
    assert all(v["translated_text"] == "First approved translation" for v in detail["values"])
    saved = h.api(f"/translations/{group['id']}/proposal", "PUT", {
        "expected_version": detail["pending_change"]["version"],
        "values": [{"translation_value_id": v["id"], "proposed_text": "Second approved translation",
            "selector_version": v["selector_version"], "selector_digest": v["selector_digest"],
            "basis_revision_number": v["history"][0]["revision_number"],
            "basis_digest": v["history"][0]["revision_digest"]} for v in detail["values"]],
    })
    approval_url = f"/translations/{group['id']}/proposal/state"
    approval_payload = {"expected_version": saved["version"], "target_state": "approved"}
    h.api(approval_url, "POST", approval_payload)
    # A lost response or double-click must not enqueue another commit.
    h.api(approval_url, "POST", approval_payload, expected=409)
    second = h.wait(lambda: h.api(endpoint), lambda d: d["items"][0]["state"] in ("committed", "blocked"), seconds=120)
    assert second["items"][0]["state"] == "committed", second
    assert len(second["items"]) == len(first["items"]) + 1
    assert second["items"][0]["commit_hash"] not in {i["commit_hash"] for i in first["items"]}
    assert h.graph()["repositories"][slug]["counters"]["pull_request"]["effects"] == 0
    h.browser({"name": "translation-awaiting", "action": "translation-status", "product": product,
        "group": group["id"], "status": "approved"})
    h.browser({"name": "approval-branch", "action": "branch-workflow", "product": product})
    published = h.wait(lambda: h.api(endpoint), lambda d: d["items"][0]["state"] in ("open", "blocked"), seconds=120)
    assert published["items"][0]["state"] == "open", published
    effects = h.graph()["repositories"][slug]["counters"]
    assert effects["pull_request"]["effects"] == 1
    assert effects["commit"]["effects"] == len(second["items"])
    # Simulate target integration at the provider boundary, then let the real
    # scheduler/worker verify the approved values. PR status alone is not used.
    target_head = second["items"][0]["commit_hash"]
    control = json.loads(h.control_path.read_text())
    h.control(branches={**control.get("branches", {}), slug: {"master": target_head}})
    h.wait(lambda: h.api(f"/translations/{group['id']}"),
        lambda d: d["pending_change"]["target_integrated"], seconds=150)
    h.browser({"name": "translation-integrated", "action": "translation-status", "product": product,
        "group": group["id"], "status": "integrated"})
    detail = h.api(f"/translations/{group['id']}")
    h.api(f"/translations/{group['id']}/proposal", "PUT", {
        "expected_version": detail["pending_change"]["version"],
        "values": [{"translation_value_id": v["id"], "proposed_text": "Next pending translation",
            "selector_version": v["selector_version"], "selector_digest": v["selector_digest"],
            "basis_revision_number": v["history"][0]["revision_number"],
            "basis_digest": v["history"][0]["revision_digest"]} for v in detail["values"]],
    })
    h.browser({"name": "translation-pending", "action": "translation-status", "product": product,
        "group": group["id"], "status": "pending"})
    assert h.graph()["repositories"][slug]["counters"] == effects
    write_json(h.runtime / "branch-workflow-evidence.json", {
        "commits": len(second["items"]), "pull_requests": 1,
        "approval_snapshots": True, "sequential_commits": True, "explicit_pr": True,
        "browser_configuration": True, "duplicate_approval_rejected": True,
        "target_badge_lifecycle": True, "integration_does_not_publish": True,
        "working_branch": "feature/verboflex", "target": "master",
        "imports_working_branch": True, "reimport_preserves_approval": True,
    })
    destination = Path(h.fixture["evidence_dir"])
    destination.mkdir(parents=True, exist_ok=True)
    write_json(destination / "branch-workflow-evidence.json", json.loads((h.runtime / "branch-workflow-evidence.json").read_text()))

def main() -> None:
    global STAGE
    STAGE = sys.argv[1]
    if STAGE == "configure":
        configure(Path(sys.argv[2]), sys.argv[3:])
    elif STAGE == "seed-extra":
        print(json.dumps(seed_extra(json.load(sys.stdin))))
    elif STAGE == "facts":
        print(json.dumps(database_facts()))
    elif STAGE == "localization-digest":
        print(json.dumps({"digest": p6.database_digest()}))
    elif STAGE == "queue-submissions":
        print(json.dumps(queue_submissions(json.load(sys.stdin))))
    elif STAGE in {"expire-owner", "expire-credential", "duplicate"}:
        print(json.dumps(inject_fault(STAGE, json.load(sys.stdin))))
    elif STAGE == "happy-oracle":
        harness = Harness(Path(sys.argv[2]))
        result = validate_graph(harness.graph(), harness.db("facts"), happy_only=True)
        assert (
            harness.db("localization-digest")["digest"]
            == harness.fixture["localization_digest"]
        )
        result["localization_unchanged"] = True
        write_json(harness.runtime / "happy-evidence.json", result)
    elif STAGE == "branch-workflow":
        harness = Harness(Path(sys.argv[2]))
        branch_workflow_smoke(harness)
        from shared_moko_smoke import run

        run(harness)
    elif STAGE == "faults":
        run_faults(Harness(Path(sys.argv[2])))
    elif STAGE == "audit":
        audit(Harness(Path(sys.argv[2])))
    elif STAGE == "evidence":
        runtime = Path(sys.argv[2]).parent
        print(
            json.dumps(
                {
                    "happy": json.loads((runtime / "happy-evidence.json").read_text()),
                    "faults": json.loads((runtime / "fault-evidence.json").read_text()),
                    "cleanup": True,
                }
            )
        )
    else:
        raise ValueError("Unknown operation")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 - private logs never print payloads
        line = traceback.extract_tb(error.__traceback__)[-1].lineno
        label = (
            str(error)
            if re.fullmatch(r"[a-zA-Z0-9_-]{1,180}", str(error))
            else "assertion"
        )
        print(
            f"phase7 smoke failed: {STAGE}-{type(error).__name__}-line{line}-{label}",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
