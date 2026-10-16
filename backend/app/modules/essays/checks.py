"""ETAPA 2: checagens objetivas sobre o texto confirmado (sem IA).

Formato do texto: uma linha física por linha; parágrafos separados por linha
em branco. Em redações digitadas, cada parágrafo é uma linha lógica e a
contagem de linhas da folha é estimada (~10 palavras por linha).
"""

import math
import re
import unicodedata
from dataclasses import dataclass, field

from app.core.enums import EssayInputType, EssayZeroReason

MIN_LINES = 8  # até 7 linhas = texto insuficiente
MAX_LINES = 30
WORDS_PER_SHEET_LINE = 10
NGRAM = 8

MARKER_RE = re.compile(r"\[ilegível\]|\[\?[^\]]*\]")
_WORD_RE = re.compile(r"[\wÀ-ÿ]+(?:[-'][\wÀ-ÿ]+)*", re.UNICODE)


@dataclass
class CheckResult:
    line_count: int
    own_line_count: int
    paragraph_count: int
    word_count: int
    avg_words_per_sentence: float
    copied_lines: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    zero_reason: EssayZeroReason | None = None
    estimated_lines: bool = False

    @property
    def annulled(self) -> bool:
        return self.zero_reason is not None


def find_markers(text: str) -> list[tuple[int, str]]:
    """Marcadores de dúvida ([ilegível], [?palavra]) com o número da linha (1-based)."""
    found = []
    for i, line in enumerate(text.splitlines(), start=1):
        found.extend((i, m.group(0)) for m in MARKER_RE.finditer(line))
    return found


def physical_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def paragraphs(text: str) -> list[str]:
    blocks = re.split(r"\n\s*\n", text.strip())
    return [" ".join(b.split()) for b in blocks if b.strip()]


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def words(text: str) -> list[str]:
    return _WORD_RE.findall(_normalize(text))


def _ngrams(tokens: list[str], n: int = NGRAM) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def copied_line_numbers(lines: list[str], reference: str | None) -> list[int]:
    """Linhas (1-based) que contêm sequências de 8+ palavras dos textos motivadores.

    O n-grama é procurado no texto corrido, porque uma frase copiada costuma
    atravessar a quebra de linha; toda linha tocada por ele conta como cópia.
    """
    if not reference:
        return []
    ref = _ngrams(words(reference))
    if not ref:
        return []
    tokens: list[str] = []
    owner: list[int] = []
    for number, line in enumerate(lines, start=1):
        for token in words(line):
            tokens.append(token)
            owner.append(number)
    copied: set[int] = set()
    for i in range(len(tokens) - NGRAM + 1):
        if tuple(tokens[i : i + NGRAM]) in ref:
            copied.update(owner[i : i + NGRAM])
    return sorted(copied)


def run_checks(
    text: str, input_type: EssayInputType, motivating_texts: str | None = None
) -> CheckResult:
    text = MARKER_RE.sub(" ", text or "")
    all_words = words(text)
    sentences = [s for s in re.split(r"[.!?]+", text) if words(s)]
    paras = paragraphs(text)
    avg = round(len(all_words) / len(sentences), 1) if sentences else 0.0

    if input_type == EssayInputType.text:
        # cada parágrafo ocupa pelo menos uma linha da folha
        lines = paras
        line_count = sum(max(1, math.ceil(len(words(p)) / WORDS_PER_SHEET_LINE)) for p in paras)
        estimated = True
    else:
        lines = physical_lines(text)
        line_count = len(lines)
        estimated = False

    copied = copied_line_numbers(lines, motivating_texts)
    if estimated and copied:
        copied_count = sum(
            max(1, math.ceil(len(words(lines[i - 1])) / WORDS_PER_SHEET_LINE)) for i in copied
        )
    else:
        copied_count = len(copied)
    own = max(0, line_count - copied_count)

    result = CheckResult(
        line_count=line_count,
        own_line_count=own,
        paragraph_count=len(paras),
        word_count=len(all_words),
        avg_words_per_sentence=avg,
        copied_lines=copied,
        estimated_lines=estimated,
    )
    if not all_words:
        result.zero_reason = EssayZeroReason.folha_em_branco
    elif line_count < MIN_LINES:
        result.zero_reason = EssayZeroReason.texto_insuficiente
    elif copied and own < MIN_LINES:
        result.zero_reason = EssayZeroReason.copia_textos_motivadores

    if line_count > MAX_LINES:
        result.warnings.append(
            f"O texto tem {line_count} linhas. No ENEM, o que passa da linha 30 não é considerado."
        )
    if copied:
        result.warnings.append(
            f"{len(copied)} linha(s) com trechos copiados dos textos motivadores não contam como "
            "texto próprio."
        )
    if estimated:
        result.warnings.append(
            "Redação digitada: a contagem de linhas é uma estimativa (cerca de 10 palavras por "
            "linha da folha oficial)."
        )
    return result
