"""Non-secret manifest CLI contracts using the owned PostgreSQL fixture."""

import json
from datetime import UTC, datetime, timedelta

from tests.integration.test_database_maintenance import (  # noqa: F401
    maintenance_factory,
    seed_staging,
)
from verboflex import cli


def test_cli_manifest_digest_and_apply(maintenance_factory, tmp_path, monkeypatch, capsys):  # noqa: F811
    seed_staging(maintenance_factory)
    future = datetime.now(UTC) + timedelta(days=8)

    class Clock:
        @staticmethod
        def now(zone):
            return future

    monkeypatch.setattr(cli, "datetime", Clock)
    path = tmp_path / "manifest.json"
    assert (
        cli.main(
            ["maintenance", "dry-run", "--temporary", "--output", str(path)],
            session_provider=maintenance_factory,
            password_reader=lambda _: (_ for _ in ()).throw(AssertionError()),
        )
        == 0
    )
    manifest = json.loads(path.read_text())
    assert "translated_text" not in path.read_text()
    assert (
        cli.main(
            ["maintenance", "apply", "--manifest", str(path), "--digest", "0" * 64],
            session_provider=maintenance_factory,
        )
        == 1
    )
    assert (
        cli.main(
            ["maintenance", "apply", "--manifest", str(path), "--digest", manifest["digest"]],
            session_provider=maintenance_factory,
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["deleted_rows"] == 2
