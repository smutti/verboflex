"""The dashboard fixture runner must never seed or remove shared resources."""

import importlib.util
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "dashboard_smoke", Path(__file__).parents[1] / "dashboard_smoke.py"
)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


@pytest.fixture
def runtime():
    result = smoke.OwnedRuntime()
    yield result
    if result.path.exists():
        shutil.rmtree(result.path)


@pytest.mark.parametrize("mode", [{}, {"bilingual": True}, {"multilingual": True}])
def test_seed_rejects_missing_owned_marker_before_database_access(
    runtime, monkeypatch, mode
):
    (runtime.path / "owner").write_text("verboflex")
    monkeypatch.setattr(
        runtime, "postgres_url", lambda: pytest.fail("must not touch database")
    )
    with pytest.raises(RuntimeError, match="Unowned"):
        smoke.seed(runtime, **mode)


def test_cleanup_refuses_shared_project_before_any_command(runtime, monkeypatch):
    runtime.project = "verboflex"
    monkeypatch.setattr(
        smoke.subprocess, "run", lambda *a, **k: pytest.fail("must not run Docker")
    )
    with pytest.raises(RuntimeError, match="Unowned"):
        runtime.cleanup()


def test_database_container_must_carry_this_compose_project(runtime, monkeypatch):
    monkeypatch.setattr(runtime, "compose", lambda *args: "some-container")
    monkeypatch.setattr(runtime, "command", lambda *args: "verboflex")
    with pytest.raises(RuntimeError, match="Unowned database container"):
        runtime.postgres_url()


def test_only_exact_owned_resources_are_removed(runtime, monkeypatch):
    runtime.configure()
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(
            returncode=0,
            stdout="image-id" if args[1:3] == ("images", "-q") else "",
            stderr="",
        )

    monkeypatch.setattr(smoke.subprocess, "run", run)
    runtime.cleanup()
    assert not runtime.path.exists()
    assert calls[0][1] == "compose"
    assert calls[0][calls[0].index("--project-name") + 1] == runtime.project
    assert calls[0][-3:] == ("down", "--volumes", "--remove-orphans")
    removals = [call[-1] for call in calls if call[1:3] == ("image", "rm")]
    assert removals == [runtime.project + "-backend", runtime.project + "-frontend"]
    assert all("prune" not in call for call in calls)


def test_configuration_is_loopback_only_and_has_no_provider_or_dispatcher(runtime):
    runtime.configure()
    config = json.loads(runtime.compose_file.read_text())
    assert set(config["services"]) == {"postgres", "redis", "backend", "frontend"}
    assert all(
        port.startswith("127.0.0.1:")
        for service in config["services"].values()
        for port in service.get("ports", [])
    )
    assert all(
        "BITBUCKET" not in key for key in config["services"]["backend"]["environment"]
    )
    assert runtime.backend.startswith("http://localhost:")
    assert config["networks"]["default"] == {"name": runtime.project + "_default"}


@pytest.mark.parametrize("mode", ["multilingual", "bilingual"])
def test_multilingual_dispatch_and_failure_still_cleanup(
    runtime, monkeypatch, tmp_path, mode
):
    runtime.configure()
    calls = []
    monkeypatch.setattr(smoke, "OwnedRuntime", lambda: runtime)
    monkeypatch.setattr(smoke, "EVIDENCE", tmp_path)
    monkeypatch.setattr(runtime, "compose", lambda *a, **k: "")
    monkeypatch.setattr(runtime, "configure", lambda: None)
    monkeypatch.setattr(runtime, "cleanup", lambda: calls.append("cleanup"))

    def seed(owned, **kwargs):
        assert owned is runtime
        assert kwargs[mode] is True
        return {"users": {}}

    def command(*args, **kwargs):
        assert args[2] == mode
        assert "dashboard_smoke_browser.mjs" in args[1]
        assert (runtime.path / "fixture.json").stat().st_mode & 0o777 == 0o600
        raise RuntimeError("browser failure")

    monkeypatch.setattr(smoke, "seed", seed)
    monkeypatch.setattr(runtime, "command", command)
    with pytest.raises(RuntimeError, match="browser failure"):
        smoke.run(mode)
    assert calls == ["cleanup"]
    report = json.loads((tmp_path / f"{mode}-result.json").read_text())
    assert report["passed"] is False
    assert report["project"] == runtime.project
