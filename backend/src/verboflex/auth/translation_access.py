"""Principal-authorized access to one active translation group and product."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final
from uuid import UUID

from sqlalchemy.orm import Session

from verboflex.auth.principal import Principal
from verboflex.auth.product_access import product_roles
from verboflex.schemas.users import RoleName
from verboflex.services.translation_search import (
    TranslationGroupDetail,
    TranslationGroupUnavailable,
    TranslationSearchInputError,
    get_translation_group,
)

TRANSLATION_UNAVAILABLE_MESSAGE: Final = "translation unavailable"
TRANSLATION_ACTION_DENIED_MESSAGE: Final = "translation action denied"


class TranslationGroupAccessMode(StrEnum):
    """Closed actions that Phase 5 services may authorize for a group."""

    READ = "read"
    PROPOSE = "propose"
    COMMENT = "comment"
    REVIEW = "review"
    DELETE_COMMENT = "delete_comment"


@dataclass(frozen=True, slots=True)
class TranslationGroupAccess:
    """Credential-free group detail paired with its exact authorized product."""

    group: TranslationGroupDetail
    product_id: UUID


class TranslationGroupAccessUnavailable(LookupError):
    """Generic absent, stale, inactive, foreign-scope, or malformed outcome."""


class TranslationGroupActionDenied(PermissionError):
    """Raised only after group and product authority has been established."""


_ALL_ROLES: Final = frozenset(RoleName)
_COMMENT_ROLES: Final = frozenset(
    (
        RoleName.ADMIN,
        RoleName.PRODUCT_MANAGER_REVIEWER,
        RoleName.TRANSLATOR,
    )
)
_REVIEW_ROLES: Final = frozenset(
    (
        RoleName.ADMIN,
        RoleName.PRODUCT_MANAGER_REVIEWER,
    )
)
_ALLOWED_ROLES: Final = {
    TranslationGroupAccessMode.READ: _ALL_ROLES,
    TranslationGroupAccessMode.PROPOSE: _COMMENT_ROLES,
    TranslationGroupAccessMode.COMMENT: _COMMENT_ROLES,
    TranslationGroupAccessMode.REVIEW: _REVIEW_ROLES,
    TranslationGroupAccessMode.DELETE_COMMENT: frozenset((RoleName.ADMIN,)),
}


def _resolve_current_group(
    session: Session,
    *,
    translation_group_id: UUID,
) -> TranslationGroupDetail:
    """Normalize only bounded resource-authority failures to one outcome."""
    try:
        group = get_translation_group(session, group_id=translation_group_id)
    except (TranslationGroupUnavailable, TranslationSearchInputError) as error:
        raise TranslationGroupAccessUnavailable(TRANSLATION_UNAVAILABLE_MESSAGE) from error

    try:
        valid_projection = group.id == translation_group_id and isinstance(group.product_id, UUID)
    except AttributeError:
        valid_projection = False
    if not valid_projection:
        raise TranslationGroupAccessUnavailable(TRANSLATION_UNAVAILABLE_MESSAGE)
    return group


def resolve_translation_group_access(
    session: Session,
    *,
    principal: Principal,
    translation_group_id: UUID,
    mode: TranslationGroupAccessMode,
) -> TranslationGroupAccess:
    """Resolve current group authority first, then enforce the closed role matrix."""
    group = _resolve_current_group(session, translation_group_id=translation_group_id)

    if not isinstance(mode, TranslationGroupAccessMode):
        raise TranslationGroupActionDenied(TRANSLATION_ACTION_DENIED_MESSAGE)
    roles = product_roles(session, principal.user_id, group.product_id)
    if not roles:
        raise TranslationGroupAccessUnavailable(TRANSLATION_UNAVAILABLE_MESSAGE)
    if _ALLOWED_ROLES[mode].isdisjoint(roles):
        raise TranslationGroupActionDenied(TRANSLATION_ACTION_DENIED_MESSAGE)

    return TranslationGroupAccess(group=group, product_id=group.product_id)
