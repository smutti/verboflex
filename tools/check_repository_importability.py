"""Read-only bounded importability probe; emits counts/provenance, never source text or keys.

Run in the backend runtime with its existing credential service and explicit
--repository-id UUID --branch BRANCH --root DIRECTORY. No provider writes.
"""

import argparse
import asyncio
import json
import logging
from collections import Counter
from uuid import UUID

from verboflex.core.config import get_settings
from verboflex.db.session import SessionFactory
from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter
from verboflex.localization.duplicate_diagnostics import inspect_duplicate_keys
from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.moko_layout import moko_layout
from verboflex.localization.preview.registry import detect_preview_layouts
from verboflex.services.bitbucket_oauth import BitbucketOAuthService, BitbucketOAuthTokenExchange
from verboflex.services.repositories import get_repository
from verboflex.services.repository_discovery import discover_repository_sources_for_record


async def probe(repository_id: UUID, branch: str, root: str) -> int:
    settings = get_settings()
    oauth = BitbucketOAuthService(settings=settings, token_exchange=BitbucketOAuthTokenExchange())
    adapter = BitbucketHttpAdapter(settings=settings, credential_leases=oauth)
    try:
        with SessionFactory() as session:
            repository = get_repository(session, repository_id=repository_id)
            snapshot = await discover_repository_sources_for_record(
                session,
                repository=repository,
                branch=branch,
                localization_root=root,
                adapter=adapter,
            )
        inputs = tuple(
            CanonicalParserInput(
                format="android_xml",
                repository_side="direct",
                path=file.path,
                content=file.content,
                layout_identity=classified[0],
                layout_version=1,
                base_language="und",
            )
            for file in snapshot.files
            if (classified := moko_layout(file.path)) is not None
        )
        report = inspect_duplicate_keys(inputs)
        per_file: Counter[str] = Counter()
        for group in report.groups:
            per_file.update(occurrence.path for occurrence in group.occurrences[1:])
        candidates = detect_preview_layouts(snapshot.files, repository_side="direct")
        print(
            json.dumps(
                dict(
                    repository_id=str(repository_id),
                    source_branch=branch,
                    root=root,
                    commit=snapshot.commit_hash,
                    files=len(snapshot.files),
                    total_bytes=snapshot.total_bytes,
                    recognized_candidates=len(candidates.candidates),
                    diagnostic_complete=report.complete,
                    issue_codes=report.issue_codes,
                    duplicate_groups=len(report.groups),
                    repeated_occurrences=report.repeated_occurrences,
                    repeated_by_file=dict(sorted(per_file.items())),
                    canonical_import="blocked_by_duplicates" if report.groups else "not_executed",
                )
            )
        )
        return 0 if report.complete else 1
    except Exception as error:
        print(json.dumps({"probe": "failed", "exception_type": type(error).__name__}))
        return 1
    finally:
        await adapter.aclose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-id", type=UUID, required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(probe(args.repository_id, args.branch, args.root)))
