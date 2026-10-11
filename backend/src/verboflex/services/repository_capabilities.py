"""Read authority for immutable provider identities on a mapping."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.models.repository import Repository


@dataclass(frozen=True)
class PublicReadAuthority:
    generation: int = 0


def is_public_github_mapping(session: Session, mapping: ProductRepositoryMapping | None) -> bool:
    if mapping is None or not mapping.sides:
        return False
    ids = {side.repository_id for side in mapping.sides}
    providers = tuple(session.scalars(select(Repository.provider).where(Repository.id.in_(ids))))
    return len(providers) == len(ids) and all(provider == "github" for provider in providers)
