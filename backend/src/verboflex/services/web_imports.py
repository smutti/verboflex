"""Worker-only source reads pinned to the catalog import's already resolved commit."""

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from verboflex.localization.web.config import JsonCatalogProfile
from verboflex.localization.web.context import catalog_addresses, extract_usages
from verboflex.localization.web.contracts import WebManifest
from verboflex.services.repositories import RepositoryRecord
from verboflex.services.repository_discovery import (
    ReadAdapters,
    RepositorySourceFile,
    discover_repository_sources_for_record,
    source_adapter,
)


async def collect_web_context(
    session: Session,
    *,
    profile: JsonCatalogProfile,
    repository: RepositoryRecord,
    branch: str,
    commit: str,
    adapter: ReadAdapters,
    root: str | None,
    catalogs: tuple[RepositorySourceFile, ...],
    base_language: str,
) -> tuple[dict[str, object], tuple[RepositorySourceFile, ...]]:
    config = profile.web_capture
    assert config is not None
    manifest_bytes = await source_adapter(adapter, repository.provider).read_repository_source_file(
        session,
        workspace=repository.workspace,
        repository_slug=repository.repository_slug,
        commit_hash=commit,
        path=config.manifest_path,
        max_bytes=1_048_576,
    )
    if len(manifest_bytes) > 1_048_576:
        raise ValueError("Scenario manifest exceeds its budget")
    manifest = WebManifest.model_validate_json(manifest_bytes)
    sources: dict[str, bytes] = {}
    for source_root in config.source_roots:
        snapshot = await discover_repository_sources_for_record(
            session,
            repository=repository,
            branch=branch,
            adapter=adapter,
            localization_root=source_root,
            commit_hash=commit,
            web_sources=True,
            excluded_roots=config.source_excludes,
        )
        sources.update({file.path: file.content for file in snapshot.files})
    usages = extract_usages(sources, config.marker)
    by_path = {file.path: file.content for file in catalogs}
    data = {
        locale: json.loads(by_path[f"{root}/{path}" if root else path])
        for locale, path in profile.files.items()
    }
    if base_language not in data:
        raise ValueError("Web capture requires a base catalog")
    diagnostics: list[str] = []
    blocked = False
    try:
        addresses = catalog_addresses(data[base_language])
        for catalog in data.values():
            catalog_addresses(catalog)
    except ValueError as error:
        addresses = {}
        blocked = True
        diagnostics.append(str(error))
    # Declared bindings, static usages and observed DOM text are separate evidence.
    occurrences = usages["occurrences"]
    assert isinstance(occurrences, list)
    missing = sorted({o["key"] for o in occurrences if o["key"] and o["key"] not in addresses})
    diagnostics.extend(f"Missing runtime key: {key}" for key in missing)
    if any(o["key"] is None for o in occurrences):
        diagnostics.append("Dynamic references require explicit scenario bindings")

    def leaf(catalog: Any, path: tuple[str, ...]) -> str:
        for part in path:
            catalog = catalog[part]
        return str(catalog)

    for locale, catalog in data.items():
        if blocked:
            break
        locale_addresses = catalog_addresses(catalog)
        if any(
            locale_addresses[key] != path
            for key, path in addresses.items()
            if key in locale_addresses
        ):
            blocked = True
            diagnostics.append(f"{locale}: incompatible literal-dot and nested catalog paths")
        missing_count = len(set(addresses) - set(locale_addresses))
        empty_count = sum(not leaf(catalog, path).strip() for path in locale_addresses.values())
        if missing_count:
            diagnostics.append(f"{locale}: {missing_count} missing base counterparts")
        if empty_count:
            diagnostics.append(f"{locale}: {empty_count} empty messages")
        if locale != base_language:
            same = sum(
                leaf(catalog, locale_addresses[key]) == leaf(data[base_language], path)
                for key, path in addresses.items()
                if key in locale_addresses
            )
            if same:
                diagnostics.append(
                    f"{locale}: {same} messages identical to the base (informational)"
                )
    for scenario in manifest.scenarios:
        diagnostics.extend(
            f"{scenario.id}: unbound target {target.key}"
            for target in scenario.targets
            if target.key not in addresses
        )
    sources[config.manifest_path] = manifest_bytes
    return {
        "catalog_urls": {
            locale: config.catalog_url_prefix + path for locale, path in profile.files.items()
        },
        "sources": [
            {
                "path": path,
                "commit": commit,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
            for path, content in sorted(sources.items())
        ],
        "version": 1,
        "config": config.model_dump(mode="json"),
        "manifest": manifest.model_dump(mode="json"),
        "catalogs": data,
        "addresses": {key: list(path) for key, path in addresses.items()},
        "usages": usages,
        "diagnostics": diagnostics,
        "capture_blocked": blocked,
        "commit": commit,
        "repository_id": str(repository.id),
        "source_digest": hashlib.sha256(
            json.dumps(
                {
                    path: hashlib.sha256(content).hexdigest()
                    for path, content in sorted(sources.items())
                },
                sort_keys=True,
            ).encode()
        ).hexdigest(),
        "manifest_digest": hashlib.sha256(manifest_bytes).hexdigest(),
    }, tuple(
        RepositorySourceFile(path=path, content=content)
        for path, content in sorted(sources.items())
    )
