"""Validate against current server-owned base values and exact JSON selectors."""

import json
from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from verboflex.localization.web.config import JsonCatalogProfile
from verboflex.localization.web.messages import WebMessageInvalid, validate_message
from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.models.translation import LocalizationScope, TranslationKey, TranslationValue
from verboflex.schemas.authoring import AuthoringInput


def validate_replacements(session: Session, replacements: Mapping[UUID, str]) -> None:
    configured = session.scalar(
        select(ProductRepositoryMapping.id)
        .join(
            LocalizationScope, LocalizationScope.current_mapping_id == ProductRepositoryMapping.id
        )
        .join(TranslationValue, TranslationValue.scope_id == LocalizationScope.id)
        .where(
            TranslationValue.id.in_(replacements),
            ProductRepositoryMapping.localization_profile.is_not(None),
        )
        .limit(1)
    )
    if configured is None:
        return
    for value_id, proposed in replacements.items():
        value = session.get(TranslationValue, value_id)
        if value is None or value.is_deleted:
            raise WebMessageInvalid("Translation unavailable")
        scope = session.get_one(LocalizationScope, value.scope_id)
        mapping = session.get_one(ProductRepositoryMapping, scope.current_mapping_id)
        if mapping.localization_profile is None:
            continue
        profile = JsonCatalogProfile.model_validate(mapping.localization_profile)
        base = session.scalar(
            select(TranslationValue).where(
                TranslationValue.translation_key_id == value.translation_key_id,
                TranslationValue.scope_id == value.scope_id,
                TranslationValue.language == mapping.base_language,
                TranslationValue.selector_digest == value.selector_digest,
                TranslationValue.is_deleted.is_(False),
            )
        )
        if base is None or base.selector_kind != "json_path":
            raise WebMessageInvalid("Matching base text is unavailable")
        key = session.get_one(TranslationKey, value.translation_key_id)
        parents = json.loads(value.selector_bytes)["fields"]["parents"]
        validate_message(
            base.display_text,
            proposed,
            rich_text=(*parents, key.raw_key) in profile.rich_text_paths,
        )


def validate_authoring(session: Session, scope: LocalizationScope, data: AuthoringInput) -> None:
    mapping = session.get_one(ProductRepositoryMapping, scope.current_mapping_id)
    if mapping.localization_profile is None:
        return
    profile = JsonCatalogProfile.model_validate(mapping.localization_profile)
    base = None
    for candidate in session.scalars(
        select(TranslationValue)
        .join(TranslationKey)
        .where(
            TranslationValue.scope_id == scope.id,
            TranslationValue.language == mapping.base_language,
            TranslationValue.is_deleted.is_(False),
            TranslationKey.raw_key == data.key,
        )
    ):
        if (
            candidate.selector_kind == "json_path"
            and json.loads(candidate.selector_bytes)["fields"]["parents"] == data.parents
        ):
            base = candidate.display_text
            break
    if base is None and data.language != mapping.base_language:
        raise WebMessageInvalid("Import matching base text before adding this translation")
    for form in data.forms:
        validate_message(
            base if base is not None else form.text,
            form.text,
            rich_text=(*data.parents, data.key) in profile.rich_text_paths,
        )


def describe_contract(session: Session, value_id: UUID) -> dict[str, object] | None:
    import re

    value = session.get_one(TranslationValue, value_id)
    scope = session.get_one(LocalizationScope, value.scope_id)
    mapping = session.get_one(ProductRepositoryMapping, scope.current_mapping_id)
    if mapping.localization_profile is None or value.selector_kind != "json_path":
        return None
    profile = JsonCatalogProfile.model_validate(mapping.localization_profile)
    base = session.scalar(
        select(TranslationValue).where(
            TranslationValue.scope_id == scope.id,
            TranslationValue.translation_key_id == value.translation_key_id,
            TranslationValue.selector_digest == value.selector_digest,
            TranslationValue.language == mapping.base_language,
            TranslationValue.is_deleted.is_(False),
        )
    )
    if base is None:
        return None
    key = session.get_one(TranslationKey, value.translation_key_id)
    path = (*json.loads(value.selector_bytes)["fields"]["parents"], key.raw_key)
    return {
        "source": base.display_text,
        "tokens": re.findall(r"\{\{.*?\}\}", base.display_text),
        "rich_text": path in profile.rich_text_paths,
    }


def has_web_profile(session: Session, value_id: UUID) -> bool:
    return (
        session.scalar(
            select(ProductRepositoryMapping.id)
            .join(
                LocalizationScope,
                LocalizationScope.current_mapping_id == ProductRepositoryMapping.id,
            )
            .join(TranslationValue, TranslationValue.scope_id == LocalizationScope.id)
            .where(
                TranslationValue.id == value_id,
                ProductRepositoryMapping.localization_profile.is_not(None),
            )
        )
        is not None
    )
