"""Physical deletion of retired canonical content, in the activating transaction.

No provider writes, disabled triggers, text snapshots or unbounded ORM graphs.
The product/scope lock order matches imports, constraints and proposal writers.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult, text
from sqlalchemy.orm import Session


def purge_retired_translations(
    session: Session, *, scope_id: UUID, batch_size: int = 1000
) -> dict[str, int]:
    """Delete retired members and consume terminal staging; caller owns commit.

    Live members and their proposals remain. If a proposal still contains a retired
    member, remove that member and require fresh review of the survivors. Discussion
    is removed only when its entire key/language group has disappeared.
    """
    if not 1 <= batch_size <= 10000:
        raise ValueError("invalid purge batch size")
    product = session.scalar(
        text("SELECT product_id FROM localization_scopes WHERE id=:id"), {"id": scope_id}
    )
    if product is None:
        return {}
    session.execute(text("SELECT id FROM products WHERE id=:id FOR UPDATE"), {"id": product})
    session.execute(
        text("SELECT id FROM localization_scopes WHERE id=:id FOR UPDATE"), {"id": scope_id}
    )
    counts: dict[str, int] = {}

    def remove(table: str, sql: str, parameters: dict[str, object]) -> int:
        result = cast(CursorResult[object], session.execute(text(sql), parameters))
        counts[table] = counts.get(table, 0) + result.rowcount
        return result.rowcount

    # Include legacy keys already marked deleted; active keys are never inferred
    # as deleted from an incomplete/failed import or from missing staging alone.
    session.execute(
        text("""UPDATE translation_values v SET is_deleted=true, deleted_at=now()
        FROM translation_keys k WHERE k.id=v.translation_key_id AND k.scope_id=:scope
        AND k.is_deleted AND NOT v.is_deleted"""),
        {"scope": scope_id},
    )
    while True:
        ids = list(
            session.scalars(
                text("""SELECT id FROM translation_values
            WHERE scope_id=:scope AND is_deleted ORDER BY translation_key_id, language, id
            LIMIT :limit FOR UPDATE"""),
                {"scope": scope_id, "limit": batch_size},
            )
        )
        if not ids:
            break
        params: dict[str, object] = {"ids": ids}
        group = """EXISTS (SELECT 1 FROM translation_values retired
            WHERE retired.id=ANY(:ids) AND retired.translation_key_id=t.translation_key_id
              AND retired.language=t.language)"""
        gone = """NOT EXISTS (SELECT 1 FROM translation_values live
            WHERE live.translation_key_id=t.translation_key_id
              AND live.language=t.language AND NOT live.is_deleted)"""
        # Activity snapshots can contain the retired member even after a proposal
        # was resaved with only live members. Delete those old snapshots first.
        remove("review_activities", f"DELETE FROM review_activities t WHERE {group}", params)
        session.execute(
            text("""UPDATE translation_proposals p
            SET version=version+1, state='draft', reconciliation_required=true, updated_at=now()
            WHERE EXISTS (SELECT 1 FROM translation_proposal_values pv
                WHERE pv.proposal_id=p.id AND pv.translation_value_id=ANY(:ids))"""),
            params,
        )
        remove(
            "translation_proposal_values",
            """DELETE FROM translation_proposal_values
            WHERE translation_value_id=ANY(:ids)""",
            params,
        )
        remove(
            "translation_proposals",
            f"DELETE FROM translation_proposals t WHERE {group} AND {gone}",
            params,
        )
        comment_ids = f"SELECT t.id FROM translation_comments t WHERE {group} AND {gone}"
        remove(
            "translation_comment_mentions",
            f"""DELETE FROM translation_comment_mentions
            WHERE comment_version_id IN (SELECT id FROM translation_comment_versions
                WHERE comment_id IN ({comment_ids}))""",
            params,
        )
        remove(
            "translation_comment_versions",
            f"""DELETE FROM translation_comment_versions
            WHERE comment_id IN ({comment_ids})""",
            params,
        )
        remove(
            "translation_comments",
            f"DELETE FROM translation_comments t WHERE {group} AND {gone}",
            params,
        )
        remove(
            "translation_constraints",
            f"DELETE FROM translation_constraints t WHERE {group} AND {gone}",
            params,
        )
        remove(
            "translation_value_revisions",
            """DELETE FROM translation_value_revisions
            WHERE value_id=ANY(:ids)""",
            params,
        )
        remove(
            "translation_value_locators",
            """DELETE FROM translation_value_locators
            WHERE value_id=ANY(:ids)""",
            params,
        )
        remove("translation_values", "DELETE FROM translation_values WHERE id=ANY(:ids)", params)
    # Legacy empty tombstones may still own discussion even without value rows.
    # Delete evidence before parents, while the retired key can authorize it.
    empty_keys = """SELECT k.id FROM translation_keys k
        WHERE k.scope_id=:scope AND k.is_deleted AND NOT EXISTS (
            SELECT 1 FROM translation_values v WHERE v.translation_key_id=k.id)"""
    empty_params: dict[str, object] = {"scope": scope_id}
    remove(
        "review_activities",
        f"DELETE FROM review_activities WHERE translation_key_id IN ({empty_keys})",
        empty_params,
    )
    remove(
        "translation_comment_mentions",
        f"""DELETE FROM translation_comment_mentions
        WHERE comment_version_id IN (SELECT id FROM translation_comment_versions
            WHERE translation_key_id IN ({empty_keys}))""",
        empty_params,
    )
    remove(
        "translation_comment_versions",
        f"""DELETE FROM translation_comment_versions
        WHERE translation_key_id IN ({empty_keys})""",
        empty_params,
    )
    remove(
        "translation_comments",
        f"DELETE FROM translation_comments WHERE translation_key_id IN ({empty_keys})",
        empty_params,
    )
    # Key-wide constraints and empty proposal heads cascade with the key.
    remove(
        "translation_keys",
        """DELETE FROM translation_keys k
        WHERE k.scope_id=:scope AND k.is_deleted
          AND NOT EXISTS (SELECT 1 FROM translation_values v WHERE v.translation_key_id=k.id)""",
        {"scope": scope_id},
    )
    # Staging is a verified import candidate, not another permanent copy of the
    # corpus. Preserve pending rewrite candidates until the user resolves them.
    executions = session.scalars(
        text("""SELECT e.id FROM import_executions e
        JOIN import_jobs j ON j.id=e.import_job_id
        JOIN product_repository_mappings m ON m.id=j.mapping_id
        JOIN localization_scopes s ON s.product_id=j.product_id
          AND s.mapping_identity_key=m.identity_key
        WHERE s.id=:scope AND e.state IN ('succeeded', 'failed')
          AND NOT EXISTS (SELECT 1 FROM import_rewrite_proposals r
            WHERE r.proposed_execution_id=e.id AND r.status='pending')
        ORDER BY e.id"""),
        {"scope": scope_id},
    )
    for execution in executions:
        while remove(
            "staged_translation_values",
            """DELETE FROM staged_translation_values
            WHERE import_execution_id=:execution AND position IN (
                SELECT position FROM staged_translation_values WHERE import_execution_id=:execution
                ORDER BY position LIMIT :limit)""",
            {"execution": execution, "limit": batch_size},
        ):
            pass
    return counts
