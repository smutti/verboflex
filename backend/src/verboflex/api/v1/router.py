"""Versioned API router composition."""

from fastapi import APIRouter

from verboflex.api.v1.routes import (
    admin_bitbucket,
    admin_discovery,
    admin_duplicates,
    admin_github,
    admin_mappings,
    admin_previews,
    admin_products,
    admin_repositories,
    admin_users,
    admin_workspace,
    auth,
    authoring,
    branch_workflow,
    comments,
    dashboard,
    glossary,
    health,
    notifications,
    product_team,
    product_workspace,
    reuse,
    screenshots,
    source_fallback,
    submissions,
    system,
    translation_constraints,
    translation_reviews,
    translations,
    users,
)

api_router = APIRouter()
api_router.include_router(screenshots.router)
api_router.include_router(source_fallback.router)
api_router.include_router(product_team.router)
api_router.include_router(product_workspace.router)
api_router.include_router(authoring.router)
api_router.include_router(reuse.router)
api_router.include_router(glossary.router)
api_router.include_router(dashboard.router)
api_router.include_router(submissions.router)
api_router.include_router(branch_workflow.router)
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(system.router)
api_router.include_router(translations.router)
api_router.include_router(translation_constraints.router)
api_router.include_router(translation_reviews.router)
api_router.include_router(comments.router)
api_router.include_router(notifications.router)
api_router.include_router(admin_bitbucket.router)
api_router.include_router(admin_github.router)
api_router.include_router(admin_workspace.router)
api_router.include_router(admin_discovery.router)
api_router.include_router(admin_mappings.router)
api_router.include_router(admin_previews.router)
api_router.include_router(admin_duplicates.router)
api_router.include_router(admin_users.router)
api_router.include_router(admin_products.router)
api_router.include_router(admin_repositories.router)
