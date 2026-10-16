"""Anthropic: saída estruturada com `messages.parse` + modelo Pydantic."""

import base64
from typing import Any

import anthropic
import pydantic

from app.ai.types import (
    AIRequest,
    ImagePart,
    ModelInfo,
    Part,
    PdfPart,
    ProviderReply,
    TextPart,
    Turn,
)
from app.core.config import get_settings

FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _b64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("ascii")


def _block(part: Part) -> dict[str, Any]:
    if isinstance(part, TextPart):
        block: dict[str, Any] = {"type": "text", "text": part.text}
        if part.cache:
            block["cache_control"] = {"type": "ephemeral"}
        return block
    if isinstance(part, ImagePart):
        return {
            "type": "image",
            "source": {"type": "base64", "media_type": part.media_type, "data": _b64(part.data)},
        }
    if isinstance(part, PdfPart):
        return {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": _b64(part.data)},
        }
    raise TypeError(part)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str = "", sdk: Any = None):
        settings = get_settings()
        self.refusal_fallback = settings.anthropic_refusal_fallback
        self.sdk = sdk or anthropic.AsyncAnthropic(
            api_key=api_key or None,
            timeout=settings.ai_timeout_seconds,
            max_retries=settings.ai_max_retries,
        )

    def _messages(self, history: list[Turn]) -> list[dict[str, Any]]:
        out = []
        for turn in history:
            if turn.role == "user":
                out.append({"role": "user", "content": [_block(p) for p in turn.parts or []]})
            else:
                out.append({"role": "assistant", "content": turn.reply.native})
        return out

    async def send(self, request: AIRequest[Any], history: list[Turn]) -> ProviderReply:
        kwargs: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "system": [_block(p) for p in request.system],
            "messages": self._messages(history),
            "output_format": request.output_type,
        }
        if request.config.effort:
            kwargs["output_config"] = {"effort": request.config.effort}
        if self.refusal_fallback:
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        try:
            response = await self.sdk.beta.messages.parse(**kwargs)
        except pydantic.ValidationError as exc:  # JSON fora do schema (raro)
            return ProviderReply(output=None, stop="ok", model=request.model, problem=str(exc))

        u = response.usage
        stop = {"refusal": "refusal", "max_tokens": "max_tokens"}.get(response.stop_reason, "ok")
        details = getattr(response, "stop_details", None)
        return ProviderReply(
            output=response.parsed_output,
            stop=stop,
            model=response.model,
            input_tokens=u.input_tokens or 0,
            output_tokens=u.output_tokens or 0,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
            request_id=getattr(response, "_request_id", None),
            refusal_category=getattr(details, "category", None),
            problem=None if response.parsed_output is not None else "resposta sem JSON",
            native=response.content,
        )

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(m.id, getattr(m, "display_name", None))
            async for m in self.sdk.models.list(limit=100)
        ]
