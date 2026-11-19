"""Domain errors with stable codes, and the response envelope (docs/API.md §1.3)."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("stitchsense")


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def not_found(what: str = "Resource") -> AppError:
    return AppError(404, "NOT_FOUND", f"{what} not found.")


def ok(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": True, "data": data, "error": None, "meta": meta or {}}


# Bangla text for the errors people meet most. Anything not listed is shown in English.
BN: dict[str, str] = {
    "UNAUTHENTICATED": "চালিয়ে যেতে লগ ইন করুন।",
    "INVALID_CREDENTIALS": "ইমেইল বা পাসওয়ার্ড ঠিক নয়।",
    "FORBIDDEN": "আপনার ভূমিকায় এটি করা যায় না।",
    "NOT_FOUND": "খুঁজে পাওয়া যায়নি।",
    "METHOD_NOT_ALLOWED": "এই কাজটি অনুমোদিত নয়।",
    "RATE_LIMITED": "অনেকবার চেষ্টা হয়েছে। একটু পরে আবার চেষ্টা করুন।",
    "VALIDATION_ERROR": "কিছু তথ্য ঠিক নয়।",
    "INTERNAL_ERROR": "কিছু একটা ভুল হয়েছে। আবার চেষ্টা করুন।",
    "CSRF_FAILED": "নিরাপত্তা যাচাই ব্যর্থ। পাতাটি নতুন করে খুলুন।",
    "ALREADY_REVIEWED": "এটি আগেই যাচাই করা হয়েছে।",
    "ALREADY_RESOLVED": "এটি আগেই সমাধান হয়েছে।",
    "ALREADY_QUARANTINED": "এই লটটি আগেই আলাদা করা হয়েছে।",
    "ASSIGNMENT_OVERLAP": "এই সময়ে আগে থেকেই একটি নিয়োগ আছে।",
    "DUPLICATE": "এটি আগেই আছে।",
    "POLICY_ALREADY_SCHEDULED": "একটি পরিবর্তন আগেই নির্ধারিত আছে। সেটি শুরু হওয়া পর্যন্ত অপেক্ষা করুন।",
    "POLICY_IN_PAST": "নতুন সংস্করণ অতীতে শুরু হতে পারে না।",
}


def wants_bangla(request: Request) -> bool:
    return request.headers.get("accept-language", "").lower().startswith("bn")


def _err(status: int, code: str, message: str, details: Any = None, request: Request | None = None) -> JSONResponse:
    if request is not None and wants_bangla(request):
        message = BN.get(code, message)
    body = {"success": False, "data": None, "error": {"code": code, "message": message, "details": details}}
    return JSONResponse(status_code=status, content=body)


_HTTP_CODES = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 429: "RATE_LIMITED"}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return _err(exc.status, exc.code, exc.message, exc.details, request)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return _err(400, "VALIDATION_ERROR", "Some fields are invalid.", {"fields": fields}, request)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _err(exc.status_code, _HTTP_CODES.get(exc.status_code, "HTTP_ERROR"), str(exc.detail), None, request)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return _err(500, "INTERNAL_ERROR", "Something went wrong. Try again.", None, request)
