"""Errors as application/problem+json with a stable ``code`` (RFC 9457, SDD 9.4)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

PROBLEM = "application/problem+json"
_CODES = {400: "invalid_request", 403: "forbidden", 404: "not_found", 405: "method_not_allowed", 409: "conflict"}


class ApiProblem(Exception):
    def __init__(self, status: int, code: str, detail: str):
        super().__init__(detail)
        self.status, self.code, self.detail = status, code, detail


def not_found(what: str) -> ApiProblem:
    return ApiProblem(404, "not_found", f"Không có {what}.")


def problem(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse({"type": "about:blank", "title": code, "status": status, "detail": detail, "code": code},
                        status_code=status, media_type=PROBLEM)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiProblem)
    async def _api_problem(request: Request, e: ApiProblem) -> JSONResponse:
        return problem(e.status, e.code, e.detail)

    @app.exception_handler(HTTPException)
    async def _http(request: Request, e: HTTPException) -> JSONResponse:
        return problem(e.status_code, _CODES.get(e.status_code, "error"), str(e.detail))

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, e: RequestValidationError) -> JSONResponse:
        fields = "; ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors())
        return problem(400, "invalid_request", fields)
