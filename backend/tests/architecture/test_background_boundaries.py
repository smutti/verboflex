"""Fail-closed architecture checks for the HTTP/worker process boundary."""

import ast
import inspect
from collections.abc import Mapping
from pathlib import Path

from verboflex.worker.celery_app import app
from verboflex.worker.import_tasks import run_import_job

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BACKEND_ROOT.parent
API_ROOT = BACKEND_ROOT / "src" / "verboflex" / "api"


def _api_trees() -> list[tuple[Path, ast.Module]]:
    """Parse every API module and fail if any source cannot be inspected."""
    trees: list[tuple[Path, ast.Module]] = []
    for path in sorted(API_ROOT.rglob("*.py")):
        trees.append((path, ast.parse(path.read_text(), filename=str(path))))
    assert trees, "API architecture check examined no modules"
    return trees


def _assert_no_worker_boundary_violations(
    sources: Mapping[str, str | ast.Module],
) -> None:
    """Reject imports, task dispatch, and task bodies from HTTP-owned modules."""
    violations: list[str] = []
    forbidden_bodies = {
        "run_import_job",
        "reconcile_stale_import_jobs",
        "reconcile_stale_imports",
    }
    for label, source in sources.items():
        tree = ast.parse(source, filename=label) if isinstance(source, str) else source
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("verboflex.worker"):
                        violations.append(f"{label}:{node.lineno}: imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").startswith("verboflex.worker"):
                    violations.append(f"{label}:{node.lineno}: imports {node.module}")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"delay", "apply_async", "run"}
            ):
                violations.append(f"{label}:{node.lineno}: calls .{node.func.attr}()")
            elif isinstance(node, ast.Name) and node.id in forbidden_bodies:
                violations.append(f"{label}:{node.lineno}: reaches {node.id}")

    assert violations == []


def test_fastapi_modules_never_import_or_call_worker_task_bodies() -> None:
    """Keep enqueue/worker mechanics entirely outside HTTP route modules."""
    _assert_no_worker_boundary_violations({str(path): tree for path, tree in _api_trees()})


def test_production_celery_configuration_cannot_execute_tasks_eagerly() -> None:
    """Require JSON transport and a genuinely out-of-process execution mode."""
    assert app.conf.task_always_eager is False
    assert app.conf.task_serializer == "json"
    assert app.conf.result_serializer == "json"
    assert set(app.conf.accept_content) == {"json"}
    assert set(app.conf.result_accept_content) == {"json"}


def test_compose_runs_backend_and_worker_as_distinct_commands() -> None:
    """Retain one API process and one separately managed Celery process."""
    compose = (REPOSITORY_ROOT / "docker-compose.yml").read_text()

    assert '"uvicorn", "verboflex.main:app"' in compose
    assert '"celery", "-A", "verboflex.worker.celery_app", "worker"' in compose
    assert "task_always_eager" not in compose


def test_import_background_boundary_registers_run_and_watchdog_without_route_dispatch() -> None:
    """Import execution and recovery stay named worker commands behind the service seam."""
    assert "verboflex.worker.import_tasks" in app.conf.include
    assert "verboflex.import.run" in app.conf.task_annotations
    assert app.conf.beat_schedule["import-stale-execution-watchdog"]["task"] == (
        "verboflex.import.reconcile_stale_jobs"
    )
    _assert_no_worker_boundary_violations({str(path): tree for path, tree in _api_trees()})


def test_import_worker_keeps_uuid_only_transport_and_parses_before_finalization() -> None:
    """Canonical values and source bytes stay in-process and never enter Redis."""
    from verboflex.services import import_jobs

    assert tuple(inspect.signature(run_import_job).parameters) == ("import_id",)
    task_source = inspect.getsource(run_import_job)
    assert "source" not in tuple(inspect.signature(run_import_job).parameters)
    assert "canonical" not in task_source

    process_tree = ast.parse(inspect.getsource(import_jobs._process_import))
    called_names = {
        node.func.id
        for node in ast.walk(process_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "parse_canonical_mapping_quarantining_duplicates" in called_names
    assert "stage_translation_parse" in called_names
