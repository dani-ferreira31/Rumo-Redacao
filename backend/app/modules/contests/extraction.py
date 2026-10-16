"""Leitura do PDF da prova e do gabarito com IA.

A prova vai em trechos de CHUNK_PAGES páginas (mais 1 página extra, para
completar a questão que continua na página seguinte). Cada trecho devolve as
questões que COMEÇAM nas suas páginas principais; o gabarito vai numa chamada
separada. Nada aqui grava no banco: quem chama junta e salva.
"""

import asyncio
import io
from dataclasses import dataclass, field
from typing import Any

import pypdfium2 as pdfium

from app.ai.client import AIRequest, AIResult, PdfPart, TaskConfig, TextPart, get_ai_client
from app.ai.prompts import load_prompt
from app.core.enums import AIPurpose
from app.modules.contests.ai_schemas import (
    ExtracaoProva,
    Gabarito,
    QuestaoExtraida,
    validate_extraction,
)

CHUNK_PAGES = 8
MAX_PAGES = 150
MAX_ANSWER_KEY_PAGES = 20
PAGE_IMAGE_LONG_EDGE = 1600
# Estimativa grosseira de tokens por página (para mostrar o custo antes de importar).
EST_INPUT_TOKENS_PER_PAGE = 3000
EST_OUTPUT_TOKENS_PER_PAGE = 1500


class PdfError(Exception):
    """PDF ilegível, protegido ou grande demais (não adianta repetir)."""


def page_count(data: bytes) -> int:
    try:
        doc = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        raise PdfError(
            "Não consegui abrir o PDF (arquivo corrompido ou protegido por senha)."
        ) from exc
    try:
        return len(doc)
    finally:
        doc.close()


def pdf_slice(data: bytes, start: int, end: int) -> bytes:
    """Páginas [start, end) (base 0) como um novo PDF."""
    src = pdfium.PdfDocument(data)
    out = pdfium.PdfDocument.new()
    try:
        out.import_pages(src, list(range(start, end)))
        buf = io.BytesIO()
        out.save(buf)
        return buf.getvalue()
    finally:
        out.close()
        src.close()


def render_pages(data: bytes, long_edge: int = PAGE_IMAGE_LONG_EDGE) -> list[bytes]:
    """Cada página como JPEG (para a revisão lado a lado e o recorte de figuras)."""
    doc = pdfium.PdfDocument(data)
    images = []
    try:
        for page in doc:
            w, h = page.get_size()
            scale = long_edge / max(w, h)
            pil = page.render(scale=scale).to_pil().convert("RGB")
            buf = io.BytesIO()
            pil.save(buf, "JPEG", quality=85, optimize=True)
            images.append(buf.getvalue())
            page.close()
    finally:
        doc.close()
    return images


@dataclass(frozen=True)
class Chunk:
    start: int  # base 0, inclusivo
    primary_end: int  # exclusivo
    end: int  # exclusivo, com a página extra


def chunks(pages: int, size: int = CHUNK_PAGES) -> list[Chunk]:
    out = []
    for start in range(0, pages, size):
        primary_end = min(start + size, pages)
        out.append(Chunk(start, primary_end, min(primary_end + 1, pages)))
    return out


@dataclass
class ExamMeta:
    board: str
    organization: str
    position: str
    year: int
    booklet: str | None
    subjects: list[str]


@dataclass
class Extraction:
    questions: dict[int, QuestaoExtraida] = field(default_factory=dict)  # pagina = absoluta
    notes: list[str] = field(default_factory=list)
    results: list[AIResult[Any]] = field(default_factory=list)


def _chunk_message(meta: ExamMeta, chunk: Chunk, pages: int) -> str:
    n = chunk.end - chunk.start
    primary = chunk.primary_end - chunk.start
    extra = (
        f" A página {n} deste trecho é extra: use-a só para completar a última questão."
        if n > primary
        else ""
    )
    return (
        f"Prova: {meta.board} · {meta.organization} · {meta.position} ({meta.year}).\n"
        f"Este trecho tem as páginas {chunk.start + 1} a {chunk.end} da prova (de {pages}). "
        f"Numere `pagina` de 1 a {n} dentro deste trecho. "
        f"Páginas principais: 1 a {primary}.{extra}\n"
        f"Disciplinas disponíveis: {', '.join(meta.subjects)}.\n"
        "Extraia as questões seguindo as regras."
    )


async def extract_questions(
    data: bytes, meta: ExamMeta, config: TaskConfig, contest_exam_id: int
) -> Extraction:
    pages = page_count(data)
    prompt = load_prompt("extracao_concurso")
    client = get_ai_client()

    async def one(chunk: Chunk) -> tuple[Chunk, AIResult[ExtracaoProva]]:
        part = await asyncio.to_thread(pdf_slice, data, chunk.start, chunk.end)
        result = await client.parse(
            AIRequest(
                purpose=AIPurpose.contest_extraction,
                config=config,
                system=[TextPart(prompt.text, cache=True)],
                content=[
                    PdfPart(part, f"prova-p{chunk.start + 1}-{chunk.end}.pdf"),
                    TextPart(_chunk_message(meta, chunk, pages)),
                ],
                output_type=ExtracaoProva,
                max_tokens=32000,
                contest_exam_id=contest_exam_id,
                validate=validate_extraction,
            )
        )
        return chunk, result

    out = Extraction()
    sem = asyncio.Semaphore(3)

    async def limited(chunk: Chunk):
        async with sem:
            return await one(chunk)

    for chunk, result in await asyncio.gather(*(limited(c) for c in chunks(pages))):
        out.results.append(result)
        if result.output.observacoes.strip():
            out.notes.append(result.output.observacoes.strip())
        for q in result.output.questoes:
            q = q.model_copy(update={"pagina": min(chunk.start + max(q.pagina, 1), pages)})
            current = out.questions.get(q.numero)
            # a mesma questão pode vir em dois trechos (página extra): fica a mais completa
            if current is None or len(q.enunciado) > len(current.enunciado):
                out.questions[q.numero] = q
    return out


async def read_answer_key(
    data: bytes, meta: ExamMeta, numbers: list[int], config: TaskConfig, contest_exam_id: int
) -> AIResult[Gabarito]:
    pages = page_count(data)
    if pages > MAX_ANSWER_KEY_PAGES:
        data = await asyncio.to_thread(pdf_slice, data, 0, MAX_ANSWER_KEY_PAGES)
    expected = f"{min(numbers)} a {max(numbers)}" if numbers else "desconhecidas"
    message = (
        f"Prova: {meta.board} · {meta.organization} · cargo {meta.position} ({meta.year}).\n"
        f"Caderno: {meta.booklet or 'não informado'}.\n"
        f"Questões esperadas: {expected} ({len(numbers)} no total).\n"
        "Leia o gabarito seguindo as regras."
    )
    prompt = load_prompt("gabarito_concurso")
    return await get_ai_client().parse(
        AIRequest(
            purpose=AIPurpose.contest_extraction,
            config=config,
            system=[TextPart(prompt.text)],
            content=[PdfPart(data, "gabarito.pdf"), TextPart(message)],
            output_type=Gabarito,
            max_tokens=16000,
            contest_exam_id=contest_exam_id,
        )
    )


def prompt_versions() -> str:
    return f"{load_prompt('extracao_concurso').version}+{load_prompt('gabarito_concurso').version}"
