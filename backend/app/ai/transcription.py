"""ETAPA 1: transcrição literal da foto (visão)."""

import uuid

from app.ai.client import AIRequest, AIResult, ImagePart, Part, TaskConfig, TextPart, get_ai_client
from app.ai.prompts import load_prompt
from app.ai.schemas import TranscriptionOutput
from app.core.enums import AIPurpose


def _validate(output: TranscriptionOutput) -> list[str]:
    if not output.folha_em_branco and not output.linhas:
        return ["`linhas` está vazia mas `folha_em_branco` é false"]
    return []


async def transcribe(
    images_jpeg: list[bytes],
    *,
    config: TaskConfig,
    user_id: uuid.UUID,
    essay_id: uuid.UUID,
) -> tuple[AIResult[TranscriptionOutput], str]:
    """Devolve o resultado da IA e a versão do prompt usada."""
    prompt = load_prompt("transcricao")
    content: list[Part] = []
    for page, data in enumerate(images_jpeg, start=1):
        if len(images_jpeg) > 1:
            content.append(TextPart(f"Página {page}:"))
        content.append(ImagePart(data))
    content.append(
        TextPart("Transcreva literalmente a redação da(s) imagem(ns) acima, seguindo as regras.")
    )
    result = await get_ai_client().parse(
        AIRequest(
            purpose=AIPurpose.transcription,
            config=config,
            system=[TextPart(prompt.text)],
            content=content,
            output_type=TranscriptionOutput,
            max_tokens=16000,
            user_id=user_id,
            essay_id=essay_id,
            validate=_validate,
        )
    )
    return result, prompt.version


def transcription_to_text(output: TranscriptionOutput) -> str:
    """Uma linha física por linha; linha em branco entre parágrafos."""
    out: list[str] = []
    for i, line in enumerate(output.linhas):
        if line.inicia_paragrafo and i > 0:
            out.append("")
        out.append(line.texto.rstrip())
    return "\n".join(out)
