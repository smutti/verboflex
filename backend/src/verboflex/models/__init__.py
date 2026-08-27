"""Import every mapped model so Alembic sees the complete metadata graph."""

from verboflex.models.auth_session import AuthSession
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.product import Product, ProductRevision
from verboflex.models.repository import Repository
from verboflex.models.role import Role, user_roles_table
from verboflex.models.user import User

__all__ = [
    "AuthSession",
    "BitbucketConnection",
    "Product",
    "ProductRevision",
    "Repository",
    "Role",
    "User",
    "user_roles_table",
]
