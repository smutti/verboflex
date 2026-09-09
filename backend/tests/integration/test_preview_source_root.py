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
        self.max_depths = []
        self.reads = []
        self.escape = escape

    async def resolve_repository_branch(self, session, **kwargs):
        return BitbucketBranch(name=kwargs["branch"], commit_hash="a" * 40)

    async def list_repository_source_page(self, session, **kwargs):
        directory = kwargs["directory_path"]
        self.directories.append(directory)
        self.max_depths.append(kwargs["max_depth"])
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


class RecursiveBabelAdapter:
    def __init__(self):
        self.list_calls = []
        self.reads = []

    async def resolve_repository_branch(self, session, **kwargs):
        return BitbucketBranch(name=kwargs["branch"], commit_hash="b" * 40)

    async def list_repository_source_page(
        self,
        session,
        *,
        directory_path,
        max_depth,
        **kwargs,
    ):
        self.list_calls.append((directory_path, max_depth))
        assert directory_path is None
        assert max_depth == 12
        unrelated = tuple(
            BitbucketSourceEntry(path=f"unrelated{i}", kind="directory", size=None)
            for i in range(60)
        )
        localization_files = (
            BitbucketSourceEntry(
                path="babel/src/commonMain/moko-resources/base/strings.xml",
                kind="file",
                size=15,
            ),
            BitbucketSourceEntry(
                path="babel/src/commonMain/moko-resources/it/strings.xml",
                kind="file",
                size=15,
            ),
        )
        return BitbucketSourcePage(
            entries=unrelated + localization_files,
            next_url=None,
        )

    async def read_repository_source_file(self, session, **kwargs):
        self.reads.append(kwargs["path"])
        return b"<resources />\n"


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
    assert adapter.max_depths == [None]
    assert adapter.reads == ["translations/it.json"]
    assert snapshot.commit_hash == "a" * 40
    assert [file.path for file in snapshot.files] == ["translations/it.json"]


def test_rootless_discovery_finds_nested_babel_resources_without_manual_root():
    adapter = RecursiveBabelAdapter()
    snapshot = asyncio.run(discover(adapter, None))
    expected_paths = [
        "babel/src/commonMain/moko-resources/base/strings.xml",
        "babel/src/commonMain/moko-resources/it/strings.xml",
    ]
    assert adapter.list_calls == [(None, 12)]
    assert adapter.reads == expected_paths
    assert [file.path for file in snapshot.files] == expected_paths


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
