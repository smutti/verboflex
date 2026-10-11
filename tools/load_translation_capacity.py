"""Owned PostgreSQL/Redis + real HTTP capacity experiment; never uses app .env files.

Run: backend/.venv/bin/python tools/load_translation_capacity.py --output /tmp/vf-load
Only generated containers/databases are accepted. Synthetic seed is not import proof.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import platform
import signal
import socket
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
LANGUAGES = [
    "en",
    "fr",
    "it",
    "de",
    "es",
    "pt",
    "nl",
    "pl",
    "cs",
    "da",
    "sv",
    "fi",
    "ro",
    "hu",
    "tr",
    "ar",
    "ja",
    "ko",
    "vi",
    "zh",
]


def emit(event, **values):
    print(json.dumps({"event": event, **values}), flush=True)


def capture(command, **kwargs):
    return (
        subprocess.check_output(command, stderr=subprocess.PIPE, timeout=120, **kwargs)
        .decode()
        .strip()
    )


class Lab:
    def __init__(self, output):
        self.output = output
        self.owner = uuid4().hex
        self.containers = []
        self.api = None
        self.secret = uuid4().hex + uuid4().hex
        # No inherited application/database/provider configuration.
        self.env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("VERBOFLEX_", "PG"))
        }
        self.env.update(VERBOFLEX_APP_ENV="local", VERBOFLEX_JWT_SECRET_KEY=self.secret)

    def infrastructure(self):
        for kind, image, port, extra, args in (
            (
                "postgres",
                "postgres:18-alpine",
                5432,
                [
                    "--cpus=4",
                    "--memory=6g",
                    "--shm-size=512m",
                    "-e",
                    "POSTGRES_HOST_AUTH_METHOD=trust",
                ],
                [
                    "-c",
                    "shared_buffers=512MB",
                    "-c",
                    "work_mem=16MB",
                    "-c",
                    "maintenance_work_mem=256MB",
                    "-c",
                    "statement_timeout=15000",
                    "-c",
                    "max_connections=100",
                ],
            ),
            ("redis", "redis:7-alpine", 6379, ["--cpus=0.5", "--memory=256m"], []),
        ):
            name = f"verboflex-load-{kind}-{self.owner[:12]}"
            container = capture(
                [
                    "docker",
                    "run",
                    "-d",
                    "--rm",
                    "--name",
                    name,
                    "--label",
                    f"verboflex.load.owner={self.owner}",
                    "-p",
                    f"127.0.0.1::{port}",
                    *extra,
                    image,
                    *args,
                ]
            )
            self.containers.append(container)
            deadline = time.monotonic() + 60
            probe = (
                ["pg_isready", "-h", "127.0.0.1", "-U", "postgres"]
                if kind == "postgres"
                else ["redis-cli", "ping"]
            )
            while subprocess.run(
                ["docker", "exec", container, *probe], capture_output=True, check=False
            ).returncode:
                if time.monotonic() > deadline:
                    raise RuntimeError("owned infrastructure readiness timeout")
                time.sleep(0.5)
            bound = int(
                capture(["docker", "port", container, f"{port}/tcp"]).rsplit(":", 1)[1]
            )
            if kind == "postgres":
                self.pg = container
                self.env["VERBOFLEX_TEST_POSTGRES_ADMIN_URL"] = (
                    f"postgresql://postgres@127.0.0.1:{bound}/postgres"
                )
                for db in ("postgres", "template1"):
                    capture(
                        [
                            "docker",
                            "exec",
                            container,
                            "psql",
                            "-U",
                            "postgres",
                            "-d",
                            db,
                            "-c",
                            "CREATE EXTENSION pg_trgm",
                        ]
                    )
            else:
                self.env["VERBOFLEX_REDIS_URL"] = f"redis://127.0.0.1:{bound}/0"
        for key in list(os.environ):
            if key.startswith(("VERBOFLEX_", "PG")):
                del os.environ[key]
        os.environ.update(
            {k: v for k, v in self.env.items() if k.startswith("VERBOFLEX_")}
        )

    def start_api(self, url):
        import httpx

        self.env["VERBOFLEX_DATABASE_URL"] = url
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        self.base_url = f"http://127.0.0.1:{sock.getsockname()[1]}"
        with (self.output / "api.log").open("ab") as stream:
            self.api = subprocess.Popen(
                [
                    str(BACKEND / ".venv/bin/python"),
                    "-m",
                    "uvicorn",
                    "verboflex.main:app",
                    "--fd",
                    str(sock.fileno()),
                    "--no-access-log",
                ],
                cwd=BACKEND,
                env=self.env,
                pass_fds=(sock.fileno(),),
                stdout=stream,
                stderr=subprocess.STDOUT,
            )
        sock.close()
        for _ in range(100):
            if self.api.poll() is not None:
                raise RuntimeError("owned API exited")
            try:
                if (
                    httpx.get(self.base_url + "/openapi.json", timeout=1).status_code
                    == 200
                ):
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        raise RuntimeError("owned API readiness timeout")

    def resources(self):
        stats = [
            json.loads(line)
            for line in capture(
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "{{json .}}",
                    *self.containers,
                ]
            ).splitlines()
        ]
        return {
            "containers": [
                {k: x[k] for k in ("Name", "CPUPerc", "MemUsage", "BlockIO")}
                for x in stats
            ],
            "api_rss_kib": int(capture(["ps", "-o", "rss=", "-p", str(self.api.pid)])),
        }

    def close(self):
        if self.api and self.api.poll() is None:
            self.api.terminate()
            try:
                self.api.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.api.kill()
                self.api.wait(timeout=10)
        for container in reversed(self.containers):
            owner = capture(
                [
                    "docker",
                    "inspect",
                    "--format",
                    '{{index .Config.Labels "verboflex.load.owner"}}',
                    container,
                ]
            )
            if owner != self.owner:
                raise RuntimeError("refusing cleanup of an unowned container")
            capture(["docker", "rm", "-fv", container])


def clone_rows(session, table, identity, template_id, overrides, source):
    """Fixed harness-owned identifiers only; retain all application constraints/triggers."""
    from sqlalchemy import text

    columns = list(
        session.scalars(
            text(
                "SELECT attname FROM pg_attribute WHERE attrelid=CAST(:table AS regclass) "
                "AND attnum>0 AND NOT attisdropped AND attgenerated='' ORDER BY attnum"
            ),
            {"table": table},
        )
    )
    names = ", ".join(f'"{c}"' for c in columns)
    projection = ", ".join(overrides.get(c, f't."{c}"') for c in columns)
    session.execute(
        text(
            f"INSERT INTO {table} ({names}) SELECT {projection} FROM {table} t "
            f"CROSS JOIN {source} WHERE t.{identity}=:template"
        ),
        {"template": template_id},
    )


def templates(factory, products):
    from tests.api import test_translation_work_filters as support
    from verboflex.models.translation import TranslationValue

    result = []
    for index in range(products):
        product, scope = support.SEARCH._seed_dataset(
            factory, name=f"Load product {index:02}"
        )
        value_id = support.SEARCH._add_group(
            factory,
            product_id=product,
            scope_id=scope,
            raw_key="seed-template",
            language="en",
            values=({"source_text": "Template", "display_text": "Template"},),
        )
        with factory.begin() as session:
            value = session.get_one(TranslationValue, value_id)
            value.selector_bytes = b'{"version":1,"kind":"scalar","fields":{}}'
            value.selector_digest = hashlib.sha256(value.selector_bytes).hexdigest()
            support.revision(session, value, source=value.source_text, number=1)
            result.append(
                {
                    "product": str(product),
                    "scope": str(scope),
                    "key": str(value.translation_key_id),
                    "value": str(value_id),
                    "index": index,
                }
            )
    return result


def grow(factory, fixtures, previous_keys, target_keys):
    from sqlalchemy import text

    started = time.monotonic()
    for fixture in fixtures:
        for start in range(previous_keys + 1, target_keys + 1, 1000):
            end = min(start + 999, target_keys)
            with factory.begin() as session:
                session.execute(text("SET LOCAL statement_timeout='120s'"))
                session.execute(
                    text(
                        "CREATE TEMP TABLE load_keys ON COMMIT DROP AS SELECT n, gen_random_uuid() key_id "
                        "FROM generate_series(CAST(:start AS integer),CAST(:end AS integer)) n"
                    ),
                    {"start": start, "end": end},
                )
                clone_rows(
                    session,
                    "translation_keys",
                    "id",
                    fixture["key"],
                    {
                        "id": "ids.key_id",
                        "raw_key": "'message.' || lpad(ids.n::text,8,'0')",
                    },
                    "load_keys ids",
                )
                session.execute(
                    text(
                        "CREATE TEMP TABLE load_values ON COMMIT DROP AS "
                        "SELECT k.*, gen_random_uuid() value_id, lang, "
                        "CASE WHEN lang='en' THEN 'Source message ' || n "
                        "WHEN n%5=0 THEN '' ELSE lang || ' Translation message ' || n || ' settings account' END AS content "
                        "FROM load_keys k CROSS JOIN unnest(CAST(:langs AS text[])) lang"
                    ),
                    {"langs": LANGUAGES},
                )
                changes = {
                    "id": "ids.value_id",
                    "translation_key_id": "ids.key_id",
                    "language": "ids.lang",
                    "source_text": "CASE WHEN ids.lang='en' THEN ids.content ELSE NULL END",
                    "translated_text": "CASE WHEN ids.lang='en' THEN NULL ELSE ids.content END",
                    "display_text": "ids.content",
                    "grapheme_count": "length(ids.content)",
                    "review_state": "CASE WHEN ids.n%20=1 THEN 'rejected' WHEN ids.n%5=1 THEN 'approved' ELSE 'draft' END",
                }
                clone_rows(
                    session,
                    "translation_values",
                    "id",
                    fixture["value"],
                    changes,
                    "load_values ids",
                )
                clone_rows(
                    session,
                    "translation_value_locators",
                    "value_id",
                    fixture["value"],
                    {
                        "value_id": "ids.value_id",
                        "translation_key_id": "ids.key_id",
                        "position": "ids.n",
                        "structural_address": "jsonb_build_array('message.' || lpad(ids.n::text,8,'0'), ids.lang)",
                    },
                    "load_values ids",
                )
                clone_rows(
                    session,
                    "translation_value_revisions",
                    "value_id",
                    fixture["value"],
                    {
                        "id": "gen_random_uuid()",
                        "value_id": "ids.value_id",
                        "translation_key_id": "ids.key_id",
                        **{
                            k: v
                            for k, v in changes.items()
                            if k
                            in (
                                "source_text",
                                "translated_text",
                                "display_text",
                                "review_state",
                            )
                        },
                    },
                    "load_values ids",
                )
                # Refresh FK/planner statistics during growth, without disabling any guard.
                if start == previous_keys + 1:
                    for table in (
                        "translation_keys",
                        "translation_values",
                        "translation_value_locators",
                        "translation_value_revisions",
                    ):
                        session.execute(text(f"ANALYZE {table}"))
        emit(
            "seed_product",
            product=fixture["index"],
            keys_per_product=target_keys,
            elapsed_seconds=round(time.monotonic() - started, 2),
        )
    with factory.begin() as session:
        session.execute(text("SET LOCAL statement_timeout='120s'"))
        session.execute(text("ANALYZE"))
    return time.monotonic() - started


def identities(factory, count, secret):
    from pydantic import SecretStr
    from sqlalchemy import select
    from verboflex.auth.access_tokens import issue_access_token
    from verboflex.core.config import Settings
    from verboflex.models.auth_session import AuthSession
    from verboflex.models.role import Role
    from verboflex.models.user import User

    now = datetime.now(UTC)
    settings = Settings(jwt_secret_key=SecretStr(secret))
    tokens = []
    with factory.begin() as session:
        role = session.scalar(select(Role).where(Role.name == "admin"))
        for _ in range(count):
            user, auth = uuid4(), uuid4()
            session.add(
                User(
                    id=user,
                    email=f"load-{user}@example.com",
                    display_name="Synthetic reader",
                    hashed_password="no-password-login-for-load-fixture",
                    is_active=True,
                    must_change_password=False,
                    roles=[role],
                )
            )
            session.flush()
            session.add(
                AuthSession(
                    id=auth,
                    user_id=user,
                    family_id=uuid4(),
                    token_hash=uuid4().hex + uuid4().hex,
                    expires_at=now + timedelta(days=1),
                )
            )
            tokens.append(
                issue_access_token(
                    user_id=user,
                    session_id=auth,
                    token_version=0,
                    purpose="access",
                    settings=settings,
                    now=now,
                )
            )
    return tokens


def summarize(samples):
    latencies = sorted(x["ms"] for x in samples)
    good = sorted(x["ms"] for x in samples if x["status"] == 200 and x["correct"])

    def percentiles(values):
        return {
            f"p{p}_ms": round(values[math.ceil(p / 100 * len(values)) - 1], 2)
            if values
            else None
            for p in (50, 95, 99)
        }

    return {
        "requests": len(samples),
        "status_counts": dict(Counter(str(x["status"]) for x in samples)),
        "correctness_errors": sum(
            not x["correct"] for x in samples if x["status"] == 200
        ),
        "all_responses": percentiles(latencies),
        "successful_responses": percentiles(good),
        "response_bytes_median": statistics.median(x["bytes"] for x in samples)
        if samples
        else 0,
    }


async def measure(base_url, factory, fixture, secret, clients, seconds, *, pilot=False):
    import httpx

    tokens = identities(factory, clients + 1, secret)
    params = {"product_id": fixture["product"], "visible_languages": LANGUAGES}
    cases = {
        "global_browse": (
            "/api/v1/translations/keys",
            {"visible_languages": LANGUAGES},
        ),
        "product_browse": ("/api/v1/translations/keys", params),
        "selective_search": (
            "/api/v1/translations/keys",
            {**params, "q": "message.00000042"},
        ),
        "broad_search": ("/api/v1/translations/keys", {**params, "q": "settings"}),
        "state_filter": (
            "/api/v1/translations/keys",
            {**params, "language": "fr", "state": "approved"},
        ),
        "missing_filter": (
            "/api/v1/translations/keys",
            {**params, "work_status": "needs_translation", "language": "fr"},
        ),
        "summary": (f"/api/v1/admin/products/{fixture['product']}/summary", {}),
        "options": ("/api/v1/translations/options", {}),
    }
    observations = []
    wall_started = time.time()
    monotonic_started = time.monotonic()
    async with httpx.AsyncClient(
        base_url=base_url, timeout=45, limits=httpx.Limits(max_connections=clients + 2)
    ) as client:
        initial = await client.get(
            cases["product_browse"][0],
            params=params,
            headers={"Authorization": f"Bearer {tokens[0]}"},
        )
        if initial.status_code != 200:
            raise RuntimeError(f"browse warmup status {initial.status_code}")
        body = initial.json()
        first_ids = {item["translation_key_id"] for item in body["items"]}
        if not body["next_cursor"] or len(first_ids) != 50:
            raise RuntimeError("fixture cannot exercise pagination")
        cursors = {tokens[0]: body["next_cursor"]}
        for token in tokens[1:clients]:
            warm = await client.get(
                cases["product_browse"][0],
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            warm.raise_for_status()
            cursors[token] = warm.json()["next_cursor"]
        cases["continuation"] = (
            cases["product_browse"][0],
            {**params, "cursor": body["next_cursor"]},
        )

        async def request(name, token):
            path, query = cases[name]
            if name == "continuation":
                query = {**query, "cursor": cursors[token]}
            started = time.perf_counter()
            status, size, correct = "timeout", 0, False
            try:
                response = await client.get(
                    path, params=query, headers={"Authorization": f"Bearer {token}"}
                )
                status, size = response.status_code, len(response.content)
                if status == 200:
                    data = response.json()
                    correct = True
                    if name == "summary":
                        keys = fixture["keys"]
                        targets = len(LANGUAGES) - 1
                        correct = (
                            data["source_string_count"] == keys + 1
                            and data["expected_translation_count"]
                            == targets * (keys + 1)
                            and data["translated_count"] == targets * (keys - keys // 5)
                            and data["missing_count"] == targets * (keys // 5 + 1)
                        )
                    if path.endswith("/keys"):
                        items = data["items"]
                        ids = {x["translation_key_id"] for x in items}
                        correct = len(items) <= 50 and len(ids) == len(items)
                        correct &= all(len(x["slots"]) == len(LANGUAGES) for x in items)
                        if name != "global_browse":
                            correct &= all(
                                x["product_id"] == fixture["product"] for x in items
                            )
                        if name == "state_filter":
                            correct &= bool(items) and all(
                                any(
                                    s["language"] == "fr"
                                    and s["states"] == ["approved"]
                                    for s in x["slots"]
                                )
                                for x in items
                            )
                        if name == "missing_filter":
                            correct &= bool(items) and all(
                                any(
                                    s["language"] == "fr"
                                    and s["effective_text"] in (None, "")
                                    for s in x["slots"]
                                )
                                for x in items
                            )
                        if name == "continuation":
                            correct &= not bool(ids & first_ids)
                        if name == "selective_search":
                            correct &= bool(items) and all(
                                x["raw_key"] == "message.00000042" for x in items
                            )
            except httpx.HTTPError:
                pass
            row = {
                "case": name,
                "status": status,
                "correct": correct,
                "bytes": size,
                "ms": round((time.perf_counter() - started) * 1000, 3),
            }
            observations.append(row)
            return row

        if pilot:
            # Individual first-request diagnostics; no statistical p95 claim.
            for name in cases:
                row = await request(name, tokens[0])
                emit("pilot", **row)
        else:
            # Closed-loop read mix; one request in flight per authenticated user.
            # Fixed think time keeps each user below 120 ordinary reads/minute.
            mix = [
                "global_browse",
                "product_browse",
                "continuation",
                "product_browse",
                "selective_search",
                "state_filter",
                "options",
                "broad_search",
                "missing_filter",
                "summary",
            ]
            until = time.monotonic() + seconds

            async def reader(index):
                iteration = index
                while time.monotonic() < until:
                    await request(mix[iteration % len(mix)], tokens[index])
                    iteration += 1
                    await asyncio.sleep(0.55)

            await asyncio.gather(*(reader(i) for i in range(clients)))
    by_case = {
        name: summarize([x for x in observations if x["case"] == name])
        for name in cases
    }
    return {
        "clients": clients,
        "target_duration_seconds": seconds,
        "started_at": datetime.fromtimestamp(wall_started, UTC).isoformat(),
        "wall_elapsed_seconds": time.time() - wall_started,
        "clock_skew_seconds": (time.time() - wall_started)
        - (time.monotonic() - monotonic_started),
        "pilot": pilot,
        "summary": summarize(observations),
        "cases": by_case,
        "samples": observations,
    }


async def write_and_rate_probe(lab, factory, fixture, clients):
    """Independent keys, persisted read-back, optimistic-conflict and real Redis limits."""
    import httpx

    tokens = identities(factory, clients + 2, lab.secret)
    rows = []
    async with httpx.AsyncClient(base_url=lab.base_url, timeout=45) as client:
        page = await client.get(
            "/api/v1/translations/keys",
            params={"product_id": fixture["product"], "visible_languages": "fr"},
            headers={"Authorization": f"Bearer {tokens[-1]}"},
        )
        page.raise_for_status()
        groups = [x["slots"][0]["group_id"] for x in page.json()["items"][:clients]]
        assert len(groups) == clients and all(groups)

        async def writer(index):
            path = f"/api/v1/translations/{groups[index]}"
            headers = {"Authorization": f"Bearer {tokens[index]}"}
            detail = await client.get(path, headers=headers)
            detail.raise_for_status()
            data = detail.json()
            basis = [
                {
                    "translation_value_id": v["id"],
                    "selector_version": v["selector_version"],
                    "selector_digest": v["selector_digest"],
                    "basis_revision_number": v["history"][0]["revision_number"],
                    "basis_digest": v["history"][0]["revision_digest"],
                }
                for v in data["values"]
            ]
            version = (data.get("pending_change") or {}).get("version", 0)
            published = [(v["id"], v["display_text"]) for v in data["values"]]
            for iteration in range(10):
                proposed = f"Load edit {index}:{iteration} 日本語"
                payload = {
                    "expected_version": version,
                    "values": [{**v, "proposed_text": proposed} for v in basis],
                }
                start = time.perf_counter()
                response = await client.put(
                    path + "/proposal", headers=headers, json=payload
                )
                elapsed = (time.perf_counter() - start) * 1000
                correct = False
                if response.status_code == 200:
                    body = response.json()
                    correct = body["version"] == version + 1 and all(
                        v["text"] == proposed for v in body["pending"]
                    )
                    version = body["version"]
                    persisted = await client.get(path, headers=headers)
                    if persisted.status_code == 200:
                        current = persisted.json()
                        pending = current["pending_change"]
                        correct &= pending["version"] == version and all(
                            v["text"] == proposed for v in pending["values"]
                        )
                        correct &= [
                            (v["id"], v["display_text"]) for v in current["values"]
                        ] == published
                    else:
                        correct = False
                rows.append(
                    {
                        "case": "save",
                        "status": response.status_code,
                        "correct": correct,
                        "bytes": len(response.content),
                        "ms": round(elapsed, 3),
                    }
                )
                if not correct:
                    break
            # The last successful request's previous version cannot overwrite it.
            conflict = await client.put(
                path + "/proposal", headers=headers, json=payload
            )
            return conflict.status_code == 409

        conflicts = await asyncio.gather(*(writer(i) for i in range(clients)))
        rate = []
        for _ in range(121):
            response = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {tokens[-2]}"},
            )
            rate.append(response.status_code)
        rate_ok = (
            rate == [200] * 120 + [429]
            and int(response.headers.get("Retry-After", "0")) > 0
        )
    return {
        "clients": clients,
        "summary": summarize(rows),
        "samples": rows,
        "stale_versions_rejected": all(conflicts),
        "rate_limit_120_then_429": rate_ok,
        "rate_limit_endpoint": "/api/v1/users/me",
        "rate_status_counts": dict(Counter(str(status) for status in rate)),
    }


def explain(factory, fixture):
    from benchmark_translation_workspace import sanitized_plan
    from sqlalchemy import event, text
    from sqlalchemy.exc import DBAPIError
    from tests.integration.test_translation_workspace_performance import read_page
    from verboflex.services.product_summary import (
        _QT_UNFINISHED,
        _SUMMARY_SQL,
        _WHITESPACE,
    )

    class Captured(Exception):
        pass

    statements = []

    def capture_query(connection, cursor, statement, parameters, context, executemany):
        if "aggregates AS MATERIALIZED" in statement:
            statements.append((statement, parameters))
            raise Captured

    engine = factory.kw["bind"]
    result = {}
    for name, filters in (
        ("global_browse", {}),
        ("product_browse", {"product_id": fixture["product"]}),
        (
            "selective_search",
            {"product_id": fixture["product"], "q": "message.00000042"},
        ),
        (
            "state_filter",
            {"product_id": fixture["product"], "language": "fr", "state": "approved"},
        ),
    ):
        event.listen(engine, "before_cursor_execute", capture_query)
        try:
            read_page(factory, visible_languages=LANGUAGES, **filters)
        except Captured:
            pass
        finally:
            event.remove(engine, "before_cursor_execute", capture_query)
        if not statements:
            raise RuntimeError("expected workspace SQL was not captured")
        statement, parameters = statements.pop()
        with engine.connect() as connection:
            connection.exec_driver_sql("SET LOCAL statement_timeout='15s'")
            connection.exec_driver_sql("SET LOCAL jit=off")
            try:
                plan = connection.exec_driver_sql(
                    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement, parameters
                ).scalar_one()[0]
                result[name] = sanitized_plan(plan)
            except DBAPIError as error:
                result[name] = {
                    "error": type(error).__name__,
                    "statement_timeout_ms": 15000,
                }
    with factory() as session:
        session.execute(text("SET LOCAL statement_timeout='15s'"))
        try:
            plan = session.execute(
                text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + _SUMMARY_SQL.text),
                {
                    "product_id": fixture["product"],
                    "whitespace": _WHITESPACE,
                    "qt_unfinished": _QT_UNFINISHED,
                    "language_limit": 500,
                },
            ).scalar_one()[0]
            result["summary"] = sanitized_plan(plan)
        except DBAPIError as error:
            result["summary"] = {
                "error": type(error).__name__,
                "statement_timeout_ms": 15000,
            }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--values", type=int, nargs="+", default=[100_000, 1_000_000, 10_000_000]
    )
    parser.add_argument("--products", type=int, default=10)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--clients", type=int, nargs="+", default=[1, 5, 20])
    args = parser.parse_args()
    if not (
        1 <= args.products <= 100
        and 5 <= args.seconds <= 300
        and all(1 <= c <= 50 for c in args.clients)
        and args.values == sorted(set(args.values))
        and all(
            args.products * len(LANGUAGES) * 60 <= n <= 10_000_000 for n in args.values
        )
    ):
        parser.error("invalid bounded experiment settings")
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=False)
    lab = Lab(args.output)
    report = {
        "source_commit": capture(["git", "rev-parse", "HEAD"], cwd=ROOT),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "started_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "postgres_limits": {"cpus": 4, "memory_gib": 6, "statement_timeout_ms": 15000},
        "api": "one host uvicorn process; SQLAlchemy default pool; real TCP and JWT/session/roles; existing Redis limits remain unchanged",
        "think_seconds": 0.55,
        "languages": LANGUAGES,
        "stages": [],
        "cleanup": False,
        "limitations": [
            "Synthetic scalar corpus, one immutable revision per value; not import/refresh capacity proof",
            "Local shared Docker host; neither production hardware nor browser rendering measured",
            "Closed-loop clients and fixed think time; no open-loop arrival-rate certification",
            "Heavy translation routes currently have no ordinary-read rate limiter; the limit probe uses users/me",
            "Post-seed warm database, no OS cache eviction; pilot is not a cold-cache benchmark",
        ],
    }

    def save():
        (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")

    try:
        lab.infrastructure()
        # Import only after the isolated environment exists.
        from sqlalchemy import text
        from tests.integration.test_translation_workspace_performance import (
            owned_database,
        )

        with owned_database() as factory:
            fixtures = templates(factory, args.products)
            lab.start_api(factory.kw["bind"].url.render_as_string(hide_password=False))
            previous = 0
            for count in args.values:
                keys = count // (args.products * len(LANGUAGES))
                seed_seconds = grow(factory, fixtures, previous, keys)
                previous = keys
                for fixture in fixtures:
                    fixture["keys"] = keys
                with factory() as session:
                    inventory = {
                        name: int(session.scalar(text(f"SELECT count(*) FROM {name}")))
                        for name in (
                            "translation_keys",
                            "translation_values",
                            "translation_value_revisions",
                            "translation_value_locators",
                        )
                    }
                    inventory["database_bytes"] = session.scalar(
                        text("SELECT pg_database_size(current_database())")
                    )
                assert (
                    inventory["translation_values"]
                    == keys * args.products * len(LANGUAGES) + args.products
                )
                stage = {
                    "requested_values": count,
                    "inventory": inventory,
                    "seed_seconds": seed_seconds,
                    "runs": [],
                }
                report["stages"].append(stage)
                save()
                for clients in [0, *args.clients]:
                    started = time.monotonic()
                    resource_samples = []
                    resource_errors = []
                    stop = Event()

                    def monitor(
                        stop=stop,
                        resource_samples=resource_samples,
                        resource_errors=resource_errors,
                    ):
                        while not stop.is_set():
                            try:
                                resource_samples.append(lab.resources())
                            except (
                                OSError,
                                ValueError,
                                subprocess.SubprocessError,
                            ) as error:
                                resource_errors.append(type(error).__name__)
                            stop.wait(2)

                    monitor_thread = Thread(target=monitor, daemon=True)
                    monitor_thread.start()
                    try:
                        result = asyncio.run(
                            measure(
                                lab.base_url,
                                factory,
                                fixtures[0],
                                lab.secret,
                                max(clients, 1),
                                args.seconds,
                                pilot=clients == 0,
                            )
                        )
                    finally:
                        stop.set()
                        monitor_thread.join(timeout=5)
                    result["elapsed_seconds"] = time.monotonic() - started
                    result["requests_per_second"] = (
                        result["summary"]["requests"] / result["elapsed_seconds"]
                    )
                    result["resource_samples"] = resource_samples
                    result["resource_errors"] = resource_errors
                    stage["runs"].append(result)
                    save()
                    emit(
                        "run",
                        values=inventory["translation_values"],
                        clients=clients,
                        elapsed_seconds=round(result["elapsed_seconds"], 2),
                        **result["summary"],
                    )
                stage["query_plans"] = explain(factory, fixtures[0])
                stage["write_probe"] = asyncio.run(
                    write_and_rate_probe(lab, factory, fixtures[0], max(args.clients))
                )
                emit(
                    "writes",
                    values=inventory["translation_values"],
                    **stage["write_probe"]["summary"],
                    stale_versions_rejected=stage["write_probe"][
                        "stale_versions_rejected"
                    ],
                    rate_limit_120_then_429=stage["write_probe"][
                        "rate_limit_120_then_429"
                    ],
                )
                save()
    except BaseException as error:
        report["error"] = type(error).__name__
        save()
        raise
    finally:
        lab.close()
        report["cleanup"] = True
        report["finished_at"] = datetime.now(UTC).isoformat()
        save()
    failures = []
    for stage in report["stages"]:
        for run in stage["runs"]:
            summary = run["summary"]
            if abs(run["clock_skew_seconds"]) > 5 or run["resource_errors"]:
                failures.append(
                    {
                        "values": stage["requested_values"],
                        "clients": run["clients"],
                        "reason": "invalid measurement: clock jump or resource monitor failure",
                    }
                )
            if (
                set(summary["status_counts"]) != {"200"}
                or summary["correctness_errors"]
            ):
                failures.append(
                    {
                        "values": stage["requested_values"],
                        "clients": run["clients"],
                        "reason": "read errors",
                    }
                )
            if (
                not run["pilot"]
                and run["clients"] == 5
                and (
                    summary["successful_responses"]["p95_ms"] is None
                    or summary["successful_responses"]["p95_ms"] > 2000
                )
            ):
                failures.append(
                    {
                        "values": stage["requested_values"],
                        "clients": 5,
                        "reason": "interactive p95 exceeds 2000 ms",
                    }
                )
        write = stage["write_probe"]
        if (
            set(write["summary"]["status_counts"]) != {"200"}
            or write["summary"]["correctness_errors"]
            or not write["stale_versions_rejected"]
            or not write["rate_limit_120_then_429"]
        ):
            failures.append(
                {
                    "values": stage["requested_values"],
                    "reason": "write or rate-limit regression",
                }
            )
    report["gate"] = {
        "passed": not failures,
        "failures": failures,
        "target": "interactive mixed-read p95 <= 2000 ms at five clients; no unexpected HTTP or correctness errors at any measured concurrency",
    }
    save()
    return 0 if not failures else 2


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(130))
    raise SystemExit(main())
