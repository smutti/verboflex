"""Durable UUID-only dispatch; repository builds belong to an isolated runner."""

import hashlib
import os
import struct
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from verboflex.core.config import get_settings
from verboflex.db.session import SessionFactory
from verboflex.localization.code_keys.locations import locate_text
from verboflex.models.screenshot import ScreenshotJob
from verboflex.services.screenshots import authority_current, encode_inputs
from verboflex.worker.celery_app import app

MAX_IMAGE_BYTES = 8 * 1024 * 1024


def validate_png(content: bytes) -> None:
    if (
        not 45 <= len(content) <= MAX_IMAGE_BYTES
        or content[:8] != b"\x89PNG\r\n\x1a\n"
        or content[12:16] != b"IHDR"
        or content[-8:-4] != b"IEND"
    ):
        raise ValueError("Invalid screenshot output")
    width, height = struct.unpack(">II", content[16:24])
    if not 1 <= width <= 8192 or not 1 <= height <= 8192 or width * height > 20_000_000:
        raise ValueError("Screenshot dimensions exceed limits")


def _render(
    inputs: dict[str, object], *, web: bool = False
) -> tuple[bytes, dict[str, object] | None]:
    settings = get_settings()
    command = settings.web_screenshot_runner_command if web else settings.screenshot_runner_command
    if not command:
        raise ValueError("Capture runner unavailable")
    with tempfile.TemporaryDirectory(prefix="verboflex-capture-") as directory:
        request = Path(directory) / "input.json"
        output = Path(directory) / "image.png"
        # Location metadata belongs to the worker, keeping existing reviewed runners compatible.
        request.write_bytes(
            encode_inputs({key: value for key, value in inputs.items() if key != "target_key"})
        )
        # The deployment command is a trusted isolation adapter. It must start a
        # sandbox/remote runner, never execute repository code in this process.
        environment = {name: os.environ[name] for name in ("PATH", "TMPDIR") if name in os.environ}
        # Build output is untrusted, may contain secrets and has no byte bound.
        # It is never exposed as a diagnostic, so discard it without a disk spool.
        subprocess.run(
            [
                *command,
                "--input",
                str(request),
                "--output",
                str(output),
                "--timeout",
                str(settings.screenshot_timeout_seconds),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
            timeout=settings.screenshot_timeout_seconds + 20,
            check=True,
        )
        if not output.is_file() or output.is_symlink() or output.stat().st_size > MAX_IMAGE_BYTES:
            raise ValueError("Capture runner did not produce a bounded image")
        content = output.read_bytes()
        validate_png(content)
        receipt = None
        if web:
            from verboflex.schemas.screenshots import WebCaptureReceipt

            metadata = output.with_suffix(".json")
            if not metadata.is_file() or metadata.is_symlink() or metadata.stat().st_size > 131072:
                raise ValueError("Web capture receipt unavailable")
            verified = WebCaptureReceipt.model_validate_json(metadata.read_bytes())
            if (
                verified.input_digest != hashlib.sha256(request.read_bytes()).hexdigest()
                or verified.image_digest != hashlib.sha256(content).hexdigest()
            ):
                raise ValueError("Web capture receipt mismatch")
            request_data = cast(dict[str, object], inputs["request"])
            if (
                verified.commit != inputs["commit"]
                or verified.scenario_id != request_data["scenario_id"]
                or verified.language != inputs["language"]
                or verified.viewport != request_data["viewport"]
                or verified.source_digest != inputs["source_digest"]
                or verified.manifest_digest != inputs["manifest_digest"]
            ):
                raise ValueError("Web receipt authority mismatch")
            viewport = cast(dict[str, int], inputs["viewport"])
            if struct.unpack(">II", content[16:24]) != (viewport["width"], viewport["height"]):
                raise ValueError("Web image viewport mismatch")
            receipt = verified.model_dump(mode="json")
        return content, receipt


def render(inputs: dict[str, object]) -> bytes:
    return _render(inputs)[0]


def render_web(inputs: dict[str, object]) -> tuple[bytes, dict[str, object]]:
    image, receipt = _render(inputs, web=True)
    assert receipt is not None
    return image, receipt


def execute_capture(job_id: UUID, factory: sessionmaker[Session] = SessionFactory) -> None:
    with factory.begin() as session:
        row = session.scalar(
            select(ScreenshotJob).where(ScreenshotJob.id == job_id).with_for_update()
        )
        if row is None or row.state != "queued":
            return
        if not authority_current(session, row) or row.expires_at <= datetime.now(UTC):
            row.state, row.error_code = "failed", "source_or_access_changed"
            return
        if hashlib.sha256(encode_inputs(row.inputs)).hexdigest() != row.input_digest:
            row.state, row.error_code = "failed", "input_changed"
            return
        row.state, row.updated_at = "rendering", datetime.now(UTC)
        inputs = dict(row.inputs)
    image: bytes | None = None
    location: dict[str, object] | None = None
    failure: str | None = None
    receipt = None
    try:
        if inputs.get("engine") == "web":
            image, receipt = render_web(inputs)
            location = cast(dict[str, object], receipt["location"])
        else:
            image = render(inputs)
    except subprocess.TimeoutExpired:
        failure = "render_timeout"
    except Exception:
        # Build logs may contain repository secrets; keep the public error closed.
        failure = "render_failed"
    if image is not None and failure is None and receipt is None:
        try:
            location = locate_text(image, inputs).model_dump(mode="json")
        except Exception:
            location = {"status": "unavailable", "regions": []}
    with factory.begin() as session:
        row = session.scalar(
            select(ScreenshotJob).where(ScreenshotJob.id == job_id).with_for_update()
        )
        if row is None or row.state != "rendering":
            return
        if not authority_current(session, row):
            failure = "source_or_access_changed"
        row.updated_at = datetime.now(UTC)
        row.error_code = failure
        if failure is None and image is not None:
            row.state, row.image = "succeeded", image
            row.image_digest = hashlib.sha256(image).hexdigest()
            row.location = location
            row.receipt = receipt
        else:
            row.state, row.image = "failed", None
            row.location = None
            row.receipt = None


@app.task(name="verboflex.screenshot.run", acks_late=True, reject_on_worker_lost=True)  # type: ignore[untyped-decorator]
def run_screenshot(job_id: str) -> None:
    execute_capture(UUID(job_id))


@app.task(name="verboflex.screenshot.reconcile")  # type: ignore[untyped-decorator]
def reconcile_screenshots() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    with SessionFactory.begin() as session:
        rows = list(
            session.scalars(
                select(ScreenshotJob)
                .where(
                    (
                        (ScreenshotJob.state == "queued")
                        & (ScreenshotJob.updated_at < now - timedelta(seconds=30))
                    )
                    | (
                        (ScreenshotJob.state == "rendering")
                        & (
                            ScreenshotJob.updated_at
                            < now - timedelta(seconds=settings.screenshot_timeout_seconds + 120)
                        )
                    )
                    | ((ScreenshotJob.expires_at <= now) & (ScreenshotJob.state != "expired")),
                )
                .order_by(ScreenshotJob.updated_at)
                .limit(100)
                .with_for_update(skip_locked=True)
            )
        )
        queued: list[str] = []
        for row in rows:
            if row.expires_at <= now:
                row.state, row.image, row.inputs = "expired", None, {}
                row.location = None
                row.receipt = None
            elif row.state == "rendering" and row.updated_at < now - timedelta(
                seconds=settings.screenshot_timeout_seconds + 120,
            ):
                row.state, row.error_code = "failed", "worker_interrupted"
            elif row.state == "queued":
                if row.created_at < now - timedelta(hours=1):
                    row.state, row.error_code = "failed", "queue_timeout"
                else:
                    row.updated_at = now
                    queued.append(str(row.id))
    for job_id in queued:
        app.send_task("verboflex.screenshot.run", args=[job_id], queue="screenshots")
