"""Google (Gemini): saída JSON com `response_json_schema` gerado do modelo Pydantic."""

import asyncio
import logging
import random
import re
from typing import Any

import pydantic
from google import genai
from google.genai import errors, types

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

logger = logging.getLogger(__name__)

MIN_OUTPUT_TOKENS = 32000
# Cota por minuto (429) e sobrecarga (500/503) são temporárias: espera e tenta de novo.
RETRY_STATUS = {429, 500, 503}
MAX_RETRY_DELAY = 65.0


def retry_delay(exc: errors.APIError, attempt: int) -> float:
    """Usa o `retryDelay` que o Google manda no 429; senão, espera exponencial."""
    match = re.search(r"'retryDelay': '(\d+(?:\.\d+)?)s'", str(exc.details))
    if match:
        return min(float(match.group(1)) + 1, MAX_RETRY_DELAY)
    return min(2**attempt * 2 + random.random(), MAX_RETRY_DELAY)


LEVELS = {
    "minimal": types.ThinkingLevel.MINIMAL,
    "low": types.ThinkingLevel.LOW,
    "medium": types.ThinkingLevel.MEDIUM,
    "high": types.ThinkingLevel.HIGH,
}
_REFUSAL = {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "IMAGE_SAFETY"}


def _part(part: Part) -> types.Part:
    if isinstance(part, TextPart):
        return types.Part.from_text(text=part.text)
    if isinstance(part, ImagePart):
        return types.Part.from_bytes(data=part.data, mime_type=part.media_type)
    if isinstance(part, PdfPart):
        return types.Part.from_bytes(data=part.data, mime_type="application/pdf")
    raise TypeError(part)


class GoogleProvider:
    name = "google"

    def __init__(self, api_key: str = "", sdk: Any = None, sleep=asyncio.sleep):
        settings = get_settings()
        self.max_retries = settings.ai_max_retries
        self.sleep = sleep
        self.sdk = sdk or genai.Client(
            api_key=api_key or None,
            http_options=types.HttpOptions(timeout=int(settings.ai_timeout_seconds * 1000)),
        )

    def _contents(self, history: list[Turn]) -> list[types.Content]:
        out = []
        for turn in history:
            if turn.role == "user":
                out.append(types.Content(role="user", parts=[_part(p) for p in turn.parts or []]))
            else:
                text = turn.reply.native or ""
                out.append(types.Content(role="model", parts=[types.Part.from_text(text=text)]))
        return out

    async def send(self, request: AIRequest[Any], history: list[Turn]) -> ProviderReply:
        config = types.GenerateContentConfig(
            system_instruction=request.system_text(),
            response_mime_type="application/json",
            response_json_schema=request.output_type.model_json_schema(),
            max_output_tokens=max(request.max_tokens, MIN_OUTPUT_TOKENS),
        )
        effort = request.config.effort
        if effort:
            config.thinking_config = types.ThinkingConfig(
                thinking_level=LEVELS.get(effort, types.ThinkingLevel.HIGH)
            )
        response = await self._generate(request.model, self._contents(history), config)

        u = response.usage_metadata
        cached = (u.cached_content_token_count or 0) if u else 0
        prompt = (u.prompt_token_count or 0) if u else 0
        output_tokens = (
            ((u.candidates_token_count or 0) + (u.thoughts_token_count or 0)) if u else 0
        )
        candidate = response.candidates[0] if response.candidates else None
        finish = candidate.finish_reason.name if candidate and candidate.finish_reason else None
        block = getattr(response.prompt_feedback, "block_reason", None)

        stop = "ok"
        category = None
        if block or finish in _REFUSAL:
            stop, category = "refusal", str(block.name if block else finish)
        elif finish == "MAX_TOKENS":
            stop = "max_tokens"

        text = response.text if stop == "ok" else None
        output = None
        problem = None
        if text:
            try:
                output = request.output_type.model_validate_json(text)
            except pydantic.ValidationError as exc:
                problem = str(exc)
        elif stop == "ok":
            problem = "resposta vazia"
        return ProviderReply(
            output=output,
            stop=stop,
            model=response.model_version or request.model,
            input_tokens=max(prompt - cached, 0),
            output_tokens=output_tokens,
            cache_read_tokens=cached,
            request_id=response.response_id,
            refusal_category=category,
            problem=problem,
            native=text,
        )

    async def _generate(self, model: str, contents: list, config: Any) -> Any:
        for attempt in range(self.max_retries + 1):
            try:
                return await self.sdk.aio.models.generate_content(
                    model=model, contents=contents, config=config
                )
            except errors.APIError as exc:
                if exc.code not in RETRY_STATUS or attempt == self.max_retries:
                    raise
                delay = retry_delay(exc, attempt)
                logger.warning(
                    "google_retry",
                    extra={"extra_fields": {"status": exc.code, "delay_s": round(delay, 1)}},
                )
                await self.sleep(delay)
        raise AssertionError("inalcançável")

    async def list_models(self) -> list[ModelInfo]:
        pager = await self.sdk.aio.models.list()
        out = []
        async for m in pager:
            actions = m.supported_actions or []
            if "generateContent" in actions and "gemini" in (m.name or ""):
                out.append(ModelInfo((m.name or "").removeprefix("models/"), m.display_name))
        return sorted(out, key=lambda m: m.id, reverse=True)
