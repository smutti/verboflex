"""Deliberate public operation allowlist. Credentials/user administration are not tools."""

# operationId: (tool name, user-facing purpose). Input contracts are generated from
# these exact operations; new API endpoints never become MCP tools automatically.
READ_ONLY_POST_OPERATIONS = frozenset(
    {"getTranslationSuggestions", "resolveTranslationSuggestion", "matchGlossaryTerms"}
)

OPERATIONS = {
    "listGlossaryTerms": ("list_glossary_terms", "Page current project terminology."),
    "matchGlossaryTerms": (
        "match_glossary_terms",
        "Find preferred and forbidden terms in source text. Read-only.",
    ),
    "saveGlossaryTerm": (
        "save_glossary_term",
        "Reviewer: save project terminology using its current version.",
    ),
    "deleteGlossaryTerm": (
        "delete_glossary_term",
        "Reviewer: delete a term using its current version.",
    ),
    "getTranslationSuggestions": (
        "get_translation_suggestions",
        "Find exact and fuzzy current translations for a source and language pair. "
        "Read-only; does not save or approve.",
    ),
    "resolveTranslationSuggestion": (
        "resolve_translation_suggestion",
        "Recheck a suggestion's live content and version before copying it to a draft. "
        "Read-only; never saves a translation.",
    ),
    "getAuthoringDestinations": (
        "list_authoring_files",
        "List confirmed files and languages for new keys or missing translations.",
    ),
    "getAuthoringPluralForms": (
        "get_plural_forms",
        "Read required forms for the chosen language and runtime format.",
    ),
    "listAuthoringRequests": (
        "list_new_entries",
        "Page pending new keys and missing translations.",
    ),
    "saveAuthoringRequest": (
        "save_new_entry",
        "Save a new key, missing language or plural form as a draft. "
        "Use confirmed file authority and expected_version. Does not write to Git.",
    ),
    "reviewAuthoringRequest": (
        "review_new_entry",
        "Approve, reject or reopen a structural draft with its exact version.",
    ),
    "discardAuthoringRequest": (
        "delete_new_entry",
        "Delete a pending new entry using its exact version.",
    ),
    "read_current_user": ("whoami", "Read the signed-in user and current roles."),
    "getPersonalDashboard": ("get_dashboard", "Read your dashboard and recent work."),
    "listProjectUpdates": ("list_project_updates", "Page project updates using next_cursor."),
    "listTranslationOptions": (
        "list_projects_and_languages",
        "List accessible projects and languages; optionally restrict to a product.",
    ),
    "searchTranslationKeys": (
        "search_translation_keys",
        "Search 50 keys per page with their selected language rows. Prefer product_id and a "
        "small visible_languages selection; pass next_cursor to continue.",
    ),
    "searchTranslations": (
        "search_translations",
        "Search 50 key-language groups per page. Filter by product, language, text, review "
        "state or work status. Use next_cursor to continue.",
    ),
    "getTranslationGroup": (
        "get_translation",
        "Read a key-language group, selector IDs, current revision digests, proposal version, "
        "constraints and allowed actions. Read before editing.",
    ),
    "saveTranslationProposal": (
        "save_translation",
        "Save the complete selector set as a draft. Use IDs/digests and expected_version from "
        "get_translation (0 for no proposal). Does not write to Git. On 409 re-read and "
        "explicitly reconcile; never silently overwrite.",
    ),
    "transitionTranslationProposal": (
        "review_translation",
        "Approve, reject or reopen a proposal using its exact current version. Review "
        "permissions, length limits and source reconciliation are enforced by VerboFlex.",
    ),
    "listTranslationReviewActivity": (
        "list_translation_activity",
        "Page translation edit and review history.",
    ),
    "putTranslationConstraint": (
        "set_translation_limit",
        "Set a maximum character length using the current constraint version.",
    ),
    "deleteTranslationConstraint": (
        "remove_translation_limit",
        "Remove a character limit using its exact current version.",
    ),
    "listTranslationComments": ("list_comments", "Read comments; use older_cursor to continue."),
    "createTranslationComment": (
        "add_comment",
        "Post a translation comment. Explicit mentions notify selected users; use "
        "search_mention_users for IDs and UTF-16 offsets.",
    ),
    "updateTranslationComment": (
        "edit_comment",
        "Edit your comment using its expected_version. Mentions can notify users.",
    ),
    "deleteTranslationComment": (
        "delete_comment",
        "Remove a comment using its current version and existing permissions.",
    ),
    "searchMentionUsers": (
        "search_mention_users",
        "Find users available for an explicitly requested comment mention.",
    ),
    "listNotifications": ("list_notifications", "Page your personal notifications."),
    "getUnreadNotificationCount": ("get_unread_count", "Count your unread notifications."),
    "markNotificationRead": ("mark_notification_read", "Mark one of your notifications as read."),
    "list_admin_products": (
        "list_admin_projects",
        "Admin: page project configurations, including unpublished projects.",
    ),
    "get_admin_product": ("get_project", "Admin: read project configuration and revision IDs."),
    "get_admin_product_summary": (
        "get_project_summary",
        "Admin: read string counts, translation coverage and languages with missing translations.",
    ),
    "create_admin_product": ("create_project", "Admin: create a project configuration draft."),
    "update_admin_product_candidate": (
        "update_project",
        "Admin: update project configuration draft.",
    ),
    "publish_admin_product_candidate": (
        "publish_project",
        "Admin: publish a validated project configuration. Preview confirmations are required "
        "by the API.",
    ),
    "list_admin_repositories": (
        "list_repositories",
        "Admin: page repositories already connected to VerboFlex.",
    ),
    "list_admin_repository_branches": (
        "list_repository_branches",
        "Admin: page branches in a connected repository.",
    ),
    "discover_admin_repository_sources": (
        "discover_repository_sources",
        "Admin: discover supported localization sources in a repository branch.",
    ),
    "list_admin_candidate_mappings": (
        "list_draft_mappings",
        "Admin: list draft repository mappings for a project.",
    ),
    "list_admin_revision_mappings": (
        "list_revision_mappings",
        "Admin: list mappings in a published project revision.",
    ),
    "create_admin_candidate_mapping": (
        "create_mapping",
        "Admin: add a repository mapping to a project draft.",
    ),
    "update_admin_candidate_mapping": ("update_mapping", "Admin: edit a draft repository mapping."),
    "create_admin_preview_job": (
        "start_mapping_preview",
        "Admin: queue mapping validation in a background worker; poll get_mapping_preview.",
    ),
    "get_admin_preview_job": ("get_mapping_preview", "Admin: read a mapping preview job."),
    "confirm_admin_preview_job": (
        "confirm_mapping_preview",
        "Admin: confirm the exact preview result after inspecting it.",
    ),
    "list_admin_published_mapping_imports": (
        "list_imports",
        "Admin: read latest import status for each published mapping.",
    ),
    "start_admin_published_mapping_import": (
        "start_import",
        "Admin: queue a source refresh. Removed repository strings are physically deleted "
        "from VerboFlex after activation. History rewrites require separate confirmation.",
    ),
    "get_admin_import": ("get_import", "Admin: poll a background import job; no blocking wait."),
    "get_admin_import_rewrite_comparison": (
        "get_rebase_comparison",
        "Admin: inspect the pending source-history rewrite before deciding whether to accept it.",
    ),
    "confirm_admin_import_rewrite_baseline": (
        "confirm_rebase",
        "Admin: accept the exact inspected history rewrite. Affected proposals require "
        "reconciliation; source deletions are applied.",
    ),
    "getChangeSetCandidates": (
        "list_submission_candidates",
        "List approved changes eligible for submission, grouped by repository/branch.",
    ),
    "createSubmissionReview": (
        "prepare_submission",
        "Prepare a durable submission review without publishing a Git commit or PR. Inspect "
        "files/values before submit_changes.",
    ),
    "getSubmissionReview": ("get_submission_review", "Read a prepared submission and blockers."),
    "getSubmissionReviewFiles": (
        "list_submission_files",
        "Page the exact files in a submission review.",
    ),
    "getSubmissionReviewValues": (
        "list_submission_values",
        "Page the exact translations in a submission review.",
    ),
    "createSubmissionBatch": (
        "submit_changes",
        "Publish approved changes through the background Git/PR workflow, using the exact "
        "prepared review and a unique request_key. This writes to the repository. Use "
        "get_submission_by_key after uncertain outcomes; do not create a new key to retry.",
    ),
    "getSubmissionBatchByKey": (
        "get_submission_by_key",
        "Recover submission status by its original idempotency request_key.",
    ),
    "getSubmissionBatch": ("get_submission", "Poll background submission batch status."),
    "listChangeSets": (
        "list_change_sets",
        "Page submitted change sets and PR status for a project.",
    ),
    "getChangeSet": (
        "get_change_set",
        "Read a submitted change set, conflicts, outcomes and pull request URL.",
    ),
    "getChangeSetItems": ("list_change_set_items", "Page items in a change set."),
    "getChangeSetFiles": ("list_change_set_files", "Page files in a change set."),
    "getChangeSetValues": ("list_change_set_values", "Page translations in a change set."),
    "getChangeSetActivity": ("list_change_set_activity", "Page submission activity and errors."),
    "retryChangeSet": (
        "retry_change_set",
        "Retry an eligible failed Git/PR job after inspecting its current state.",
    ),
    "reconcileChangeSet": (
        "reconcile_change_set",
        "Reconcile an uncertain Git/PR submission outcome with the provider.",
    ),
    "finalizeChangeSet": (
        "finalize_change_set",
        "Finalize an inspected change set according to the current API state.",
    ),
}
