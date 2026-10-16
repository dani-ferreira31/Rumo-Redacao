"""ETAPA 3: uma correção independente (um "corretor")."""

import uuid
from dataclasses import dataclass

from app.ai.client import AIRequest, AIResult, TaskConfig, TextPart, get_ai_client
from app.ai.prompts import load_prompt
from app.ai.schemas import GradingOutput
from app.core.enums import AIPurpose
from app.modules.essays.checks import CheckResult
from app.modules.essays.consolidation import validate_grading


@dataclass(frozen=True)
class GradingInput:
    theme_title: str
    motivating_texts: str | None
    text: str
    checks: CheckResult


def prompt_version() -> str:
    return f"{load_prompt('correcao_sistema').version}+{load_prompt('rubrica').version}"


def system_blocks() -> list[TextPart]:
    """Instruções + grade: estáticas, com cache (as correções seguintes leem do cache)."""
    return [
        TextPart(load_prompt("correcao_sistema").text),
        TextPart(load_prompt("rubrica").text, cache=True),
    ]


def numbered(text: str) -> str:
    """Numera as linhas não vazias como [L01] (linhas em branco separam parágrafos)."""
    out, n = [], 0
    for line in text.splitlines():
        if not line.strip():
            out.append("")
            continue
        n += 1
        out.append(f"[L{n:02d}] {line.strip()}")
    return "\n".join(out)


def user_message(data: GradingInput) -> str:
    c = data.checks
    parts = [f"## Tema\n{data.theme_title}"]
    if data.motivating_texts:
        parts.append(f"## Textos motivadores\n{data.motivating_texts}")
    checks = [
        f"- linhas de texto: {c.line_count}"
        + (" (estimativa: redação digitada)" if c.estimated_lines else ""),
        f"- linhas de texto próprio (sem cópia dos motivadores): {c.own_line_count}",
        f"- parágrafos: {c.paragraph_count}",
        f"- palavras: {c.word_count}",
        f"- média de palavras por frase: {c.avg_words_per_sentence}",
    ]
    if c.copied_lines:
        checks.append(
            "- linhas com trechos copiados dos textos motivadores: "
            + ", ".join(f"L{n:02d}" for n in c.copied_lines)
        )
    parts.append("## Checagens automáticas\n" + "\n".join(checks))
    parts.append(f"## Redação (linhas numeradas)\n{numbered(data.text)}")
    parts.append("Avalie a redação acima segundo a grade.")
    return "\n\n".join(parts)


async def grade_once(
    data: GradingInput,
    *,
    config: TaskConfig,
    user_id: uuid.UUID | None,
    essay_id: uuid.UUID | None,
) -> AIResult[GradingOutput]:
    return await get_ai_client().parse(
        AIRequest(
            purpose=AIPurpose.grading,
            config=config,
            system=system_blocks(),
            content=[TextPart(user_message(data))],
            output_type=GradingOutput,
            max_tokens=16000,
            user_id=user_id,
            essay_id=essay_id,
            validate=validate_grading,
        )
    )
