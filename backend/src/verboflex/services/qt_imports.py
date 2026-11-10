"""Optional Qt manifests read only by Celery, at the resolved import commit."""

import hashlib
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session, sessionmaker

from verboflex.integrations.bitbucket.client import BitbucketProviderReadError
from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.qt_capture import MANIFEST_PATH, MAX_MANIFEST_BYTES, QtManifest
from verboflex.services.repository_discovery import ReadAdapters, source_adapter

if TYPE_CHECKING:
    from verboflex.services.import_jobs import ImportExecutionIdentity


async def collect_qt_context(
    factory: sessionmaker[Session],
    *,
    identity: ImportExecutionIdentity,
    adapter: ReadAdapters,
    parser_inputs: tuple[CanonicalParserInput, ...],
    commits: Mapping[str, str],
) -> dict[str, object] | None:
    sides = {item.repository_side for item in parser_inputs if item.format == "qt_ts"}
    if len(sides) != 1:
        return None
    side = next(s for s in identity.repository_sides if s.role in sides)
    try:
        # Provider credential leases must own their transaction.
        with factory() as session:
            content = await source_adapter(adapter, side.provider).read_repository_source_file(
                session,
                workspace=side.workspace,
                repository_slug=side.repository_slug,
                commit_hash=commits[side.role],
                path=MANIFEST_PATH,
                max_bytes=MAX_MANIFEST_BYTES,
            )
    except BitbucketProviderReadError as error:
        if error.kind == "not_found":
            return None
        raise
    if len(content) > MAX_MANIFEST_BYTES:
        raise ValueError("Qt screenshot manifest exceeds its budget")
    manifest = QtManifest.model_validate_json(content)
    return {
        "manifest": manifest.model_dump(mode="json"),
        "manifest_digest": hashlib.sha256(content).hexdigest(),
        "source_digest": hashlib.sha256(
            json.dumps(manifest.sources, sort_keys=True).encode()
        ).hexdigest(),
        "commit": commits[side.role],
        "repository_id": str(side.repository_id),
    }
