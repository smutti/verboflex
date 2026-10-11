#!/usr/bin/env python3
"""Kill the closed Phase 5 authority/privacy mutant inventory safely."""

from __future__ import annotations

import argparse
import ast
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = str(ROOT / "backend/.venv/bin/python")
MUTATION_TIMEOUT_SECONDS = 70


@dataclass(frozen=True, slots=True)
class Mutation:
    label: str
    path: str
    original: str
    replacement: str
    command: tuple[str, ...]


def pytest(file: str, name: str) -> tuple[str, ...]:
    return (
        PYTHON,
        "-m",
        "pytest",
        f"backend/tests/{file}::{name}",
        "-q",
        "--import-mode=importlib",
    )


def vitest(file: str, name: str) -> tuple[str, ...]:
    return (
        "npm",
        "--prefix",
        "frontend",
        "test",
        "--",
        "--run",
        file,
        "-t",
        name,
    )


ACCESS = "backend/src/verboflex/auth/translation_access.py"
REVIEWS = "backend/src/verboflex/services/translation_reviews.py"
COMMENTS = "backend/src/verboflex/services/translation_comments.py"
NOTIFICATIONS = "backend/src/verboflex/services/notifications.py"
CURSORS = "backend/src/verboflex/services/signed_cursor.py"
SCHEMAS = "backend/src/verboflex/schemas/notifications.py"

MUTATIONS = (
    Mutation(
        "proposal-version",
        REVIEWS,
        "if proposal is not None and proposal.version != exact_expected_version:",
        "if False:",
        pytest(
            "api/test_translation_reviews.py",
            "test_scalar_proposal_save_preserves_imported_authority",
        ),
    ),
    Mutation(
        "proposal-selector-atomicity",
        REVIEWS,
        "if attempted_identity != current_identity:",
        "if False:",
        pytest(
            "api/test_translation_reviews.py",
            "test_scalar_proposal_save_rejects_viewer_and_foreign_authority",
        ),
    ),
    Mutation(
        "review-role-widening",
        ACCESS,
        "        RoleName.PRODUCT_MANAGER_REVIEWER,\n    )\n)\n_ALLOWED_ROLES",
        "        RoleName.PRODUCT_MANAGER_REVIEWER,\n"
        "        RoleName.TRANSLATOR,\n    )\n)\n_ALLOWED_ROLES",
        pytest(
            "api/test_translation_reviews.py",
            "test_review_transition_enforces_role_matrix_and_never_changes_imported_authority",
        ),
    ),
    Mutation(
        "review-constraint-bypass",
        REVIEWS,
        "ineligible = stale_basis or any(",
        "ineligible = stale_basis and any(",
        pytest(
            "api/test_translation_reviews.py",
            "test_approval_recomputes_current_authority_before_mutation",
        ),
    ),
    Mutation(
        "resolver-bypass",
        ACCESS,
        "group = _resolve_current_group(session, translation_group_id=translation_group_id)",
        "group = get_translation_group(session, group_id=translation_group_id)",
        pytest(
            "auth/test_translation_access.py",
            "test_all_inaccessible_group_conditions_are_indistinguishable",
        ),
    ),
    Mutation(
        "resolver-duplicate-lookup",
        ACCESS,
        "group = _resolve_current_group(session, translation_group_id=translation_group_id)",
        "group = _resolve_current_group(session, translation_group_id=translation_group_id)\n"
        "    group = _resolve_current_group(session, translation_group_id=translation_group_id)",
        pytest("auth/test_translation_access.py", "test_closed_role_action_matrix"),
    ),
    Mutation(
        "resolver-role-widening",
        ACCESS,
        "        RoleName.TRANSLATOR,\n    )\n)\n_REVIEW_ROLES",
        "        RoleName.TRANSLATOR,\n        RoleName.VIEWER,\n    )\n)\n_REVIEW_ROLES",
        pytest("auth/test_translation_access.py", "test_closed_role_action_matrix"),
    ),
    Mutation(
        "resolver-unavailable-distinction",
        ACCESS,
        "raise TranslationGroupAccessUnavailable(TRANSLATION_UNAVAILABLE_MESSAGE) from error",
        'raise TranslationGroupAccessUnavailable("translation missing") from error',
        pytest(
            "auth/test_translation_access.py",
            "test_all_inaccessible_group_conditions_are_indistinguishable",
        ),
    ),
    Mutation(
        "comment-stable-scope",
        COMMENTS,
        "    return select(TranslationComment).where(\n"
        "        TranslationComment.translation_key_id == discussion.translation_key_id,\n"
        "        TranslationComment.scope_id == discussion.scope_id,\n"
        "        TranslationComment.language == discussion.language,\n"
        "    )",
        "    return select(TranslationComment).where(\n"
        "        TranslationComment.language == discussion.language,\n"
        "    )",
        pytest(
            "api/test_translation_comments.py",
            "test_anchor_is_target_centered_bounded_and_scope_private",
        ),
    ),
    Mutation(
        "comment-history-role",
        COMMENTS,
        "is_admin = RoleName.ADMIN in principal.roles",
        "is_admin = True",
        pytest(
            "api/test_translation_comments.py",
            "test_admin_delete_retains_tombstone_and_hides_prior_text_from_non_admins",
        ),
    ),
    Mutation(
        "comment-history-tombstone",
        COMMENTS,
        "body=None if removed else version.body,",
        "body=version.body,",
        pytest(
            "api/test_translation_comments.py",
            "test_admin_delete_retains_tombstone_and_hides_prior_text_from_non_admins",
        ),
    ),
    Mutation(
        "mention-identity",
        COMMENTS,
        "    return tuple(validated)\n\n\ndef _persist_mentions",
        "    return ()\n\n\ndef _persist_mentions",
        pytest(
            "api/test_translation_comments.py",
            "test_structured_mentions_persist_but_plain_at_text_has_no_identity",
        ),
    ),
    Mutation(
        "notification-dedupe",
        COMMENTS,
        '.on_conflict_do_nothing(constraint="uq_notifications_recipient_comment_kind")',
        ".on_conflict_do_update(\n"
        '            constraint="uq_notifications_recipient_comment_kind",\n'
        '            set_={"actor_user_id": actor_id},\n'
        "        )",
        pytest(
            "integration/test_notification_exactly_once.py",
            "test_notification_helper_returns_only_the_recipient_it_inserted",
        ),
    ),
    Mutation(
        "cursor-binding",
        CURSORS,
        "if any(payload.get(key) != value for key, value in expected.items()):",
        "if False:",
        pytest(
            "unit/services/test_signed_cursor.py",
            "test_decode_rejects_every_mismatched_binding",
        ),
    ),
    Mutation(
        "cursor-signature",
        CURSORS,
        "if not hmac.compare_digest(signature, expected_signature):",
        "if False:",
        pytest(
            "unit/services/test_signed_cursor.py",
            "test_malformed_wire_tokens_fail_generically",
        ),
    ),
    Mutation(
        "notification-schema-widening",
        SCHEMAS,
        '    model_config = ConfigDict(\n        extra="forbid",\n        json_schema_extra=',
        '    model_config = ConfigDict(\n        extra="allow",\n        json_schema_extra=',
        pytest(
            "api/test_notifications.py",
            "test_notification_contract_is_closed_registered_and_principal_only",
        ),
    ),
    Mutation(
        "notification-schema-field-omission",
        SCHEMAS,
        "    comment_status: NotificationCommentStatus",
        "    # Mutant omits the required public status field.",
        pytest(
            "api/test_notifications.py",
            "test_list_recent_count_filters_and_closed_projection_are_private",
        ),
    ),
    Mutation(
        "anchor-bound",
        COMMENTS,
        ".order_by(TranslationComment.created_at.desc(), TranslationComment.id.desc())\n"
        "            .limit(ANCHOR_SIDE_SIZE)",
        ".order_by(TranslationComment.created_at.desc(), TranslationComment.id.desc())\n"
        "            .limit(ANCHOR_SIDE_SIZE + 100)",
        pytest(
            "api/test_translation_comments.py",
            "test_anchor_is_target_centered_bounded_and_scope_private",
        ),
    ),
    Mutation(
        "anchor-group",
        COMMENTS,
        "target = session.scalar("
        "_base_query(discussion).where(TranslationComment.id == comment_id))",
        "target = session.scalar("
        "select(TranslationComment).where(TranslationComment.id == comment_id))",
        pytest(
            "api/test_translation_comments.py",
            "test_anchor_is_target_centered_bounded_and_scope_private",
        ),
    ),
    Mutation(
        "origin-read-recipient",
        NOTIFICATIONS,
        "            Notification.kind == NotificationKind.MENTION.value,\n"
        "            Notification.recipient_user_id == principal.user_id,",
        "            Notification.kind == NotificationKind.MENTION.value,\n"
        "            Notification.recipient_user_id != principal.user_id,",
        pytest(
            "api/test_notifications.py",
            "test_manual_and_origin_reads_are_idempotent_and_never_cross_recipient",
        ),
    ),
    Mutation(
        "origin-read-kind",
        NOTIFICATIONS,
        "            Notification.originating_comment_id == comment_id,\n"
        "            Notification.kind == NotificationKind.MENTION.value,",
        "            Notification.originating_comment_id == comment_id,\n"
        "            Notification.kind != NotificationKind.MENTION.value,",
        pytest(
            "api/test_notifications.py",
            "test_manual_and_origin_reads_are_idempotent_and_never_cross_recipient",
        ),
    ),
    Mutation(
        "origin-read-group",
        NOTIFICATIONS,
        "            mode=TranslationGroupAccessMode.READ,\n        )\n"
        "    except TranslationGroupAccessUnavailable as error:",
        "            mode=TranslationGroupAccessMode.COMMENT,\n        )\n"
        "    except TranslationGroupAccessUnavailable as error:",
        pytest(
            "api/test_notifications.py",
            "test_manual_and_origin_reads_are_idempotent_and_never_cross_recipient",
        ),
    ),
    Mutation(
        "premature-read",
        "frontend/src/features/translations/ExactCommentTarget.tsx",
        'if (status !== "ready" || !focusReported.current || readStarted.current)\n'
        "      return;",
        'if (status !== "ready" || readStarted.current)\n      return;',
        vitest(
            "src/features/translations/ExactCommentTarget.test.tsx",
            "never marks read when the mounted target cannot receive focus",
        ),
    ),
    Mutation(
        "content-bearing-sse",
        NOTIFICATIONS,
        '{"kind": event.kind, "id": event.id},',
        '{"kind": event.kind, "id": event.id, "body": "private"},',
        pytest(
            "integration/test_notification_stream.py",
            "test_two_principals_receive_only_closed_own_channel_frames_and_heartbeat",
        ),
    ),
    Mutation(
        "stale-page",
        "frontend/src/features/notifications/NotificationCenterPage.tsx",
        "controller.signal.aborted ||\n"
        "          generation !== requestGeneration.current ||\n"
        "          !result.data",
        "!result.data",
        vitest(
            "src/features/notifications/NotificationCenterPage.test.tsx",
            "discards a late page from a superseded filter generation",
        ),
    ),
    Mutation(
        "logout-cache",
        "frontend/src/features/auth/session.tsx",
        '    setState((current) => transitionSession(current, { type: "sign_out" }));\n'
        "    await generatedLogout();",
        "    await generatedLogout();",
        vitest(
            "src/features/auth/session.test.tsx",
            "logout clears React memory even when the generated network call fails",
        ),
    ),
)


def lock_path(root: Path = ROOT) -> Path:
    lock_id = hashlib.sha256(str(root.resolve()).encode()).hexdigest()
    return Path(tempfile.gettempdir()) / f"verboflex-phase5-mutation-{lock_id}"


@contextmanager
def mutation_lock(root: Path = ROOT) -> Iterator[None]:
    descriptor = os.open(lock_path(root), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


def execute(command: tuple[str, ...], root: Path, timeout: int) -> int:
    process = subprocess.Popen(
        command,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        process.communicate(timeout=timeout)
    except BaseException as error:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
        if isinstance(error, subprocess.TimeoutExpired):
            raise ValueError("mutation probe timed out") from error
        raise
    return process.returncode


def _remove_bytecode(path: Path) -> None:
    if path.suffix == ".py":
        for cache in path.parent.glob(f"__pycache__/{path.stem}.*.pyc"):
            cache.unlink()


def run_mutation(
    mutation: Mutation,
    *,
    root: Path = ROOT,
    timeout: int = MUTATION_TIMEOUT_SECONDS,
) -> dict[str, object]:
    started = time.monotonic()
    path = root / mutation.path
    original = path.read_bytes()
    source_digest = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    if text.count(mutation.original) != 1:
        raise ValueError("mutation target identity drift")
    modified = text.replace(mutation.original, mutation.replacement, 1)
    if path.suffix == ".py":
        try:
            ast.parse(modified)
        except SyntaxError as error:
            raise ValueError("mutation must remain syntactically valid") from error
    try:
        path.write_text(modified, encoding="utf-8")
        _remove_bytecode(path)
        returncode = execute(mutation.command, root, timeout)
        if returncode != 1:
            raise ValueError("mutation kill requires behavioral test exit 1")
    finally:
        path.write_bytes(original)
        _remove_bytecode(path)
        if path.read_bytes() != original:
            raise ValueError("source restoration failed")
        if hashlib.sha256(path.read_bytes()).hexdigest() != source_digest:
            raise ValueError("source digest restoration failed")
    return {
        "status": "killed",
        "source_sha256": source_digest,
        "duration_seconds": round(time.monotonic() - started, 3),
    }


def stop(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--only", choices=[mutation.label for mutation in MUTATIONS])
    args = parser.parse_args()
    if args.list:
        for index, mutation in enumerate(MUTATIONS, start=1):
            print(json.dumps({"index": index, "name": mutation.label}, sort_keys=True))
        return 0
    if args.self_test:
        return subprocess.call(
            [
                PYTHON,
                "-m",
                "pytest",
                "tests/architecture/test_phase5_mutation_verifier.py",
                "-q",
            ],
            cwd=ROOT / "backend",
        )

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    with mutation_lock():
        for index, mutation in enumerate(MUTATIONS, start=1):
            if args.only and args.only != mutation.label:
                continue
            if execute(mutation.command, ROOT, MUTATION_TIMEOUT_SECONDS) != 0:
                raise ValueError("baseline behavioral assertion did not pass")
            record = run_mutation(mutation)
            print(json.dumps({"index": index, **record}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BlockingIOError, KeyboardInterrupt, OSError, ValueError:
        print(
            json.dumps({"status": "failed", "reason": "mutation verification failed closed"}),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
