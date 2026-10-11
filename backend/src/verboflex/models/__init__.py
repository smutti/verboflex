"""Import every mapped model so Alembic sees the complete metadata graph."""

from verboflex.models.audit import AuditEntry
from verboflex.models.auth_session import AuthSession
from verboflex.models.authoring import AuthoringRequest
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.duplicate_report import (
    DuplicateGroupRow,
    DuplicateOccurrenceRow,
    DuplicateReportRow,
)
from verboflex.models.glossary import GlossaryEntry
from verboflex.models.import_job import (
    ImportExecution,
    ImportJob,
    ImportRewriteDelta,
    ImportRewriteProposal,
    ImportSourceReference,
)
from verboflex.models.mcp_oauth import McpAuthorizationRequest, McpClient, McpGrant, McpToken
from verboflex.models.preview_job import ActiveRevisionRevalidationConfirmation, PreviewJob
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import (
    ProductMappingAllowedTarget,
    ProductMappingRepositorySide,
    ProductRepositoryMapping,
)
from verboflex.models.repository import Repository
from verboflex.models.review import (
    Notification,
    NotificationKind,
    ReviewActivity,
    ReviewActivityKind,
    TranslationComment,
    TranslationCommentMention,
    TranslationCommentVersion,
    TranslationProposal,
    TranslationProposalValue,
)
from verboflex.models.role import Role, user_roles_table
from verboflex.models.submission import (
    ChangeSet,
    ChangeSetEvent,
    ChangeSetFile,
    ChangeSetItem,
    ChangeSetProof,
    SubmissionBatch,
    SubmissionReview,
)
from verboflex.models.translation import (
    EffectiveConstraintSource,
    LocalizationScope,
    ParseIssueCode,
    ReviewState,
    SelectorKind,
    StagedTranslationValue,
    TranslationKey,
    TranslationParseIssue,
    TranslationValue,
    TranslationValueLocator,
    TranslationValueRevision,
)
from verboflex.models.translation_constraint import TranslationConstraint
from verboflex.models.user import User

__all__ = [
    "AuthoringRequest",
    "GlossaryEntry",
    "AuditEntry",
    "McpAuthorizationRequest",
    "McpClient",
    "McpGrant",
    "McpToken",
    "ChangeSet",
    "ChangeSetEvent",
    "ChangeSetFile",
    "ChangeSetItem",
    "ChangeSetProof",
    "SubmissionBatch",
    "SubmissionReview",
    "AuthSession",
    "ActiveRevisionRevalidationConfirmation",
    "BitbucketConnection",
    "DuplicateGroupRow",
    "DuplicateOccurrenceRow",
    "DuplicateReportRow",
    "EffectiveConstraintSource",
    "ImportExecution",
    "ImportJob",
    "ImportRewriteDelta",
    "ImportRewriteProposal",
    "ImportSourceReference",
    "LocalizationScope",
    "Notification",
    "NotificationKind",
    "ParseIssueCode",
    "PreviewJob",
    "Product",
    "ProductMappingAllowedTarget",
    "ProductMappingRepositorySide",
    "ProductRepositoryMapping",
    "ProductRevision",
    "Repository",
    "ReviewActivity",
    "ReviewActivityKind",
    "ReviewState",
    "Role",
    "SelectorKind",
    "StagedTranslationValue",
    "TranslationKey",
    "TranslationComment",
    "TranslationCommentMention",
    "TranslationCommentVersion",
    "TranslationConstraint",
    "TranslationParseIssue",
    "TranslationValue",
    "TranslationValueLocator",
    "TranslationValueRevision",
    "TranslationProposal",
    "TranslationProposalValue",
    "User",
    "user_roles_table",
]
