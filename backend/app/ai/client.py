"""Ponto único de acesso aos provedores de IA. Todo uso é registrado em `ai_usage`.

Nenhum módulo chama um SDK diretamente: usam `get_ai_client().parse(...)` com um
`AIRequest` neutro (partes de texto, imagem e PDF). O provedor, o modelo e a
chave vêm da configuração da tarefa (`app/ai/config.py`, editável no painel).

A saída é sempre estruturada (modelo Pydantic). Validações de negócio extras são
feitas por quem chama, via `validate`; se falharem, a IA recebe os erros e tem
uma nova chance.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.catalog import estimate_cost, pricing_table
from app.ai.models import AIUsage
from app.ai.types import (
    AIConfigError,
    AIError,
    AIIncompleteError,
    AIRefusalError,
    AIRequest,
    AIResult,
    AIValidationError,
    ImagePart,
    ModelInfo,
    Part,
    PdfPart,
    ProviderReply,
    T,
    TaskConfig,
    TextPart,
    Turn,
)

__all__ = [
    "AIClient",
    "AIConfigError",
    "AIError",
    "AIIncompleteError",
    "AIRefusalError",
    "AIRequest",
    "AIResult",
    "AIValidationError",
    "ImagePart",
    "Part",
    "PdfPart",
    "TaskConfig",
    "TextPart",
    "get_ai_client",
    "save_usage",
]

logger = logging.getLogger(__name__)

ProviderFactory = Callable[[str], Any]


def _default_factories() -> dict[str, ProviderFactory]:
    # importações tardias: cada SDK só carrega quando o provedor é usado
    def anthropic_(key: str):
        from app.ai.providers.anthropic import AnthropicProvider

        return AnthropicProvider(api_key=key)

    def openai_(key: str):
        from app.ai.providers.openai import OpenAIProvider

        return OpenAIProvider(api_key=key)

    def google_(key: str):
        from app.ai.providers.google import GoogleProvider

        return GoogleProvider(api_key=key)

    def fake_(_: str):
        from app.ai.fake import FakeProvider

        return FakeProvider()

    return {"anthropic": anthropic_, "openai": openai_, "google": google_, "fake": fake_}


class AIClient:
    def __init__(self, factories: dict[str, ProviderFactory] | None = None):
        self.factories = factories or _default_factories()
        self._providers: dict[tuple[str, str], Any] = {}

    def provider(self, name: str, api_key: str) -> Any:
        factory = self.factories.get(name)
        if factory is None:
            raise AIConfigError(f"Provedor de IA desconhecido: {name!r}")
        if name != "fake" and not api_key:
            raise AIConfigError(
                f"Nenhuma chave de API configurada para {name}. Cadastre em Admin → IA."
            )
        cache_key = (name, hashlib.sha256(api_key.encode()).hexdigest())
        if cache_key not in self._providers:
            self._providers[cache_key] = factory(api_key)
        return self._providers[cache_key]

    async def list_models(self, name: str, api_key: str) -> list[ModelInfo]:
        return await self.provider(name, api_key).list_models()

    def _usage_row(self, request: AIRequest[Any], reply: ProviderReply, ms: int) -> AIUsage:
        return AIUsage(
            user_id=request.user_id,
            essay_id=request.essay_id,
            contest_exam_id=request.contest_exam_id,
            purpose=request.purpose,
            provider=request.config.provider,
            model=reply.model,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            cache_read_tokens=reply.cache_read_tokens,
            cache_write_tokens=reply.cache_write_tokens,
            cost_usd=None,  # calculado em save_usage, com a tabela de preços do painel
            latency_ms=ms,
            request_id=reply.request_id,
        )

    async def parse(self, request: AIRequest[T]) -> AIResult[T]:
        provider = self.provider(request.config.provider, request.config.api_key)
        history = [Turn("user", parts=list(request.content))]
        usage: list[AIUsage] = []
        last_problem = ""
        for attempt in (1, 2):
            started = time.perf_counter()
            reply = await provider.send(request, history)
            usage.append(
                self._usage_row(request, reply, int((time.perf_counter() - started) * 1000))
            )

            if reply.stop == "refusal":
                refusal = AIRefusalError(reply.refusal_category)
                refusal.usage = usage
                raise refusal
            if reply.stop == "max_tokens":
                cut = AIIncompleteError("A resposta da IA foi cortada (limite de tokens).")
                cut.usage = usage
                raise cut
            if reply.output is None:
                last_problem = reply.problem or "resposta sem conteúdo estruturado"
                logger.warning("ai_schema_error", extra={"extra_fields": {"attempt": attempt}})
                continue

            problems = list(request.validate(reply.output)) if request.validate else []
            if not problems:
                return AIResult(
                    output=reply.output,  # type: ignore[arg-type]
                    model=reply.model,
                    provider=request.config.provider,
                    usage=usage,
                )

            last_problem = "; ".join(problems)
            logger.warning(
                "ai_validation_failed",
                extra={"extra_fields": {"attempt": attempt, "problems": problems}},
            )
            # Mantém o histórico intacto (só acrescenta) e pede a correção.
            history = [
                *history,
                Turn("assistant", reply=reply),
                Turn(
                    "user",
                    parts=[
                        TextPart(
                            "Sua resposta tem problemas que impedem o uso: "
                            f"{last_problem}. Refaça a resposta completa corrigindo esses pontos."
                        )
                    ],
                ),
            ]
        exc = AIValidationError(f"Resposta da IA inválida após 2 tentativas: {last_problem}")
        exc.usage = usage
        raise exc


async def save_usage(session: AsyncSession, result: AIResult[Any] | list[AIUsage]) -> None:
    """Calcula o custo pela tabela de preços e adiciona os registros à sessão (sem commit)."""
    from app.modules.system.settings import get_setting

    rows = result if isinstance(result, list) else result.usage
    table = pricing_table(await get_setting(session, "ai_pricing"))
    for row in rows:
        if row.cost_usd is None:
            row.cost_usd = estimate_cost(
                table,
                row.model,
                row.input_tokens,
                row.output_tokens,
                row.cache_read_tokens,
                row.cache_write_tokens,
            )
    session.add_all(rows)


@lru_cache
def get_ai_client() -> AIClient:
    return AIClient()
