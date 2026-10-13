"""Owned, disposable built-app dashboard smoke. No provider or shared-stack access."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "backend/.pytest_cache/dashboard-smoke"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class OwnedRuntime:
    def __init__(self):
        self.project = "dashboard-smoke-" + uuid4().hex[:12]
        self.path = Path(tempfile.mkdtemp(prefix=self.project + "-"))
        self.database = self.project.replace("-", "_")
        self.backend_port, self.frontend_port = free_port(), free_port()
        # Production nginx permits localhost API origins; bindings stay loopback-only.
        self.backend = f"http://localhost:{self.backend_port}"
        self.frontend = f"http://localhost:{self.frontend_port}"
        (self.path / "owner").write_text(self.project)
        self.compose_file = self.path / "compose.json"
        self.stage = "setup"

    def validate(self):
        if (
            not re.fullmatch(r"dashboard-smoke-[0-9a-f]{12}", self.project)
            or not self.path.name.startswith(self.project + "-")
            or self.path.parent.resolve() != Path(tempfile.gettempdir()).resolve()
            or (self.path / "owner").read_text() != self.project
            or self.database != self.project.replace("-", "_")
        ):
            raise RuntimeError("Unowned dashboard runtime")

    def command(self, *args: str, timeout: int = 240, env=None, cwd=ROOT) -> str:
        self.validate()
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
        (self.path / "last-command.log").write_text(result.stdout + result.stderr)
        if result.returncode:
            for diagnostic in re.findall(
                r"^dashboard (?:browser failed|failure type): [a-zA-Z0-9_-]+$",
                result.stderr,
                re.MULTILINE,
            ):
                print(diagnostic, flush=True)
            for diagnostic in re.findall(
                r"^dashboard HTTP: /[a-zA-Z0-9/_-]+ [0-9]+$",
                result.stdout,
                re.MULTILINE,
            ):
                print(diagnostic, flush=True)
            raise RuntimeError(f"Dashboard smoke failed: {self.stage}")
        return result.stdout

    def compose(self, *args: str, timeout: int = 240) -> str:
        return self.command(
            "docker",
            "compose",
            "--env-file",
            os.devnull,
            "--project-name",
            self.project,
            "--file",
            str(self.compose_file),
            *args,
            timeout=timeout,
        )

    def configure(self):
        self.validate()
        # Only the syntax frontend directive is omitted, as in the existing smoke.
        for name in ("backend", "frontend"):
            source = (ROOT / "docker" / f"{name}.Dockerfile").read_text()
            assert source.startswith("# syntax=docker/dockerfile:1.8\n")
            (self.path / f"{name}.Dockerfile").write_text(source.split("\n", 1)[1])
        environment = {
            "VERBOFLEX_APP_ENV": "local",
            "VERBOFLEX_DATABASE_URL": f"postgresql+psycopg://postgres@postgres:5432/{self.database}",
            "VERBOFLEX_REDIS_URL": "redis://redis:6379/0",
            "VERBOFLEX_JWT_SECRET_KEY": secrets.token_urlsafe(48),
            "VERBOFLEX_CORS_ORIGINS": json.dumps([self.frontend]),
        }
        services = {
            "postgres": {
                "image": "postgres:18-alpine",
                "environment": {
                    "POSTGRES_DB": self.database,
                    "POSTGRES_HOST_AUTH_METHOD": "trust",
                },
                "ports": ["127.0.0.1::5432"],
                "volumes": ["database:/var/lib/postgresql"],
                "healthcheck": {
                    "test": ["CMD", "pg_isready", "-U", "postgres"],
                    "interval": "2s",
                    "retries": 30,
                },
            },
            "redis": {
                "image": "redis:7-alpine",
                "healthcheck": {
                    "test": ["CMD", "redis-cli", "ping"],
                    "interval": "2s",
                    "retries": 30,
                },
            },
            "backend": {
                "build": {
                    "context": str(ROOT),
                    "dockerfile": str(self.path / "backend.Dockerfile"),
                    "target": "runtime",
                },
                "image": self.project + "-backend",
                "environment": environment,
                "ports": [f"127.0.0.1:{self.backend_port}:8000"],
            },
            "frontend": {
                "build": {
                    "context": str(ROOT),
                    "dockerfile": str(self.path / "frontend.Dockerfile"),
                    "target": "runtime",
                    "args": {"VITE_API_BASE_URL": self.backend},
                },
                "image": self.project + "-frontend",
                # nginx resolves its API upstream at startup, so the backend
                # must already be running on the owned Compose network.
                "depends_on": {"backend": {"condition": "service_healthy"}},
                "ports": [f"127.0.0.1:{self.frontend_port}:80"],
            },
        }
        self.compose_file.write_text(
            json.dumps(
                {
                    "services": services,
                    "volumes": {"database": {}},
                    "networks": {"default": {"name": self.project + "_default"}},
                }
            )
        )
        self.compose_file.chmod(0o600)

    def postgres_url(self) -> str:
        self.validate()
        container = self.compose("ps", "-q", "postgres").strip()
        label = self.command(
            "docker",
            "inspect",
            "--format",
            '{{index .Config.Labels "com.docker.compose.project"}}',
            container,
        ).strip()
        if label != self.project:
            raise RuntimeError("Unowned database container")
        address = self.compose("port", "postgres", "5432").strip()
        if not re.fullmatch(r"127\.0\.0\.1:[0-9]+", address):
            raise RuntimeError("Unowned database address")
        return f"postgresql+psycopg://postgres@{address}/{self.database}"

    def cleanup(self):
        self.validate()
        if self.compose_file.exists():
            self.compose("down", "--volumes", "--remove-orphans", timeout=120)
            for suffix in ("backend", "frontend"):
                tag = self.project + "-" + suffix
                # An interrupted build may never have produced this exact image.
                found = self.command("docker", "images", "-q", tag).strip()
                if found:
                    self.command("docker", "image", "rm", tag)
            remaining = self.command(
                "docker",
                "ps",
                "-aq",
                "--filter",
                "label=com.docker.compose.project=" + self.project,
            ).strip()
            volumes = self.command(
                "docker",
                "volume",
                "ls",
                "-q",
                "--filter",
                "label=com.docker.compose.project=" + self.project,
            ).strip()
            if remaining or volumes:
                raise RuntimeError("Owned runtime cleanup incomplete")
        shutil.rmtree(self.path)


def seed(
    runtime: OwnedRuntime,
    *,
    full: bool = False,
    product_summary: bool = False,
    bilingual: bool = False,
    multilingual: bool = False,
) -> dict:
    runtime.validate()
    url = runtime.postgres_url()
    sys.path.insert(0, str(ROOT / "backend"))
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from verboflex.auth.passwords import hash_password
    from verboflex.models.import_job import ImportExecution, ImportJob
    from verboflex.models.product import Product
    from verboflex.models.product_member import ProductMember
    from verboflex.models.role import Role
    from verboflex.models.translation import TranslationKey
    from verboflex.models.user import User

    support = importlib.import_module("tests.api.test_translation_reviews")
    engine = create_engine(url)
    factory = sessionmaker(engine, expire_on_commit=False)
    fixture = {"users": {}}
    try:
        with factory.begin() as session:
            for role, name in (
                ("translator", "Mira Translator"),
                ("product_manager_reviewer", "Alex Reviewer"),
                ("admin", "Jordan Admin"),
                ("viewer", "Sam Viewer"),
            ):
                password = secrets.token_urlsafe(24)
                user = User(
                    id=uuid4(),
                    email=f"{role}@dashboard.example",
                    display_name=name,
                    hashed_password=hash_password(password),
                    is_active=True,
                    must_change_password=False,
                    roles=[session.scalar(select(Role).where(Role.name == role))],
                )
                session.add(user)
                fixture["users"][role] = {
                    "id": str(user.id),
                    "email": user.email,
                    "password": password,
                    "name": name,
                }
        ids = support._seed_scalar_basis(factory, name="Mobile workspace")
        fixture["product"] = str(ids["product"])
        fixture["group"] = str(ids["group"])
        fixture["proposal"] = support._payload(ids, "Welcome from the dashboard")
        if multilingual or bilingual:
            fixture.update(seed_multilingual(factory))
        if product_summary:
            summary_support = importlib.import_module("tests.api.test_product_summary")
            summary_ids = summary_support.seed_two_keys(factory, name="Atlas Mobile")
            empty_ids = support.SUPPORT._seed_constraint_group(
                factory, name="New product", complete_dataset=False
            )
            with factory.begin() as session:
                for key_id in (summary_ids["key"], summary_ids["second"]):
                    summary_support.add_value(
                        session, summary_ids, key_id, "en", translated="Ready"
                    )
            fixture["summary_product"] = str(summary_ids["product"])
            fixture["summary_group"] = str(summary_ids["group"])
            fixture["empty_product"] = str(empty_ids["product"])
        if full:
            hidden = support._seed_scalar_basis(
                factory, name="Inactive product", active=False
            )
            unactivated = support.SUPPORT._seed_constraint_group(
                factory, name="Unactivated import", complete_dataset=False
            )
            failed = support.SUPPORT._seed_constraint_group(
                factory, name="Failed import", complete_dataset=False
            )
            with factory.begin() as session:
                failed_id = uuid4()
                now = datetime.now(UTC)
                session.add(
                    ImportExecution(
                        id=failed_id,
                        import_job_id=failed["import"],
                        sequence=2,
                        state="failed",
                        connection_generation=1,
                        started_at=now,
                        finished_at=now,
                    )
                )
                session.flush()
                job = session.get_one(ImportJob, failed["import"])
                job.current_execution_id = failed_id
                job.state = "import_failed"
                job.error_category = "source_unavailable"
                job.error_message = "Synthetic import failure"
                session.get_one(TranslationKey, ids["key"]).raw_key = (
                    "notifications.preferences." + "multilingual_welcome_message_" * 6
                )
            dashboard_support = importlib.import_module("tests.api.test_dashboard")
            change_set = dashboard_support.seed_submission(
                factory,
                ids,
                UUID(fixture["users"]["admin"]["id"]),
                datetime.now(UTC) - timedelta(hours=3),
            )
            fixture["change_set"] = str(change_set)
            fixture["excluded_products"] = [
                str(row["product"]) for row in (hidden, unactivated, failed)
            ]
        # Global operational labels no longer grant product access. These actors
        # exercise only this disposable database's synthetic products.
        with factory.begin() as session:
            for product_id in session.scalars(select(Product.id)):
                for role, user in fixture["users"].items():
                    if role != "admin":
                        session.merge(
                            ProductMember(
                                product_id=product_id,
                                user_id=UUID(user["id"]),
                                role=role,
                            )
                        )
        return fixture
    finally:
        engine.dispose()


def seed_multilingual(factory) -> dict:
    """Exact canonical siblings and real provenance, only in the owned database."""
    import hashlib

    from verboflex.models.translation import TranslationValue, TranslationValueLocator

    workspace = importlib.import_module("tests.api.test_translation_workspace")
    work = workspace.WORK
    product, _, ids = workspace.seed_keys(factory)
    with factory.begin() as session:
        for (index, language), value_id in ids.items():
            value = session.get_one(TranslationValue, value_id)
            locator = session.get_one(TranslationValueLocator, value_id)
            if index == 2 and language == "it":
                session.delete(locator)
                session.flush()
                session.delete(value)
                continue
            if index in {0, 1} and language == "fr":
                value.translated_text = value.display_text = ""
                value.grapheme_count = 0
            kind = "android_quantity" if index == 10 else "scalar"
            fields = {"quantity": "one"} if index == 10 else {}
            value.selector_kind = kind
            value.selector_bytes = json.dumps(
                {"version": 1, "kind": kind, "fields": fields}
            ).encode()
            value.selector_digest = hashlib.sha256(value.selector_bytes).hexdigest()
            locator.format = "android_xml"
            if index == 60 and language == "it":
                value.review_state = "approved"
            work.revision(
                session,
                value,
                source="Earlier source"
                if index == 0 and language == "en"
                else value.source_text,
                number=1,
            )
            if index == 0 and language == "en":
                work.revision(session, value, source=value.source_text, number=2)
            if index == 10:
                extra = TranslationValue(
                    **{
                        column.name: getattr(value, column.name)
                        for column in TranslationValue.__table__.columns
                    }
                )
                extra.id = uuid4()
                extra.selector_bytes = json.dumps(
                    {"version": 1, "kind": kind, "fields": {"quantity": "other"}}
                ).encode()
                extra.selector_digest = hashlib.sha256(extra.selector_bytes).hexdigest()
                extra.display_text = extra.source_text = (
                    "Several items" if language == "en" else None
                )
                if language != "en":
                    extra.translated_text = extra.display_text = f"{language} several"
                session.add(extra)
                session.flush()
                extra_locator = TranslationValueLocator(
                    **{
                        column.name: getattr(locator, column.name)
                        for column in TranslationValueLocator.__table__.columns
                    }
                )
                extra_locator.value_id = extra.id
                session.add(extra_locator)
                session.flush()
                work.revision(session, extra, source=extra.source_text, number=1)
                ids[index, language] = min(value.id, extra.id)
    duplicate, duplicate_scope = workspace.SEARCH._seed_dataset(
        factory, name="Other product"
    )
    workspace.SEARCH._add_group(
        factory,
        product_id=duplicate,
        scope_id=duplicate_scope,
        raw_key="key-000",
        language="fr",
        values=({"display_text": "Other scope", "translated_text": "Other scope"},),
    )
    source_product, target, source = work.seed(
        factory, name="Source only", separate=True, target_revision=False
    )
    with factory.begin() as session:
        # Keep only the real source in this disposable source-only product.
        session.delete(session.get_one(TranslationValueLocator, target))
        session.flush()
        session.delete(session.get_one(TranslationValue, target))
    embedded, _, _ = work.seed(
        factory, name="Embedded source", format="qt_ts", embedded=True, base=False
    )
    cap_product, cap_scope = workspace.SEARCH._seed_dataset(
        factory, name="Language catalog"
    )
    for locale in (
        "en",
        "fr",
        "it",
        "de",
        "es",
        "pt",
        "nl",
        "da",
        "sv",
        "no",
        "fi",
        "pl",
        "cs",
        "sk",
        "sl",
        "hr",
        "ro",
        "hu",
        "el",
        "tr",
        "uk",
    ):
        workspace.SEARCH._add_group(
            factory,
            product_id=cap_product,
            scope_id=cap_scope,
            raw_key="cap." + locale,
            language=locale,
            values=({"display_text": locale, "translated_text": locale},),
        )
    return {
        "multilingual_product": str(product),
        "multilingual_groups": {
            f"{index}:{language}": str(value)
            for (index, language), value in ids.items()
        },
        "duplicate_product": str(duplicate),
        "source_only_product": str(source_product),
        "source_only_group": str(source),
        "embedded_product": str(embedded),
        "language_catalog_product": str(cap_product),
    }


def run(mode: str):
    runtime = OwnedRuntime()
    passed = False
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    try:
        runtime.configure()
        for service in ("backend", "frontend"):
            runtime.stage = "build-" + service
            runtime.compose("build", service, timeout=600)
            print(runtime.stage + ": PASS", flush=True)
        runtime.stage = "infrastructure"
        runtime.compose(
            "up", "-d", "--wait", "--wait-timeout", "120", "postgres", "redis"
        )
        runtime.compose(
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "postgres",
            "-d",
            "template1",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "CREATE EXTENSION pg_trgm",
        )
        runtime.compose(
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "postgres",
            "-d",
            runtime.database,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "CREATE EXTENSION pg_trgm",
        )
        runtime.stage = "migrations"
        runtime.compose("run", "--rm", "-T", "backend", "alembic", "upgrade", "head")
        runtime.stage = "applications"
        runtime.compose(
            "up", "-d", "--wait", "--wait-timeout", "120", "backend", "frontend"
        )
        runtime.stage = "seed"
        fixture = seed(
            runtime,
            full=mode == "full",
            product_summary=mode == "product-summary",
            bilingual=mode == "bilingual",
            multilingual=mode == "multilingual",
        )
        fixture_path = runtime.path / "fixture.json"
        fixture_path.write_text(json.dumps(fixture))
        fixture_path.chmod(0o600)
        runtime.stage = "browser-" + mode
        output = runtime.command(
            "node",
            str(ROOT / "tools/dashboard_smoke_browser.mjs"),
            mode,
            str(fixture_path),
            runtime.backend,
            runtime.frontend,
            str(EVIDENCE),
            timeout=600 if mode in {"multilingual", "bilingual"} else 240,
        )
        print(output, end="", flush=True)
        if mode == "full":
            runtime.stage = "backend-regressions"
            env = {
                **os.environ,
                "VERBOFLEX_TEST_POSTGRES_ADMIN_URL": runtime.postgres_url()
                .replace("postgresql+psycopg:", "postgresql:")
                .rsplit("/", 1)[0]
                + "/postgres",
            }
            output = runtime.command(
                str(ROOT / "backend/.venv/bin/python"),
                "-m",
                "pytest",
                "tests/api/test_dashboard.py",
                "tests/api/test_openapi_contract.py",
                "tests/auth/test_translation_access.py",
                "-q",
                env=env,
                cwd=ROOT / "backend",
            )
            print(output, end="", flush=True)
        passed = True
    finally:
        runtime.cleanup()
        report = {
            "mode": mode,
            "passed": passed,
            "project": runtime.project,
            "cleanup": "Exact owned Compose containers, volumes, network, image tags and private runtime removed",
        }
        (EVIDENCE / f"{mode}-result.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print("owned cleanup: PASS", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tracer", action="store_true")
    group.add_argument("--full", action="store_true")
    group.add_argument("--product-summary", action="store_true")
    group.add_argument("--bilingual", action="store_true")
    group.add_argument("--multilingual", action="store_true")
    args = parser.parse_args()
    run(
        "multilingual"
        if args.multilingual
        else "bilingual"
        if args.bilingual
        else "product-summary"
        if args.product_summary
        else "tracer"
        if args.tracer
        else "full"
    )
