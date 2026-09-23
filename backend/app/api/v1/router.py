from fastapi import APIRouter

from app.api.v1 import (
    admin_columnists,
    admin_contributor,
    admin_issues,
    admin_x_ingest,
    billing,
    columnists,
    contributor,
    issue_takes,
    issues,
    pipeline,
    push,
    settings,
)

api_router = APIRouter()
api_router.include_router(admin_issues.router)
api_router.include_router(admin_x_ingest.router)
api_router.include_router(admin_columnists.router)
api_router.include_router(admin_contributor.router)
api_router.include_router(columnists.router)
api_router.include_router(contributor.router)
# Issue-takes before issues so static paths like .../takes/mine resolve cleanly
# when mounted; both use /issues prefix.
api_router.include_router(issue_takes.router)
api_router.include_router(issues.router)
api_router.include_router(pipeline.router)
api_router.include_router(billing.router)
api_router.include_router(settings.router)
api_router.include_router(push.router)
