"""Formato padrão de erro: {"error": {"code", "message", "details"}}."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.headers = headers


class NotFoundError(AppError):
    def __init__(self, message: str = "Recurso não encontrado.", code: str = "not_found"):
        super().__init__(code, message, 404)


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or {}}},
        headers=headers,
    )


_HTTP_DEFAULTS = {
    400: ("bad_request", "Requisição inválida."),
    401: ("unauthorized", "Autenticação necessária."),
    403: ("forbidden", "Você não tem permissão para esta ação."),
    404: ("not_found", "Recurso não encontrado."),
    405: ("method_not_allowed", "Método não permitido."),
    409: ("conflict", "Conflito com o estado atual do recurso."),
    413: ("payload_too_large", "Arquivo ou requisição grande demais."),
    429: ("rate_limited", "Muitas tentativas. Aguarde um pouco e tente de novo."),
}


def _validation_details(exc: RequestValidationError) -> dict[str, Any]:
    fields = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
        fields.append({"field": ".".join(loc), "message": err.get("msg"), "type": err.get("type")})
    return {"fields": fields}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        # Erros do framework vêm em inglês; nossas regras usam AppError com texto em pt-BR.
        code, message = _HTTP_DEFAULTS.get(exc.status_code, ("http_error", "Erro."))
        return error_response(exc.status_code, code, message, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        return error_response(
            422, "validation_error", "Alguns campos são inválidos.", _validation_details(exc)
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        logger.exception("unhandled_error")
        return error_response(500, "internal_error", "Erro interno. Tente novamente mais tarde.")
