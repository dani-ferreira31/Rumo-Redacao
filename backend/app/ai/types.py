"""Tipos neutros de pedido e resposta, iguais para todos os provedores de IA."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeVar

import pydantic

from app.ai.models import AIUsage
from app.core.enums import AIPurpose

T = TypeVar("T", bound=pydantic.BaseModel)


# ---- partes do conteúdo -------------------------------------------------------


@dataclass(frozen=True)
class TextPart:
    text: str
    # Marca o fim de um prefixo estável (ex.: a rubrica) para o cache do provedor.
    cache: bool = False


@dataclass(frozen=True, repr=False)
class ImagePart:
    data: bytes
    media_type: str = "image/jpeg"

    def __repr__(self) -> str:
        return f"ImagePart({self.media_type}, {len(self.data)} bytes)"


@dataclass(frozen=True, repr=False)
class PdfPart:
    data: bytes
    filename: str = "documento.pdf"

    def __repr__(self) -> str:
        return f"PdfPart({self.filename}, {len(self.data)} bytes)"


Part = TextPart | ImagePart | PdfPart


# ---- configuração e pedido ----------------------------------------------------


@dataclass(frozen=True)
class TaskConfig:
    provider: str
    model: str
    effort: str | None = None
    api_key: str = field(default="", repr=False)


@dataclass
class AIRequest(Generic[T]):
    purpose: AIPurpose
    config: TaskConfig
    system: list[TextPart]
    content: list[Part]
    output_type: type[T]
    max_tokens: int = 16000
    user_id: uuid.UUID | None = None
    essay_id: uuid.UUID | None = None
    contest_exam_id: int | None = None
    # Regras de negócio além do schema: devolve a lista de problemas (vazia = ok).
    validate: Callable[[T], Sequence[str]] | None = None

    @property
    def model(self) -> str:
        return self.config.model

    def system_text(self) -> str:
        return "\n\n".join(p.text for p in self.system)


@dataclass
class AIResult(Generic[T]):
    output: T
    model: str
    provider: str
    usage: list[AIUsage] = field(default_factory=list)


# ---- conversa (para pedir correção após validação) ----------------------------


@dataclass
class ProviderReply:
    """Resposta normalizada de um provedor."""

    output: pydantic.BaseModel | None
    stop: Literal["ok", "refusal", "max_tokens"]
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    request_id: str | None = None
    refusal_category: str | None = None
    # Motivo quando `output` veio vazio (ex.: JSON fora do schema).
    problem: str | None = None
    # Conteúdo da resposta no formato do provedor, para continuar a conversa.
    native: Any = None


@dataclass
class Turn:
    role: Literal["user", "assistant"]
    parts: list[Part] | None = None
    reply: ProviderReply | None = None


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str | None = None


# ---- erros --------------------------------------------------------------------


class AIError(Exception):
    """Falha da IA que não adianta repetir com o mesmo pedido."""

    # Chamadas já cobradas antes da falha (para o relatório de custos).
    usage: list[AIUsage] = []


class AIConfigError(AIError):
    """Provedor sem chave, chave ilegível ou provedor desconhecido."""


class AIRefusalError(AIError):
    def __init__(self, category: str | None):
        super().__init__(f"A IA recusou o pedido (categoria: {category or 'desconhecida'})")
        self.category = category


class AIIncompleteError(AIError):
    pass


class AIValidationError(AIError):
    pass
