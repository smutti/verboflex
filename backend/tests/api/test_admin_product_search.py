"""Focused HTTP contract for administrator product-name search."""

from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session, sessionmaker

from tests.api import test_admin_products as product_contract

product_session_factory = product_contract.product_session_factory
clean_product_database = product_contract.clean_product_database


def test_product_collection_filters_by_name_and_binds_cursor_to_search(
    product_session_factory: sessionmaker[Session],
) -> None:
    """Name search is normalized, literal, bounded, and cursor-isolated."""
    _admin_id, admin_token = product_contract.create_authority(
        product_session_factory,
        email="search-admin@example.com",
        roles=("admin",),
    )
    product_contract.configure_dependencies(product_session_factory)
    product_contract._seed_products(product_session_factory, 105)

    first = asyncio.run(
        product_contract.product_request(
            "GET",
            access_token=admin_token,
            path=f"{product_contract.ADMIN_PRODUCTS_PATH}?name=PRODUCT%2001&limit=3",
        )
    )
    assert first.status_code == 200
    assert [item["name"] for item in first.json()["items"]] == [
        "Product 010",
        "Product 011",
        "Product 012",
    ]
    assert first.json()["next_cursor"]

    second = asyncio.run(
        product_contract.product_request(
            "GET",
            access_token=admin_token,
            path=(
                f"{product_contract.ADMIN_PRODUCTS_PATH}?name=product%2001&limit=50"
                f"&cursor={first.json()['next_cursor']}"
            ),
        )
    )
    assert second.status_code == 200
    assert [item["name"] for item in second.json()["items"]] == [
        "Product 013",
        "Product 014",
        "Product 015",
        "Product 016",
        "Product 017",
        "Product 018",
        "Product 019",
    ]
    assert second.json()["next_cursor"] is None

    wrong_search = asyncio.run(
        product_contract.product_request(
            "GET",
            access_token=admin_token,
            path=(
                f"{product_contract.ADMIN_PRODUCTS_PATH}?name=product%2002&limit=3"
                f"&cursor={first.json()['next_cursor']}"
            ),
        )
    )
    literal_wildcard = asyncio.run(
        product_contract.product_request(
            "GET",
            access_token=admin_token,
            path=f"{product_contract.ADMIN_PRODUCTS_PATH}?name=%25",
        )
    )
    assert wrong_search.status_code == 422
    assert wrong_search.json() == {"detail": "Invalid cursor"}
    assert literal_wildcard.status_code == 200
    assert literal_wildcard.json() == {"items": [], "next_cursor": None}
