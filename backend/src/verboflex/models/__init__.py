"""Import every mapped model so Alembic sees the complete metadata graph."""

from verboflex.models.auth_session import AuthSession
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.preview_job import ActiveRevisionRevalidationConfirmation, PreviewJob
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import (
    ProductMappingAllowedTarget,
    ProductMappingRepositorySide,
    ProductRepositoryMapping,
)
from verboflex.models.repository import Repository
from verboflex.models.role import Role, user_roles_table
from verboflex.models.user import User

__all__ = [
    "AuthSession",
    "ActiveRevisionRevalidationConfirmation",
    "BitbucketConnection",
    "PreviewJob",
    "Product",
    "ProductMappingAllowedTarget",
    "ProductMappingRepositorySide",
    "ProductRepositoryMapping",
    "ProductRevision",
    "Repository",
    "Role",
    "User",
    "user_roles_table",
]
