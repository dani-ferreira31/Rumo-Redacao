"""OpenAI: Responses API com saída estruturada (`responses.parse` + modelo Pydantic)."""

import base64
from typing import Any

import openai
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

# Raciocínio conta como saída: folga para não cortar a resposta.
MIN_OUTPUT_TOKENS = 32000
# Modelos de chat/raciocínio; o resto da lista (áudio, imagem, embeddings...) não serve.
_EXCLUDE = (
    "audio",
    "tts",
    "embedding",
    "whisper",
    "dall-e",
    "image",
    "realtime",
    "transcribe",
    "search",
    "moderation",
    "babbage",
    "davinci",
)


def _data_url(media_type: str, data: bytes) -> str:
    return f"data:{media_type};base64,{base64.standard_b64encode(data).decode('ascii')}"


def _item(part: Part) -> dict[str, Any]:
    if isinstance(part, TextPart):
        return {"type": "input_text", "text": part.text}
    if isinstance(part, ImagePart):
        return {
            "type": "input_image",
            "image_url": _data_url(part.media_type, part.data),
            "detail": "high",
        }
    if isinstance(part, PdfPart):
        return {
            "type": "input_file",
            "filename": part.filename,
            "file_data": _data_url("application/pdf", part.data),
        }
    raise TypeError(part)


def _refusal(response: Any) -> str | None:
    for item in response.output or []:
        for content in getattr(item, "content", None) or []:
            if getattr(content, "type", None) == "refusal":
                return getattr(content, "refusal", None) or "refusal"
    return None


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str = "", sdk: Any = None):
        settings = get_settings()
        self.sdk = sdk or openai.AsyncOpenAI(
            api_key=api_key or None,
            timeout=settings.ai_timeout_seconds,
            max_retries=settings.ai_max_retries,
        )

    def _input(self, history: list[Turn]) -> list[dict[str, Any]]:
        out = []
        for turn in history:
            if turn.role == "user":
                out.append({"role": "user", "content": [_item(p) for p in turn.parts or []]})
            else:
                out.append({"role": "assistant", "content": turn.reply.native or ""})
        return out

    async def send(self, request: AIRequest[Any], history: list[Turn]) -> ProviderReply:
        kwargs: dict[str, Any] = {
            "model": request.model,
            "instructions": request.system_text(),
            "input": self._input(history),
            "text_format": request.output_type,
            "max_output_tokens": max(request.max_tokens, MIN_OUTPUT_TOKENS),
            "store": False,
        }
        if request.config.effort:
            kwargs["reasoning"] = {"effort": request.config.effort}
        try:
            response = await self.sdk.responses.parse(**kwargs)
        except pydantic.ValidationError as exc:
            return ProviderReply(output=None, stop="ok", model=request.model, problem=str(exc))

        u = response.usage
        cached = getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0
        written = getattr(getattr(u, "input_tokens_details", None), "cache_write_tokens", 0) or 0
        reason = getattr(response.incomplete_details, "reason", None)
        refusal = _refusal(response)
        if refusal or reason == "content_filter":
            stop = "refusal"
        elif reason == "max_output_tokens":
            stop = "max_tokens"
        else:
            stop = "ok"
        output = response.output_parsed
        return ProviderReply(
            output=output,
            stop=stop,
            model=response.model,
            # input_tokens da OpenAI já inclui o que veio do cache
            input_tokens=max((u.input_tokens if u else 0) - cached - written, 0),
            output_tokens=u.output_tokens if u else 0,
            cache_read_tokens=cached,
            cache_write_tokens=written,
            request_id=getattr(response, "_request_id", None),
            refusal_category=refusal if refusal else reason,
            problem=None if output is not None else "resposta sem JSON",
            native=response.output_text,
        )

    async def list_models(self) -> list[ModelInfo]:
        models = [m async for m in self.sdk.models.list()]
        ids = sorted((m.id for m in models if not any(x in m.id for x in _EXCLUDE)), reverse=True)
        return [ModelInfo(i) for i in ids]
