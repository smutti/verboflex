# ruff: noqa: SIM117
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "database_backup", Path(__file__).resolve().parents[2] / "ops/database_backup.py"
)
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.config = self.directory / "private.env"
        self.config.write_text(
            "VERBOFLEX_POSTGRES_PASSWORD=do-not-log\nVERBOFLEX_JWT_SECRET_KEY=do-not-log\nVERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING=do-not-log\n"
        )
        self.environment = patch.dict(
            os.environ,
            {
                "PGDATABASE": "verboflex",
                "PGPASSWORD": "never-in-argv",
                "BACKUP_CONFIG_FILE": str(self.config),
                "BACKUP_KEEP_COUNT": "2",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def bundle(self, day):
        name = f"vf-202610{day:02d}T030000Z-abcdef01"
        directory = self.directory / name
        directory.mkdir()
        (directory / "database.dump").write_bytes(b"archive")
        (directory / "deployment.env").write_text("SECRET=not-public")
        data = {
            "format_version": 1,
            "id": name,
            "verified": True,
            "created_at": f"2026-10-{day:02d}T03:00:00+00:00",
            "files": {
                n: backup.digest(directory / n)
                for n in ("database.dump", "deployment.env")
            },
            "inventory": {
                "schema_revisions": ["0033_repository_providers"],
                "row_counts": {"products": 5},
            },
        }
        backup.atomic_json(directory / "manifest.json", data)
        return directory, data

    def test_schedule_daily_utc_and_catchup(self):
        _, entry = self.bundle(2)
        moment = datetime(2026, 10, 3, 2, 59, tzinfo=timezone.utc)
        self.assertFalse(backup.due([entry], moment, 3))
        self.assertTrue(backup.due([entry], moment.replace(hour=3), 3))
        self.assertTrue(backup.due([], moment, 3))
        self.assertTrue(backup.due([entry], moment.replace(day=5), 3))

    def test_retention_only_removes_old_verified_owned_bundles(self):
        old, _ = self.bundle(1)
        middle, _ = self.bundle(2)
        newest, _ = self.bundle(3)
        foreign = self.directory / "manual-backup.dump"
        foreign.write_text("keep")
        partial = self.directory / ".partial-old"
        partial.mkdir()
        backup.prune(self.directory, 2)
        self.assertFalse(old.exists())
        self.assertTrue(
            middle.exists()
            and newest.exists()
            and foreign.exists()
            and partial.exists()
        )

    def test_retention_keeps_extra_operator_files(self):
        old, _ = self.bundle(1)
        (old / "notes.txt").write_text("operator owned")
        self.bundle(2)
        backup.prune(self.directory, 1)
        self.assertTrue(old.exists())

    def test_retention_never_deletes_corrupt_archive(self):
        old, _ = self.bundle(1)
        (old / "database.dump").write_bytes(b"corrupt")
        self.bundle(2)
        with self.assertRaises(backup.BackupError):
            backup.prune(self.directory, 1)
        self.assertTrue(old.exists())

    def test_failed_backup_preserves_previous_bundles(self):
        old, _ = self.bundle(1)
        with patch.object(
            backup, "backup", side_effect=RuntimeError("secret provider error")
        ):
            with self.assertRaisesRegex(backup.BackupError, "backup_internal_error"):
                backup.run_backup(self.directory)
        self.assertTrue(old.exists())
        status = (self.directory / "status.json").read_text()
        self.assertNotIn("secret", status)
        self.assertFalse(backup.health(self.directory))

    def test_invalid_bundle_or_changed_secret_prevents_restore(self):
        directory, _ = self.bundle(1)
        (directory / "deployment.env").write_text("OTHER!=not-public")
        with patch.object(backup, "command") as command:
            with self.assertRaises(backup.BackupError):
                backup.verified_restore(directory, "vf_restore_test")
        command.assert_not_called()

    def test_symlink_archive_prevents_restore(self):
        directory, _ = self.bundle(1)
        (directory / "database.dump").unlink()
        (directory / "database.dump").symlink_to(self.config)
        with self.assertRaises(backup.BackupError):
            backup.metadata(directory, checksums=True)

    def test_restore_refuses_live_and_non_literal_targets(self):
        for target in (
            "verboflex",
            "postgres",
            "postgresql://host/db",
            "vf_restore_x;DROP DATABASE verboflex",
        ):
            with (
                self.subTest(target=target),
                patch.object(backup, "command") as command,
            ):
                with self.assertRaises(backup.BackupError):
                    backup.restore_archive(Path("x"), target)
                command.assert_not_called()

    def test_existing_target_is_never_restored_or_dropped(self):
        with patch.object(
            backup, "command", side_effect=backup.BackupError("database_command_failed")
        ) as command:
            with self.assertRaises(backup.BackupError):
                backup.restore_archive(
                    Path("x"), "vf_restore_existing", disposable=True
                )
        self.assertEqual(command.call_count, 1)
        self.assertEqual(command.call_args.args[0][0], "createdb")

    def test_rehearsal_drops_only_its_created_database_even_on_failure(self):
        calls = []

        def command(args, **kwargs):
            calls.append(args)
            if args[0] == "pg_restore":
                raise backup.BackupError("database_command_failed")
            return ""

        with patch.object(backup, "command", side_effect=command):
            with self.assertRaises(backup.BackupError):
                backup.restore_archive(
                    Path("x"), "vf_restore_generated", disposable=True
                )
        self.assertEqual([c[0] for c in calls], ["createdb", "pg_restore", "dropdb"])
        self.assertEqual(calls[-1][-1], "vf_restore_generated")
        self.assertIn("--single-transaction", calls[1])
        self.assertNotIn("--disable-triggers", calls[1])

    def test_operator_restore_preserves_new_target_and_checks_inventory(self):
        directory, data = self.bundle(1)
        with (
            patch.object(backup, "command") as command,
            patch.object(backup, "inventory", return_value=data["inventory"]),
        ):
            self.assertEqual(
                backup.verified_restore(directory, "vf_restore_recovery"),
                data["inventory"],
            )
        self.assertEqual(
            [c.args[0][0] for c in command.call_args_list], ["createdb", "pg_restore"]
        )

    def test_inventory_mismatch_fails_rehearsal(self):
        directory, _ = self.bundle(1)
        with (
            patch.object(backup, "command") as command,
            patch.object(backup, "inventory", return_value={}),
        ):
            with self.assertRaisesRegex(
                backup.BackupError, "restore_inventory_mismatch"
            ):
                backup.verified_restore(directory)
        self.assertEqual(command.call_args.args[0][0], "dropdb")

    def test_concurrent_operations_are_refused(self):
        with backup.operation_lock(self.directory):
            with self.assertRaisesRegex(
                backup.BackupError, "operation_already_running"
            ):
                with backup.operation_lock(self.directory):
                    self.fail("second lock acquired")

    def test_health_requires_success_and_freshness(self):
        directory, _ = self.bundle(1)
        backup.atomic_json(self.directory / "status.json", {"ok": True})
        with patch.object(
            backup, "now", return_value=datetime(2026, 10, 2, 3, tzinfo=timezone.utc)
        ):
            self.assertTrue(backup.health(self.directory))
        with patch.object(
            backup, "now", return_value=datetime(2026, 10, 3, 3, tzinfo=timezone.utc)
        ):
            self.assertFalse(backup.health(self.directory))
        (directory / "manifest.json").write_text("malformed")
        self.assertFalse(backup.health(self.directory))

    def test_password_never_enters_command_arguments_or_error(self):
        with patch.object(
            subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 1, b"", b"never-in-argv"),
        ) as run:
            with self.assertRaisesRegex(
                backup.BackupError, "^database_command_failed$"
            ):
                backup.command(["pg_dump", "-w"])
        self.assertNotIn("never-in-argv", str(run.call_args.args))
        self.assertEqual(run.call_args.kwargs["env"]["PGPASSWORD"], "never-in-argv")

    def test_backup_publishes_only_after_successful_restore(self):
        def command(args, **kwargs):
            if args[0] == "pg_dump":
                Path(args[-1]).write_bytes(b"real-shaped-archive")
            return ""

        expected = {
            "schema_revisions": ["0033_repository_providers"],
            "row_counts": {"products": 5},
        }
        with (
            patch.object(backup, "command", side_effect=command),
            patch.object(backup, "restore_archive", return_value=expected),
        ):
            data = backup.run_backup(self.directory)
        self.assertEqual(
            backup.metadata(self.directory / data["id"], checksums=True)["inventory"],
            expected,
        )
        self.assertEqual(
            (self.directory / data["id"] / "deployment.env").stat().st_mode & 0o777,
            0o600,
        )
        self.assertFalse(list(self.directory.glob(".partial-*")))

    def test_changing_keyring_during_backup_prevents_publication(self):
        def command(args, **kwargs):
            Path(args[-1]).write_bytes(b"archive")
            return ""

        def restore(*args, **kwargs):
            self.config.write_text(
                "VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING=rotated\n"
            )
            return {"schema_revisions": ["0033"], "row_counts": {"products": 5}}

        with (
            patch.object(backup, "command", side_effect=command),
            patch.object(backup, "restore_archive", side_effect=restore),
        ):
            with self.assertRaisesRegex(
                backup.BackupError, "deployment_config_changed_during_backup"
            ):
                backup.run_backup(self.directory)
        self.assertEqual(backup.bundles(self.directory), [])

    def test_backup_requires_decryption_configuration(self):
        self.config.write_text("VERBOFLEX_POSTGRES_PASSWORD=x\n")
        with patch.object(backup, "command") as command:
            with self.assertRaisesRegex(
                backup.BackupError, "deployment_config_incomplete"
            ):
                backup.run_backup(self.directory)
        command.assert_not_called()

    def test_malformed_manifest_shape_fails_without_database_call(self):
        directory, data = self.bundle(1)
        data["files"] = ["database.dump", "deployment.env"]
        (directory / "manifest.json").write_text(json.dumps(data))
        with patch.object(backup, "command") as command:
            with self.assertRaises(backup.BackupError):
                backup.verified_restore(directory)
        command.assert_not_called()

    def test_failed_rehearsal_never_promotes_or_prunes(self):
        old, _ = self.bundle(1)

        def command(args, **kwargs):
            Path(args[-1]).write_bytes(b"archive")
            return ""

        with (
            patch.object(backup, "command", side_effect=command),
            patch.object(
                backup,
                "restore_archive",
                side_effect=backup.BackupError("database_command_failed"),
            ),
            patch.object(backup, "prune") as prune,
        ):
            with self.assertRaises(backup.BackupError):
                backup.run_backup(self.directory)
        self.assertTrue(old.exists())
        self.assertEqual(len(backup.bundles(self.directory)), 1)
        prune.assert_not_called()
        self.assertFalse(list(self.directory.glob(".partial-*")))


if __name__ == "__main__":
    unittest.main()
