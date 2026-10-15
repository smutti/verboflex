"""Source fallback applies only to explicit, unchanged Qt scalar sources in the base locale."""

# Shared by both search representations. Value, key, and :whitespace are bound by
# the caller. Imported translations and proposals remain the writeback authority.
SOURCE_FALLBACK_SQL = """
    value.selector_kind = 'scalar' AND NOT value.is_deleted AND NOT key.is_deleted
    AND value.language = {base_language}
    AND value.translated_text IS NOT NULL
    AND btrim(value.translated_text, :whitespace) = ''
    AND EXISTS (
        SELECT 1 FROM translation_value_locators AS fallback_locator
        WHERE fallback_locator.value_id = value.id AND fallback_locator.format = 'qt_ts'
          AND fallback_locator.repository_side IN ('direct', 'translations')
    )
    AND EXISTS (
        SELECT 1 FROM source_fallback_policies AS fallback_policy
        JOIN source_fallback_texts AS fallback_text
          ON fallback_text.product_id = fallback_policy.product_id
        WHERE fallback_policy.product_id = {product_id}
          AND fallback_policy.enabled AND fallback_policy.language = value.language
          AND fallback_text.source_digest =
              encode(sha256(convert_to(value.source_text, 'UTF8')), 'hex')
          AND fallback_text.source_text = value.source_text
    )
"""
