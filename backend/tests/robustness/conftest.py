"""Reuse the isolated PostgreSQL/OAuth harness; never connect to the application DB."""

from tests.api.test_mcp_oauth import database as database
from tests.api.test_mcp_oauth import env as env
