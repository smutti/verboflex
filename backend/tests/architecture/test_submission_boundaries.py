"""Executable HTTP/worker/privacy boundaries, with adversarial negative controls."""

import ast
import importlib
import inspect
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import inspect as orm_inspect

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "backend/src"
MATRIX = ROOT / "backend/tests/fixtures/submissions/edge_matrix.json"
ROUTES = "verboflex.api.v1.routes.submissions"
NETWORK = ("httpx", "requests", "socket", "urllib.request")
PROVIDER_CALLS = {
    "resolve_repository_branch",
    "read_repository_source_file",
    "read_repository_source_metadata",
    "read_repository_metadata",
    "create_branch",
    "create_commit",
    "create_pull_request",
    "reconcile_branch",
    "reconcile_commit",
    "reconcile_pull_request",
    "read_pull_request",
    "read_pr_merge_status",
    "read_rebase_file",
    "verify_commit_files",
}


def assert_http_graph_is_database_only(sources, roots):
    """Follow named service calls and import aliases, including nested local imports.

    This is a bounded architectural guard, not a general Python dataflow proof;
    the real API tests also trap provider preparation and prove no enqueue on reads.
    """
    cache, visited = {}, set()

    def module(name):
        if name not in cache:
            if name in sources:
                text = sources[name]
            else:
                path = SOURCE / (name.replace(".", "/") + ".py")
                if not name.startswith("verboflex.") or not path.is_file():
                    return None
                text = path.read_text()
            tree = ast.parse(text)
            functions = {
                n.name: n
                for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            cache[name] = tree, functions
        return cache[name]

    def aliases(nodes):
        found = {}
        for node in nodes:
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    found[alias.asname or alias.name] = f"{node.module}.{alias.name}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    found[alias.asname or alias.name.split(".")[0]] = (
                        alias.name if alias.asname else alias.name.split(".")[0]
                    )
        return found

    def walk(name, function):
        if (name, function) in visited:
            return
        loaded = module(name)
        if loaded is None or function not in loaded[1]:
            return
        visited.add((name, function))
        tree, functions = loaded
        node = functions[function]
        imports = {**aliases(tree.body), **aliases(ast.walk(node))}
        for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
            parts, value = [], call.func
            while isinstance(value, ast.Attribute):
                parts.insert(0, value.attr)
                value = value.value
            if isinstance(value, ast.Name):
                parts.insert(0, value.id)
            else:
                continue
            qualified = ".".join([imports.get(parts[0], parts[0]), *parts[1:]])
            assert not qualified.startswith(NETWORK), (
                f"HTTP reaches network: {name}.{function}: {qualified}"
            )
            assert parts[-1] not in PROVIDER_CALLS, f"HTTP reaches provider operation: {qualified}"
            if "." not in qualified and qualified in functions:
                walk(name, qualified)
            elif qualified.startswith("verboflex."):
                owner, target = qualified.rsplit(".", 1)
                walk(owner, target)

    for owner, function in roots:
        walk(owner, function)
    return visited


def test_submission_http_routes_and_transitive_services_never_execute_provider_io():
    tree = ast.parse((SOURCE / "verboflex/api/v1/routes/submissions.py").read_text())
    roots = [
        (ROUTES, n.name) for n in tree.body if isinstance(n, ast.FunctionDef) and n.decorator_list
    ]
    assert len(roots) >= 10
    visited = assert_http_graph_is_database_only({}, roots)
    assert ("verboflex.services.submissions", "create_submission_batch") in visited
    assert ("verboflex.services.submission_recovery", "request_retry") in visited
    assert ("verboflex.services.submission_history", "list_change_set_values") in visited


@pytest.mark.parametrize(
    "forbidden",
    [
        "import httpx as network\n    network.get('https://example.test')",
        "adapter.read_repository_source_file(session)",
        "from verboflex.services.writeback import prepare_writeback as work\n"
        "    work(factory, selection=value, adapter=adapter)",
    ],
)
def test_http_guard_detects_network_hidden_behind_a_helper_or_alias(forbidden):
    source = "def endpoint():\n    helper()\ndef helper():\n    " + forbidden + "\n"
    with pytest.raises(AssertionError, match="HTTP reaches"):
        assert_http_graph_is_database_only(
            {"verboflex.test_boundary": source}, [("verboflex.test_boundary", "endpoint")]
        )


@pytest.mark.parametrize(
    "module,function,task",
    [
        ("submission_reviews", "enqueue_submission_review", "run_submission_review"),
        ("submissions", "enqueue_submission", "run_submission"),
        ("submission_recovery", "enqueue_reconciliation", "run_submission_reconciliation"),
    ],
)
def test_each_enqueuer_transmits_exactly_one_uuid_string(monkeypatch, module, function, task):
    from verboflex.worker import submission_tasks
    from verboflex.worker.celery_app import app

    queued = []
    worker = getattr(submission_tasks, task)

    def send_task(name, **options):
        assert name == worker.name
        assert set(options) <= {"args", "kwargs", "serializer", "task_id"}
        assert options["serializer"] == "json"
        queued.append((tuple(options.get("args", ())), options.get("kwargs", {})))

    monkeypatch.setattr(app, "send_task", send_task)
    monkeypatch.setattr(
        getattr(submission_tasks, task),
        "delay",
        lambda *args, **kwargs: queued.append((args, kwargs)),
    )
    identity = uuid4()
    getattr(importlib.import_module("verboflex.services." + module), function)(identity)
    assert queued == [((str(identity),), {})]
    assert len(inspect.signature(worker.run).parameters) == 1
    assert (
        worker.serializer == "json"
        and worker.ignore_result
        and worker.acks_late
        and worker.reject_on_worker_lost
    )


def test_uuid_workers_reject_unknown_identity_before_opening_provider(monkeypatch):
    from verboflex.worker import submission_tasks

    called = []

    async def record(identity, **kwargs):
        assert isinstance(identity, UUID)
        called.append((identity, kwargs))

    monkeypatch.setattr(submission_tasks, "_execute", record)
    monkeypatch.setattr(submission_tasks, "_submit", record)
    for task in (
        submission_tasks.run_submission_review,
        submission_tasks.run_submission,
        submission_tasks.run_submission_reconciliation,
    ):
        task.run("not-a-uuid")
    assert called == []
    identity = uuid4()
    submission_tasks.run_submission.run(str(identity))
    submission_tasks.run_submission_reconciliation.run(str(identity))
    assert called == [(identity, {}), (identity, {"reconcile": True})]


def test_public_submission_dtos_cannot_serialize_private_proofs_or_arbitrary_receipts():
    from verboflex.schemas import submissions

    protected = {
        "prepared_payload",
        "original_prepared_payload",
        "original_bytes",
        "content",
        "access_token",
        "ciphertext",
        "connection_generation",
        "actor_token_version",
        "execution_fence",
    }
    for name in (
        "SubmissionBatchResponse",
        "SubmissionReviewResponse",
        "ChangeSetHistoryPage",
        "ChangeSetValuesPage",
        "ChangeSetFilesPage",
        "ChangeSetActivityPage",
    ):
        schema = getattr(submissions, name).model_json_schema()
        for model in [schema, *schema.get("$defs", {}).values()]:
            if model.get("type") == "object":
                assert model.get("additionalProperties") is False, name
                assert not set(model.get("properties", {})) & protected, name
    receipt = submissions.ChangeSetActivityResponse.model_json_schema()["properties"]["receipt"]
    assert "discriminator" in receipt["anyOf"][0]


def test_storage_proof_and_file_bytes_are_deferred_and_not_implicit_read_columns():
    from verboflex.models.submission import (
        ChangeSet,
        ChangeSetFile,
        ChangeSetItem,
        ChangeSetProof,
        SubmissionReview,
    )

    for model, names in [
        (SubmissionReview, ("prepared_payload",)),
        (ChangeSet, ("original_prepared_payload",)),
        (ChangeSetProof, ("prepared_payload",)),
        (ChangeSetFile, ("original_bytes", "content")),
        (ChangeSetItem, ("members",)),
    ]:
        assert all(orm_inspect(model).attrs[name].deferred for name in names)


def test_edge_matrix_covers_exactly_15_source_probes_and_real_executable_selectors():
    data = json.loads(MATRIX.read_text())
    probes = json.loads(
        (ROOT / ".planning/phases/07-change-sets-and-pull-requests/07-EDGE-PROBE.json").read_text()
    )["items"]
    assert len(data["edges"]) == len(probes) == 15
    assert {(r["requirement_id"], r["category"]) for r in data["edges"]} == {
        (r["requirement_id"], r["category"]) for r in probes
    }
    assert len({r["id"] for r in data["edges"]}) == 15
    gate_path = ".planning/phases/07-change-sets-and-pull-requests/07-GATE.json"
    assert gate_path in data["execution_note"]
    assert "static contract" in data["execution_note"]
    for row in data["edges"]:
        assert row["test_nodes"] and row["smoke"]["status"] == "requires_current_gate"
        for selector in row["test_nodes"]:
            path, function = selector.split("::", 1)
            content = (ROOT / path).read_text()
            if path.endswith(".py"):
                tree = ast.parse(content)
                assert any(
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == function
                    for node in tree.body
                ), selector
            else:
                assert path.endswith((".test.ts", ".test.tsx"))
                assert f"it({json.dumps(function)}," in content, selector
    ordering = next(row for row in data["edges"] if row["id"] == "PR-05-ordering")
    assert "new review IDs" in ordering["contract"] and "reserved" in ordering["contract"]
