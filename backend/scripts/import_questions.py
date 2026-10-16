"""Importa questões do ENEM combinando duas fontes públicas:

1. **enem.dev** (dados brutos do repositório yunger7/enem-api, pasta `public/`):
   enunciado em Markdown, imagens, alternativas e gabarito.
2. **Microdados do INEP** (opcional, arquivo `ITENS_PROVA_<ano>.csv`): código do
   item (CO_ITEM), habilidade (H1–H30), parâmetros da TRI e anulação.

O cruzamento é automático: para cada área, o script escolhe o caderno (CO_PROVA)
dos microdados cujo gabarito mais coincide com o do enem.dev, posição a posição.

A área vem da POSIÇÃO no caderno (o campo `discipline` do enem.dev tem erros):
- desde 2017: 1–45 LC, 46–90 CH (1º dia); 91–135 CN, 136–180 MT (2º dia);
- 2009–2016:  1–45 CH, 46–90 CN (1º dia); 91–135 LC, 136–180 MT (2º dia).

Tudo entra com `reviewed = false` para revisão no admin. Rodar de novo é seguro
(idempotente).

Uso:
    python -m scripts.import_questions --year 2023
    python -m scripts.import_questions --year 2023 --microdados data/inep/ITENS_PROVA_2023.csv
    python -m scripts.import_questions --year 2019 --year 2020 --year 2021
"""

import argparse
import asyncio
import csv
import json
import logging
import mimetypes
import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import delete, select

import app.models  # noqa: F401  (registra todas as tabelas no SQLAlchemy)
from app.core.db import SessionLocal, engine
from app.core.enums import ExamApplication, ForeignLanguage
from app.modules.questions.models import (
    Exam,
    ExamQuestion,
    KnowledgeArea,
    Question,
    QuestionAsset,
    QuestionOption,
    Subject,
)
from app.storage import get_storage

logger = logging.getLogger("import_questions")

SOURCE = "enem.dev"
REF_BOOKLET = "enem.dev"  # o caderno da numeração do enem.dev
IMAGE_URL_RE = re.compile(r"https?://enem\.dev/(\d{4})/questions/([^/\s)]+)/([^/\s)]+)")
LANG = {"ingles": ForeignLanguage.ingles, "espanhol": ForeignLanguage.espanhol}


def area_for(year: int, position: int) -> tuple[str, int]:
    """(código da área, dia) a partir da posição no caderno."""
    block = (position - 1) // 45  # 0..3
    order = ["LC", "CH", "CN", "MT"] if year >= 2017 else ["CH", "CN", "LC", "MT"]
    return order[block], 1 if block < 2 else 2


# ---- enem.dev -------------------------------------------------------------------


@dataclass
class SourceQuestion:
    folder: Path
    index: int
    language: ForeignLanguage | None
    context: str
    intro: str | None
    files: list[str]
    correct: str | None
    alternatives: list[dict]


def load_enem_dev(root: Path, year: int) -> list[SourceQuestion]:
    base = root / str(year) / "questions"
    if not base.is_dir():
        raise SystemExit(f"Ano {year} não encontrado em {root}")
    out = []
    for folder in sorted(base.iterdir()):
        details = folder / "details.json"
        if not details.is_file():
            continue
        q = json.loads(details.read_text(encoding="utf-8"))
        out.append(
            SourceQuestion(
                folder=folder,
                index=int(q["index"]),
                language=LANG.get(q.get("language") or ""),
                context=(q.get("context") or "").strip(),
                intro=(q.get("alternativesIntroduction") or "").strip() or None,
                files=q.get("files") or [],
                correct=q.get("correctAlternative"),
                alternatives=q.get("alternatives") or [],
            )
        )
    return out


# ---- microdados do INEP ---------------------------------------------------------


@dataclass
class Item:
    prova: str
    position: int
    area: str
    item_code: int | None
    answer: str | None
    skill: int | None
    annulled: bool
    a: Decimal | None
    b: Decimal | None
    c: Decimal | None
    color: str
    language: ForeignLanguage | None


def _num(value: str | None) -> Decimal | None:
    if value is None or not value.strip():
        return None
    try:
        return Decimal(value.strip().replace(",", "."))
    except InvalidOperation:
        return None


def _int(value: str | None) -> int | None:
    n = _num(value)
    return int(n) if n is not None else None


def load_microdados(path: Path) -> list[Item]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    header = text.split("\n", 1)[0]
    delimiter = ";" if header.count(";") >= header.count(",") else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    items = []
    for row in reader:
        r = {k.strip().upper(): (v or "").strip() for k, v in row.items() if k}
        lang = r.get("TP_LINGUA", "")
        items.append(
            Item(
                prova=r.get("CO_PROVA", ""),
                position=int(r["CO_POSICAO"]),
                area=r.get("SG_AREA", "").upper(),
                item_code=_int(r.get("CO_ITEM")),
                answer=(r.get("TX_GABARITO") or "").upper()[:1] or None,
                skill=_int(r.get("CO_HABILIDADE")),
                annulled=r.get("IN_ITEM_ABAN", "0") == "1",
                a=_num(r.get("NU_PARAM_A")),
                b=_num(r.get("NU_PARAM_B")),
                c=_num(r.get("NU_PARAM_C")),
                color=r.get("TX_COR", "").lower(),
                language={"0": ForeignLanguage.ingles, "1": ForeignLanguage.espanhol}.get(lang),
            )
        )
    return items


@dataclass
class Match:
    prova: str
    color: str
    rate: float
    items: dict[tuple[int, ForeignLanguage | None], Item] = field(default_factory=dict)


def match_booklets(
    year: int, questions: list[SourceQuestion], items: list[Item], min_rate: float = 0.8
) -> dict[str, Match]:
    """Por área, o caderno dos microdados com gabarito mais parecido com o do enem.dev."""
    by_prova: dict[str, dict[tuple[int, ForeignLanguage | None], Item]] = defaultdict(dict)
    for it in items:
        by_prova[it.prova][(it.position, it.language)] = it
    by_area: dict[str, list[SourceQuestion]] = defaultdict(list)
    for q in questions:
        by_area[area_for(year, q.index)[0]].append(q)

    result: dict[str, Match] = {}
    for area, qs in by_area.items():
        best: Match | None = None
        for prova, pos_items in by_prova.items():
            sample = next(iter(pos_items.values()))
            if sample.area != area:
                continue
            hits = total = 0
            for q in qs:
                it = pos_items.get((q.index, q.language)) or pos_items.get((q.index, None))
                if it is None or not q.correct or not it.answer:
                    continue
                total += 1
                hits += it.answer == q.correct
            rate = hits / total if total else 0.0
            if best is None or rate > best.rate:
                best = Match(prova, sample.color, rate, pos_items)
        if best and best.rate >= min_rate:
            result[area] = best
            logger.info(
                "área %s: caderno %s (%s), gabarito coincide em %.0f%%",
                area,
                best.prova,
                best.color,
                100 * best.rate,
            )
        else:
            logger.warning(
                "área %s: nenhum caderno dos microdados coincide (melhor: %s)",
                area,
                f"{best.rate:.0%}" if best else "nenhum",
            )
    return result


# ---- importação -----------------------------------------------------------------


@dataclass
class Stats:
    created: int = 0
    updated: int = 0
    with_inep: int = 0
    assets: int = 0
    warnings: list[str] = field(default_factory=list)


async def _upload_assets(q: SourceQuestion, year: int, stats: Stats) -> tuple[str, list[str], dict]:
    """Envia as imagens locais ao storage e troca as URLs por `asset:<chave>`."""
    storage = get_storage()
    keys: list[str] = []

    async def to_asset(url: str) -> str | None:
        m = IMAGE_URL_RE.match(url)
        if not m:
            return None
        local = q.folder.parent / m.group(2) / m.group(3)
        if not local.is_file():
            stats.warnings.append(f"{year}/{q.folder.name}: imagem ausente {url}")
            return None
        key = f"questions/{year}/{m.group(2)}/{m.group(3)}"
        ctype = mimetypes.guess_type(local.name)[0] or "application/octet-stream"
        await storage.put(key, local.read_bytes(), ctype)
        if key not in keys:
            keys.append(key)
        return f"asset:{key}"

    async def rewrite(md: str) -> str:
        out = md
        for url in {m.group(0) for m in IMAGE_URL_RE.finditer(md)}:
            asset = await to_asset(url)
            if asset:
                out = out.replace(url, asset)
        return out

    statement = await rewrite(q.context)
    for url in q.files:  # arquivos que não aparecem no texto entram no fim do enunciado
        asset = await to_asset(url)
        if asset and asset not in statement:
            statement += f"\n\n![]({asset})"
    if q.intro:
        statement = f"{statement}\n\n{q.intro}".strip()

    options: dict[str, str] = {}
    for alt in q.alternatives:
        text = (alt.get("text") or "").strip()
        if alt.get("file"):
            asset = await to_asset(alt["file"])
            if asset:
                text = f"![]({asset})" + (f"\n\n{text}" if text else "")
        options[alt["letter"]] = text or "(alternativa sem texto)"
    stats.assets += len(keys)
    return statement, keys, options


async def _exam(session, year: int, day: int, color: str, prova: str | None) -> Exam:
    exam = await session.scalar(
        select(Exam).where(
            Exam.year == year,
            Exam.application == ExamApplication.regular,
            Exam.day == day,
            Exam.booklet_color == color,
        )
    )
    if exam is None:
        exam = Exam(year=year, application=ExamApplication.regular, day=day, booklet_color=color)
        session.add(exam)
        await session.flush()
    if prova and prova.isdigit():
        exam.booklet_code = int(prova)
    return exam


async def import_year(root: Path, year: int, microdados: Path | None, dry_run: bool) -> Stats:
    stats = Stats()
    questions = load_enem_dev(root, year)
    matches = match_booklets(year, questions, load_microdados(microdados)) if microdados else {}

    async with SessionLocal() as session:
        areas = {a.code: a for a in await session.scalars(select(KnowledgeArea))}
        subjects = {s.slug: s for s in await session.scalars(select(Subject))}

        for q in questions:
            area_code, day = area_for(year, q.index)
            match = matches.get(area_code)
            item = None
            if match:
                item = match.items.get((q.index, q.language)) or match.items.get((q.index, None))

            color = REF_BOOKLET + (f"-{q.language.value}" if q.language else "")
            exam = await _exam(session, year, day, color, match.prova if match else None)

            question = None
            if item and item.item_code:
                question = await session.scalar(
                    select(Question).where(Question.inep_item_code == item.item_code)
                )
            if question is None:
                question = await session.scalar(
                    select(Question)
                    .join(ExamQuestion, ExamQuestion.question_id == Question.id)
                    .where(ExamQuestion.exam_id == exam.id, ExamQuestion.position == q.index)
                )
            statement, asset_keys, options = await _upload_assets(q, year, stats)

            annulled = (item.annulled if item else False) or not q.correct
            subject_slug = (
                "matematica" if area_code == "MT" else q.language.value if q.language else None
            )
            values = {
                "year": year,
                "area_id": areas[area_code].id,
                "foreign_language": q.language,
                "statement_md": statement or "(enunciado não disponível)",
                "correct_option": None if annulled else q.correct,
                "is_annulled": annulled,
                "source": SOURCE + ("+inep" if item else ""),
            }
            if item:
                values.update(
                    inep_item_code=item.item_code,
                    skill_code=item.skill if item.skill and 1 <= item.skill <= 30 else None,
                    irt_a=item.a,
                    irt_b=item.b,
                    irt_c=item.c,
                )
                stats.with_inep += 1

            if question is None:
                question = Question(**values, reviewed=False)
                if subject_slug in subjects:
                    question.subject_id = subjects[subject_slug].id
                session.add(question)
                await session.flush()
                session.add(
                    ExamQuestion(exam_id=exam.id, question_id=question.id, position=q.index)
                )
                stats.created += 1
            else:
                if question.reviewed:
                    # não sobrescreve texto revisado por humano; só completa dados do INEP
                    for key in ("inep_item_code", "skill_code", "irt_a", "irt_b", "irt_c"):
                        if key in values:
                            setattr(question, key, values[key])
                else:
                    for key, value in values.items():
                        setattr(question, key, value)
                    if question.subject_id is None and subject_slug in subjects:
                        question.subject_id = subjects[subject_slug].id
                stats.updated += 1
            if not question.reviewed:
                await session.execute(
                    delete(QuestionOption).where(QuestionOption.question_id == question.id)
                )
                for letter, text in sorted(options.items()):
                    session.add(
                        QuestionOption(question_id=question.id, letter=letter, text_md=text)
                    )
                await session.execute(
                    delete(QuestionAsset).where(QuestionAsset.question_id == question.id)
                )
                for pos, key in enumerate(asset_keys, start=1):
                    session.add(
                        QuestionAsset(question_id=question.id, storage_key=key, position=pos)
                    )

        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    return stats


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--year", type=int, action="append", required=True)
    parser.add_argument(
        "--source", default="data/enem-api/public", help="pasta public/ do enem-api"
    )
    parser.add_argument("--microdados", type=Path, help="ITENS_PROVA_<ano>.csv (um ano por vez)")
    parser.add_argument("--dry-run", action="store_true", help="processa sem gravar no banco")
    args = parser.parse_args()
    if args.microdados and len(args.year) > 1:
        raise SystemExit("--microdados vale para um ano por vez.")

    for year in args.year:
        stats = await import_year(Path(args.source), year, args.microdados, args.dry_run)
        print(
            f"{year}: {stats.created} criadas, {stats.updated} atualizadas, "
            f"{stats.with_inep} com dados do INEP, {stats.assets} imagens"
            + (" (dry-run, nada gravado)" if args.dry_run else "")
        )
        for w in stats.warnings[:20]:
            print(f"  aviso: {w}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
