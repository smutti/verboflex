"""Product discovery uses import snapshots, never per-request corpus scans."""

import asyncio
import importlib
from pathlib import Path
from urllib.parse import urlencode

import pytest
from alembic.config import Config
from sqlalchemy import event, text

from alembic import command
from verboflex.schemas.product_workspace import ProductWorkspaceQuery
from verboflex.services.product_workspace import list_product_workspaces

SUMMARY = importlib.import_module("tests.api.test_product_summary")
factory = SUMMARY.factory
clean_database = SUMMARY.clean_database


def refresh(factory, ids):
    with factory.begin() as session:
        session.execute(
            text("""UPDATE localization_scopes scope
            SET coverage_snapshot=verboflex_scope_coverage(scope.id, mapping.base_language),
                read_version=scope.read_version+1
            FROM product_repository_mappings mapping
            WHERE scope.id=:scope_id AND mapping.id=scope.current_mapping_id"""),
            {"scope_id": ids["scope"]},
        )


def request(token, **params):
    return asyncio.run(
        SUMMARY.SUPPORT.SUPPORT._request(
            "GET", "/api/v1/products/workspace?" + urlencode(params), token=token
        )
    )


@pytest.mark.parametrize("role", ["admin", "viewer", "translator", "product_manager_reviewer"])
def test_ordinary_roles_see_repository_coverage(factory, role):
    ids = SUMMARY.seed_two_keys(factory)
    refresh(factory, ids)
    response = request(SUMMARY.authority(factory, role))
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.json()["items"][0]["coverage"] == {
        "source_string_count": 2,
        "expected_translation_count": 2,
        "translated_count": 1,
        "missing_count": 1,
        "coverage_percent": 50.0,
        "language_count": 2,
        "languages": ["it", "vi"],
    }


@pytest.mark.parametrize(
    "text_value,structure",
    [
        ("\u2007 \t", []),
        (
            "Filled",
            [{"kind": "qt_ts:translation", "fields": [{"name": "status", "value": "unfinished"}]}],
        ),
    ],
)
def test_incomplete_variants_match_existing_product_summary(factory, text_value, structure):
    ids = SUMMARY.seed_two_keys(factory)
    with factory.begin() as session:
        SUMMARY.add_value(
            session, ids, ids["key"], "vi", translated=text_value, slot=4, structure=structure
        )
    refresh(factory, ids)
    token = SUMMARY.authority(factory)
    summary = SUMMARY.request(token, ids["product"]).json()
    coverage = request(token).json()["items"][0]["coverage"]
    for field in (
        "source_string_count",
        "expected_translation_count",
        "translated_count",
        "missing_count",
        "coverage_percent",
    ):
        assert coverage[field] == summary[field]
    assert coverage["translated_count"] == 0


def test_empty_and_unknown_denominators_are_not_complete(factory):
    ids = SUMMARY.SUPPORT.SUPPORT._seed_constraint_group(factory, name="Source only")
    refresh(factory, ids)
    SUMMARY.SUPPORT.SUPPORT._seed_constraint_group(
        factory, name="Not imported", complete_dataset=False
    )
    result = request(SUMMARY.authority(factory)).json()
    by_name = {item["name"]: item for item in result["items"]}
    assert by_name["Not imported"]["coverage"] is None
    assert by_name["Not imported"]["imported_scope_count"] == 0
    assert by_name["Source only"]["coverage"]["coverage_percent"] is None


def test_private_active_products_and_closed_query(factory):
    SUMMARY.SUPPORT.SUPPORT._seed_constraint_group(factory, name="Inactive", active=False)
    assert request(None).status_code == 401
    token = SUMMARY.authority(factory)
    assert request(token).json()["items"] == []
    for params in ({"page": 0}, {"q": "x" * 121}, {"q": "\x00"}, {"unknown": "x"}):
        assert request(token, **params).status_code == 422


def test_search_is_literal_case_insensitive_and_pagination_is_bounded(factory):
    with factory.begin() as session:
        for index in range(27):
            session.add(
                SUMMARY.Product(
                    display_name=f"Project {index:02d}",
                    name_key=f"project {index:02d}",
                    is_active=True,
                )
            )
        session.add(
            SUMMARY.Product(display_name="100%_Ready", name_key="100%_ready", is_active=True)
        )
    token = SUMMARY.authority(factory)
    first = request(token).json()
    second = request(token, page=2).json()
    assert first["total"] == 28
    assert len(first["items"]) == 24 and first["has_more"]
    assert len(second["items"]) == 4 and not second["has_more"]
    assert not ({item["id"] for item in first["items"]} & {item["id"] for item in second["items"]})
    assert request(token, q="  PROJECT 26 ").json()["items"][0]["name"] == "Project 26"
    assert request(token, q="%_").json()["total"] == 1
    assert request(token, q="absent").json()["total"] == 0
    assert request(token, page=10).json()["items"] == []


def test_card_read_is_one_snapshot_query_and_no_translation_scan(factory):
    ids = SUMMARY.seed_two_keys(factory)
    refresh(factory, ids)
    statements = []
    with factory() as session:
        connection = session.connection()

        def record(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)

        event.listen(connection, "before_cursor_execute", record)
        page = list_product_workspaces(session, query=ProductWorkspaceQuery())
    assert page.items[0].coverage.missing_count == 1
    assert len(statements) == 1
    assert "translation_values" not in statements[0]
    assert "translation_keys" not in statements[0]


def test_product_lookup_keeps_languages_scoped_to_the_repository(factory):
    first = SUMMARY.seed_two_keys(factory, name="Italian and Vietnamese")
    second = SUMMARY.SUPPORT.SUPPORT._seed_constraint_group(
        factory, name="Italian only", base_language="it"
    )
    refresh(factory, first)
    refresh(factory, second)
    token = SUMMARY.authority(factory)
    result = request(token, product_id=second["product"]).json()
    assert result["total"] == 1
    assert result["items"][0]["id"] == str(second["product"])
    assert result["items"][0]["coverage"]["languages"] == ["it"]
    assert request(token, product_id=first["product"]).json()["items"][0]["coverage"][
        "languages"
    ] == ["it", "vi"]
    assert request(token, product_id="invalid").status_code == 422


def test_rounding_never_claims_completion_with_missing_strings(factory):
    ids = SUMMARY.seed_two_keys(factory)
    refresh(factory, ids)
    with factory.begin() as session:
        session.execute(
            text("""UPDATE localization_scopes
            SET coverage_snapshot=coverage_snapshot ||
                '{"source_string_count": 10000,"expected_translation_count": 10000,
                  "translated_count": 9999}'::jsonb,
                read_version=read_version+1
            WHERE id=:id"""),
            {"id": ids["scope"]},
        )
    coverage = request(SUMMARY.authority(factory)).json()["items"][0]["coverage"]
    assert coverage["coverage_percent"] == 99.9
    assert coverage["missing_count"] == 1


def test_migration_backfills_existing_imports_reversibly(factory):
    ids = SUMMARY.seed_two_keys(factory)
    with factory() as session:
        engine = session.get_bind()
        config = Config(Path(__file__).resolve().parents[2] / "alembic.ini")
        config.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    command.downgrade(config, "0042_pull_request_tracking")
    command.upgrade(config, "head")
    # No refresh call: upgrading existing data must make statistics available.
    result = request(SUMMARY.authority(factory), product_id=ids["product"]).json()
    assert result["items"][0]["coverage"]["coverage_percent"] == 50
    assert result["items"][0]["coverage"]["languages"] == ["it", "vi"]
