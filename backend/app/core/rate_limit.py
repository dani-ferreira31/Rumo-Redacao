"""Rate limit em memória (slowapi). Suficiente com 1 instância da API.

O IP vem de request.client, que o uvicorn preenche a partir do X-Forwarded-For
(--proxy-headers) quando a API está atrás do Nginx Proxy Manager ou do rewrite do Next.
"""

from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.errors import error_response

limiter = Limiter(key_func=get_remote_address, headers_enabled=False)


def register_rate_limit(app: FastAPI) -> None:
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(_: Request, exc: RateLimitExceeded):
        return error_response(
            429,
            "rate_limited",
            "Muitas tentativas. Aguarde um pouco e tente de novo.",
            {"limit": str(exc.limit.limit)},
        )
