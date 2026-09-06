"""Real HTTP polling must not mix pre-activation jobs and post-activation datasets."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, current_thread

import httpx
import pytest
from sqlalchemy import event, text

from tests.integration.test_import_jobs import _configure_dependencies, _create_admin
from tests.integration.test_translation_import_activation import (
    _json_result,
    _seed_running_direct_import,
    _stage_direct_manifest,
)
from tests.integration.test_translation_import_activation import (
    activation_session_factory as activation_session_factory,
)
from tests.integration.test_translation_import_activation import (
    clean_activation_database as clean_activation_database,
)
from verboflex.main import app
from verboflex.models.import_job import ImportJob
from verboflex.services import import_jobs


@pytest.mark.parametrize("collection", [False, True])
def test_polling_and_activation_share_one_coherent_snapshot(
    activation_session_factory, monkeypatch, collection
):
    factory = activation_session_factory
    identity, repository = _seed_running_direct_import(factory)
    manifest, references = _stage_direct_manifest(
        factory, identity=identity, repository_id=repository, result=_json_result()
    )
    _configure_dependencies(factory)
    token = _create_admin(factory)
    path = f"/api/v1/admin/products/{identity.product_id}/" + (
        "published/mapping-imports" if collection else f"imports/{identity.import_id}"
    )
    original_statement = import_jobs._published_mapping_statement
    worker_ready = Event()
    worker_pid = []
    future = None
    blocked = False
    engine = factory.kw["bind"]

    def capture_worker(connection, _cursor, _statement, _parameters, _context, _many):
        if current_thread().name.startswith("activation-race") and not worker_pid:
            worker_pid.append(connection.connection.driver_connection.info.backend_pid)
            worker_ready.set()

    def activate():
        result = import_jobs.finish_import_execution(
            factory,
            identity=identity,
            references=references,
            canonical_manifest_digest=manifest.digest,
        )
        with factory() as verification:
            job = verification.get_one(ImportJob, identity.import_id)
            assert job.state == "current", (job.state, job.error_category)
        return result

    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://testserver",
        ) as client:
            return await client.get(path, headers={"Authorization": f"Bearer {token}"})

    event.listen(engine, "before_cursor_execute", capture_worker)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="activation-race") as executor:

        def interleave():
            nonlocal future, blocked
            if future is None:
                # Detail has loaded its job; collection has loaded its mappings
                # and eager scopes. Interleave before the other authority read.
                future = executor.submit(activate)
                assert worker_ready.wait(3)
                deadline = time.monotonic() + 3
                with engine.connect() as observer:
                    while not future.done():
                        blocked = bool(
                            observer.scalar(
                                text("SELECT cardinality(pg_blocking_pids(:pid))"),
                                {"pid": worker_pid[0]},
                            )
                        )
                        if blocked:
                            break
                        assert time.monotonic() < deadline, "worker did not reach barrier"
                        time.sleep(0.01)

        def mapping_statement(**kwargs):
            if not collection:
                interleave()
            return original_statement(**kwargs)

        def collection_jobs(_connection, _cursor, statement, _parameters, _context, _many):
            if (
                collection
                and not current_thread().name.startswith("activation-race")
                and "FROM import_jobs" in statement
                and "import_jobs.revision_id =" in statement
            ):
                interleave()

        monkeypatch.setattr(import_jobs, "_published_mapping_statement", mapping_statement)
        event.listen(engine, "before_cursor_execute", collection_jobs)
        try:
            response = asyncio.run(request())
            assert future is not None and future.result(timeout=3)
            assert response.status_code == 200
            record = response.json()["items"][0] if collection else response.json()
            assert (record["state"], record["dataset_status"]) == ("running", "not_created")
            assert blocked, "worker must wait for the in-flight polling snapshot"
            refreshed = asyncio.run(request())
            assert refreshed.status_code == 200
            record = refreshed.json()["items"][0] if collection else refreshed.json()
            assert (record["state"], record["dataset_status"]) == ("current", "active")
        finally:
            event.remove(engine, "before_cursor_execute", capture_worker)
            event.remove(engine, "before_cursor_execute", collection_jobs)
            app.dependency_overrides.clear()
