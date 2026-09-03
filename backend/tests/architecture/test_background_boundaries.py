"""Fail-closed architecture checks for the HTTP/worker process boundary."""

import ast
from pathlib import Path

from verboflex.worker.celery_app import app

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


def test_fastapi_modules_never_import_or_call_worker_task_bodies() -> None:
    """Keep enqueue/worker mechanics entirely outside HTTP route modules."""
    violations: list[str] = []
    for path, tree in _api_trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("verboflex.worker"):
                        violations.append(f"{path}:{node.lineno}: imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").startswith("verboflex.worker"):
                    violations.append(f"{path}:{node.lineno}: imports {node.module}")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"delay", "apply_async", "run"}
            ):
                violations.append(f"{path}:{node.lineno}: calls .{node.func.attr}()")

    assert violations == []


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
    for path, tree in _api_trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                assert node.id not in {
                    "run_import_job",
                    "reconcile_stale_import_jobs",
                    "reconcile_stale_imports",
                }, f"{path}:{node.lineno}: route reaches an import worker body"
