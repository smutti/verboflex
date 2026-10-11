"""Bounded validation failures that never reflect credentials or raw request data."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _safe_label(value: object, limit: int) -> str:
    return str(value)[:limit].encode("utf-8", errors="replace").decode("utf-8")


async def request_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # `input` and `ctx` may contain secrets, non-finite numbers, malformed Unicode,
    # or deeply nested structures. Clients only need location, type and message.
    detail = [
        {
            "type": _safe_label(error.get("type", "value_error"), 80),
            "loc": [
                part if isinstance(part, int) else _safe_label(part, 40)
                for part in error.get("loc", ())[:6]
            ],
            "msg": _safe_label(error.get("msg", "Invalid input"), 256),
        }
        for error in exc.errors()[:8]
    ]
    return JSONResponse(status_code=422, content={"detail": detail})
