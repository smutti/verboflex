"""Intended assertion evidence, private subprocess limits and exact restoration."""

import asyncio
import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location(
        "verify_phase7_mutants", ROOT / "tools/verify_phase7_mutants.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def probe(runner):
    return runner.Mutation(
        "authority",
        "protected.py",
        "VALUE = 1",
        "VALUE = 0",
        "test_probe.py::test_authority",
        "pytest",
        "assert protected.VALUE == 1",
    )


def test_commit_send_binds_expected_parent_for_provider_cas():
    from tests.integration.test_bitbucket_write_adapter import PARENT, Provider, with_provider

    provider = Provider()
    outcome = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_commit(object(), intent=provider.intent)
        )
    )
    # The transport intentionally sanitizes callback errors. Inspect the actual
    # recorded multipart fields so a missing CAS fails this precise assertion.
    assert provider.fields.get("parents") == PARENT
    assert outcome.state == "verified"


@pytest.mark.parametrize(
    "failure", ["setup", "wrong-assertion", "skipped", "wrong-test", "missing", "wrong-exit"]
)
def test_exit_one_without_the_named_assertion_is_rejected(runner, tmp_path, failure):
    report = tmp_path / "report.xml"
    content = '<testsuites><testsuite tests="1"><testcase name="test_authority">'
    code = 1
    if failure == "setup":
        content += '<error message="fixture unavailable">assert protected.VALUE == 1</error>'
    elif failure == "wrong-assertion":
        content += "<failure>AssertionError: assert unrelated == 1</failure>"
    elif failure == "skipped":
        content += "<skipped />"
    else:
        content += "<failure>AssertionError: assert protected.VALUE == 1</failure>"
    content += "</testcase></testsuite></testsuites>"
    if failure == "wrong-test":
        content = content.replace('name="test_authority"', 'name="test_other"')
    if failure == "wrong-exit":
        code = 2
    if failure != "missing":
        report.write_text(content)
    with pytest.raises(ValueError):
        runner.validate_report(probe(runner), report, code, killed=True)


def test_real_behavioral_failure_restores_original_bytes(runner, tmp_path):
    protected = tmp_path / "protected.py"
    protected.write_bytes(b"VALUE = 1\r\n")
    (tmp_path / "test_probe.py").write_text(
        "import protected\ndef test_authority():\n    assert protected.VALUE == 1\n"
    )
    original = protected.read_bytes()
    result = runner.run_mutation(probe(runner), root=tmp_path)
    assert result["status"] == "killed" and result["test"] == "test_probe.py::test_authority"
    assert protected.read_bytes() == original


def test_wrong_real_assertion_fails_closed_and_restores(runner, tmp_path):
    protected = tmp_path / "protected.py"
    protected.write_text("VALUE = 1\n")
    (tmp_path / "test_probe.py").write_text(
        "import protected\ndef test_authority():\n    assert protected.VALUE > 0\n"
    )
    original = protected.read_bytes()
    with pytest.raises(ValueError):
        runner.run_mutation(probe(runner), root=tmp_path)
    assert protected.read_bytes() == original


@pytest.mark.parametrize("error", [KeyboardInterrupt, ValueError])
def test_interrupted_or_broken_probe_restores_without_masking_error(
    runner, tmp_path, monkeypatch, error
):
    protected = tmp_path / "protected.py"
    protected.write_bytes(b"VALUE = 1\r\n")
    original = protected.read_bytes()

    def interrupt(_mutation, _root, _timeout, *, killed):
        if killed:
            assert protected.read_text() == "VALUE = 0\n"
            raise error("private provider detail")

    monkeypatch.setattr(runner, "run_probe", interrupt)
    with pytest.raises(error):
        runner.run_mutation(probe(runner), root=tmp_path)
    assert protected.read_bytes() == original


def test_failed_baseline_never_mutates_source(runner, tmp_path):
    protected = tmp_path / "protected.py"
    protected.write_text("VALUE = 1\n")
    (tmp_path / "test_probe.py").write_text(
        "import pytest\n@pytest.fixture\ndef missing():\n"
        "    raise RuntimeError('setup unavailable')\n"
        "def test_authority(missing):\n    assert False\n"
    )
    with pytest.raises(ValueError):
        runner.run_mutation(probe(runner), root=tmp_path)
    assert protected.read_text() == "VALUE = 1\n"


@pytest.mark.parametrize("failure", [None, "setup", "wrong-assertion", "skipped", "extra-failure"])
def test_vitest_requires_the_exact_executed_assertion(runner, tmp_path, failure):
    mutation = replace(probe(runner), engine="vitest", assertion="expected unsafe to be null")
    selected = {
        "fullName": "test_authority",
        "status": "failed",
        "failureMessages": ["AssertionError: expected unsafe to be null"],
    }
    data = {
        "success": False,
        "numFailedTests": 1,
        "numPassedTests": 0,
        "testResults": [{"message": "", "assertionResults": [selected]}],
    }
    if failure == "setup":
        data["testResults"][0]["message"] = "setup failed"
    elif failure == "wrong-assertion":
        selected["failureMessages"] = ["AssertionError: expected unrelated value"]
    elif failure == "skipped":
        selected["status"] = "skipped"
    elif failure == "extra-failure":
        data["testResults"][0]["assertionResults"].append(
            {"fullName": "unrelated", "status": "failed"}
        )
    report = tmp_path / "result.json"
    report.write_text(json.dumps(data))
    if failure is None:
        runner.validate_report(mutation, report, 1, killed=True)
    else:
        with pytest.raises(ValueError):
            runner.validate_report(mutation, report, 1, killed=True)


@pytest.mark.parametrize("limit", ["time", "output"])
def test_subprocess_limits_are_closed_and_private(runner, tmp_path, monkeypatch, capsys, limit):
    monkeypatch.setattr(runner, "MAX_PRIVATE_BYTES", 4096)
    script = (
        "import time; print('private provider detail',flush=True); time.sleep(10)"
        if limit == "time"
        else "print('private provider detail'*10000)"
    )
    with pytest.raises(ValueError, match="budget"):
        runner.execute((sys.executable, "-c", script), tmp_path, 0.1)
    assert capsys.readouterr() == ("", "")


def test_shared_lock_prevents_overlapping_mutation_runners(runner, tmp_path):
    with (
        runner.mutation_lock(tmp_path),
        pytest.raises(BlockingIOError),
        runner.mutation_lock(tmp_path),
    ):
        pytest.fail("overlapping owner entered")
    with runner.mutation_lock(tmp_path):
        pass


def test_seven_targets_are_exact_syntactically_valid_and_test_backed(runner):
    assert len(runner.MUTATIONS) == len({m.name for m in runner.MUTATIONS}) == 7
    for mutation in runner.MUTATIONS:
        source = (ROOT / mutation.path).read_text()
        assert source.count(mutation.original) == 1, mutation.name
        changed = source.replace(mutation.original, mutation.replacement, 1)
        if mutation.path.endswith(".py"):
            runner.ast.parse(changed)
        assert (ROOT / mutation.test.split("::", 1)[0]).is_file()
        assert mutation.assertion


def test_cli_success_evidence_is_closed_and_content_free(runner, tmp_path, monkeypatch, capsys):
    (tmp_path / "protected.py").write_text("VALUE = 1\n")
    inventory = tuple(replace(probe(runner), name=f"check-{index}") for index in range(7))
    monkeypatch.setattr(runner, "MUTATIONS", inventory)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(sys, "argv", ["verify_phase7_mutants.py"])
    monkeypatch.setattr(
        runner,
        "run_mutation",
        lambda mutation: {
            "name": mutation.name,
            "status": "killed",
            "test": mutation.test,
            "duration_seconds": 0.1,
        },
    )
    assert runner.main() == 0
    output = capsys.readouterr()
    assert output.err == "" and len(output.out.splitlines()) == 1
    evidence = json.loads(output.out.removeprefix("phase7 mutants evidence: "))
    assert evidence == {
        "status": "pass",
        "killed": 7,
        "survived": 0,
        "source_restored": True,
        "mutants": [runner.run_mutation(m) for m in inventory],
    }
    assert "VALUE" not in output.out
