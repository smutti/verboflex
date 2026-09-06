"""S3/S4: bounded provider reads cannot escape a selected localization root."""

import asyncio
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from verboflex.integrations.bitbucket.client import (
    BitbucketBranch,
    BitbucketProviderReadError,
    BitbucketSourceEntry,
    BitbucketSourcePage,
)
from verboflex.services.repositories import RepositoryRecord
from verboflex.services.repository_discovery import (
    SourceDiscoveryAdapter,
    discover_repository_sources_for_record,
)


class ScopedAdapter:
    def __init__(self, escape=False):
        self.directories = []
        self.reads = []
        self.escape = escape

    async def resolve_repository_branch(self, session, **kwargs):
        return BitbucketBranch(name=kwargs["branch"], commit_hash="a" * 40)

    async def list_repository_source_page(self, session, **kwargs):
        directory = kwargs["directory_path"]
        self.directories.append(directory)
        if directory is None:
            entries = tuple(
                BitbucketSourceEntry(path=f"unrelated{i}", kind="directory", size=None)
                for i in range(60)
            )
        elif directory == "translations":
            entries = (
                BitbucketSourceEntry(
                    path="outside/it.json" if self.escape else "translations/it.json",
                    kind="file",
                    size=2,
                ),
            )
        else:
            entries = ()
        return BitbucketSourcePage(entries=entries, next_url=None)

    async def read_repository_source_file(self, session, **kwargs):
        self.reads.append(kwargs["path"])
        return b"{}"


async def discover(adapter, root):
    with Session() as session:
        return await discover_repository_sources_for_record(
            session,
            repository=RepositoryRecord(
                id=uuid4(), workspace="team", repository_slug="repo", descriptive_name=None
            ),
            branch="source",
            adapter=cast(SourceDiscoveryAdapter, adapter),
            localization_root=root,
        )


def test_root_skips_unrelated_directories_and_preserves_commit_paths():
    adapter = ScopedAdapter()
    snapshot = asyncio.run(discover(adapter, "translations"))
    assert adapter.directories == ["translations"]
    assert adapter.reads == ["translations/it.json"]
    assert snapshot.commit_hash == "a" * 40
    assert [file.path for file in snapshot.files] == ["translations/it.json"]


def test_scoped_discovery_rejects_escaping_provider_entries_before_read():
    adapter = ScopedAdapter(escape=True)
    with pytest.raises(BitbucketProviderReadError) as error:
        asyncio.run(discover(adapter, "translations"))
    assert error.value.kind == "invalid_source"
    assert adapter.reads == []


@pytest.mark.parametrize("root", ["%74ranslations", "translations/%2e", "../translations"])
def test_worker_rejects_noncanonical_localization_root_before_provider_reads(root):
    adapter = ScopedAdapter()
    with pytest.raises((BitbucketProviderReadError, ValueError)):
        asyncio.run(discover(adapter, root))
    assert adapter.directories == [] and adapter.reads == []
