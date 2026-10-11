"""Bounded cleanup of expired MCP authorization records."""

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from verboflex.db.session import SessionFactory
from verboflex.services.mcp_oauth import cleanup_oauth
from verboflex.worker.celery_app import app


@app.task(name="verboflex.mcp.cleanup", soft_time_limit=25, time_limit=30)  # type: ignore[untyped-decorator]
def cleanup_mcp_oauth() -> dict[str, object]:
    try:
        with SessionFactory() as session:
            session.execute(text("SET LOCAL lock_timeout = '1s'"))
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            if not session.scalar(text("SELECT pg_try_advisory_xact_lock(77146202)")):
                return {"status": "busy"}
            return {
                "status": "completed",
                "deleted_rows": cleanup_oauth(session, datetime.now(UTC)),
            }
    except DBAPIError:
        return {"status": "unavailable"}
