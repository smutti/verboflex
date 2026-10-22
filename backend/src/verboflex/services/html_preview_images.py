"""Import-time, commit-pinned image snapshots; called only by the import worker."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session, sessionmaker

from verboflex.integrations.bitbucket.client import BitbucketProviderReadError
from verboflex.localization.html_images import (
    MAX_IMAGE_BYTES,
    MAX_IMAGE_PATHS,
    MAX_TOTAL_IMAGE_BYTES,
    image_data_uri,
    referenced_images,
)
from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.services.repository_discovery import ReadAdapters, source_adapter

if TYPE_CHECKING:
    from verboflex.services.import_jobs import ImportExecutionIdentity


async def collect_html_preview_images(
    factory: sessionmaker[Session],
    *,
    identity: ImportExecutionIdentity,
    adapter: ReadAdapters,
    parser_inputs: tuple[CanonicalParserInput, ...],
    commits: Mapping[str, str],
) -> dict[str, dict[str, str]] | None:
    requested: dict[str, set[str]] = {}
    for item in parser_inputs:
        if item.format == "html":
            paths = requested.setdefault(item.repository_side, set())
            paths.update(
                sorted(referenced_images(item.path, item.content) - paths)[
                    : max(0, MAX_IMAGE_PATHS - len(paths))
                ]
            )
    if not requested:
        return None
    result: dict[str, dict[str, str]] = {}
    attempts = 0
    used_bytes = 0
    for side in identity.repository_sides:
        if side.role not in requested:
            continue
        images = result.setdefault(side.role, {})
        for path in sorted(requested[side.role]):
            remaining = min(MAX_IMAGE_BYTES, MAX_TOTAL_IMAGE_BYTES - used_bytes)
            if attempts >= MAX_IMAGE_PATHS or remaining <= 0:
                break
            attempts += 1
            try:
                with factory() as session:
                    content = await source_adapter(
                        adapter, side.provider
                    ).read_repository_source_file(
                        session,
                        workspace=side.workspace,
                        repository_slug=side.repository_slug,
                        commit_hash=commits[side.role],
                        path=path,
                        max_bytes=remaining,
                    )
            except BitbucketProviderReadError as error:
                # An optional broken image must not prevent text translation.
                # Connection/permission failures still fail the whole import.
                if error.kind in {"not_found", "invalid_source", "limit_exceeded"}:
                    continue
                raise
            used_bytes += len(content)
            uri = image_data_uri(content) if len(content) <= remaining else None
            if uri is not None:
                images[path] = uri
    return result
