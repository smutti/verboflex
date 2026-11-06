import pytest
from pydantic import ValidationError

from verboflex.localization.web.config import JsonCatalogProfile, select_catalogs
from verboflex.services.repository_discovery import RepositorySourceFile


def test_catalog_selection_excludes_template_without_blacklisting_nav():
    profile = JsonCatalogProfile(files={"en": "en.json", "nav": "nav.json"})
    files = tuple(
        RepositorySourceFile(path="locales/" + name, content=b"{}")
        for name in ("en.json", "nav.json", "template.json")
    )
    assert [f.path for f in select_catalogs(files, profile, "locales")] == [
        "locales/en.json",
        "locales/nav.json",
    ]
    assert select_catalogs(files, None, None) is files


@pytest.mark.parametrize(
    "files",
    [
        {"en": "../en.json"},
        {"en": "it.json"},
        {"EN": "en.json"},
        {"en": "en.json", "it": "en.json"},
        {"en": "/en.json"},
    ],
)
def test_profile_rejects_invalid_catalog_authority(files):
    with pytest.raises(ValidationError):
        JsonCatalogProfile(files=files)


def test_missing_catalog_never_produces_partial_import():
    with pytest.raises(ValueError, match="missing"):
        select_catalogs((), JsonCatalogProfile(files={"en": "en.json"}), "locales")


def test_discovery_filters_before_download_and_size_validation():
    """An oversized malformed template cannot poison the two selected catalogs."""
    import asyncio
    from types import SimpleNamespace
    from uuid import uuid4

    from verboflex.localization.preview.registry import detect_preview_layouts
    from verboflex.services.repositories import RepositoryRecord
    from verboflex.services.repository_discovery import discover_repository_sources_for_record

    downloaded = []
    commits = []
    profile = JsonCatalogProfile(files={"en": "en.json", "it": "it.json"})
    files = {
        "locales/en.json": b'{"SITE":{"NAME":"Name"}}',
        "locales/it.json": b'{"SITE":{"NAME":"Nome"}}',
    }

    class Adapter:
        async def resolve_repository_branch(self, *args, **kwargs):
            commits.append(kwargs["branch"])
            return SimpleNamespace(name="main", commit_hash="a" * 40)

        async def list_repository_source_page(self, *args, **kwargs):
            assert kwargs["commit_hash"] == "a" * 40
            return SimpleNamespace(
                next_url=None,
                entries=[
                    SimpleNamespace(path=p, kind="file", size=len(c)) for p, c in files.items()
                ]
                + [SimpleNamespace(path="locales/template.json", kind="file", size=10**9)],
            )

        async def read_repository_source_file(self, *args, **kwargs):
            downloaded.append(kwargs["path"])
            return files[kwargs["path"]]

    snapshot = asyncio.run(
        discover_repository_sources_for_record(
            object(),
            repository=RepositoryRecord(
                id=uuid4(), workspace="fixture", repository_slug="web", descriptive_name=None
            ),
            branch="main",
            adapter=Adapter(),
            localization_root="locales",
            selected_paths=profile.catalog_paths("locales"),
        )
    )
    selected = select_catalogs(snapshot.files, profile, "locales")
    candidates = detect_preview_layouts(selected, repository_side="direct").candidates
    assert downloaded == ["locales/en.json", "locales/it.json"]
    assert commits == ["main"]
    assert snapshot.excluded_paths == ("locales/template.json",)
    assert len(candidates) == 1 and set(candidates[0].languages) == {"en", "it"}
