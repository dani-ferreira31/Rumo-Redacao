import json
from decimal import Decimal

from scripts.import_questions import (
    SourceQuestion,
    area_for,
    load_microdados,
    match_booklets,
)


def test_area_pela_posicao():
    assert area_for(2023, 1) == ("LC", 1)
    assert area_for(2023, 46) == ("CH", 1)
    assert area_for(2023, 91) == ("CN", 2)
    assert area_for(2023, 180) == ("MT", 2)
    assert area_for(2015, 1) == ("CH", 1)
    assert area_for(2015, 91) == ("LC", 2)


def _q(index, correct, lang=None):
    return SourceQuestion(
        folder=None,
        index=index,
        language=lang,
        context="",
        intro=None,
        files=[],
        correct=correct,
        alternatives=[],
    )


def test_cruza_com_o_caderno_cujo_gabarito_coincide(tmp_path):
    header = (
        "CO_POSICAO;SG_AREA;CO_ITEM;TX_GABARITO;CO_HABILIDADE;IN_ITEM_ABAN;"
        "TX_MOTIVO_ABAN;NU_PARAM_A;NU_PARAM_B;NU_PARAM_C;TX_COR;CO_PROVA;TP_LINGUA;"
        "IN_ITEM_ADAPTADO"
    )
    rows = [header]
    keys = "ABCDE" * 9
    # caderno 1111 (azul): mesma numeração do enem.dev
    for pos in range(136, 181):
        rows.append(
            f"{pos};MT;{90000 + pos};{keys[pos - 136]};{pos % 30 + 1};0;;2,1;1,25;0,2;AZUL;1111;;0"
        )
    # caderno 2222 (amarelo): mesmas questões em outra ordem
    for pos in range(136, 181):
        rows.append(f"{pos};MT;{80000 + pos};{keys[(pos - 130) % 45]};1;0;;1;1;0,1;AMARELO;2222;;0")
    path = tmp_path / "ITENS_PROVA_2023.csv"
    path.write_bytes("\n".join(rows).encode("latin-1"))

    items = load_microdados(path)
    assert len(items) == 90
    assert items[0].b == Decimal("1.25")

    questions = [_q(pos, keys[pos - 136]) for pos in range(136, 181)]
    matches = match_booklets(2023, questions, items)
    assert matches["MT"].prova == "1111" and matches["MT"].rate == 1.0
    item = matches["MT"].items[(140, None)]
    assert item.item_code == 90140 and item.skill == 140 % 30 + 1


def test_nao_cruza_quando_nenhum_caderno_coincide(tmp_path):
    path = tmp_path / "itens.csv"
    path.write_text(
        "CO_POSICAO;SG_AREA;CO_ITEM;TX_GABARITO;TX_COR;CO_PROVA\n"
        + "\n".join(f"{p};MT;{p};A;AZUL;1" for p in range(136, 181))
    )
    questions = [_q(p, "B") for p in range(136, 181)]
    assert match_booklets(2023, questions, load_microdados(path)) == {}


def test_formato_enem_dev(tmp_path):
    from scripts.import_questions import load_enem_dev

    folder = tmp_path / "2023" / "questions" / "1-ingles"
    folder.mkdir(parents=True)
    (folder / "details.json").write_text(
        json.dumps(
            {
                "index": 1,
                "language": "ingles",
                "context": "Texto",
                "files": [],
                "correctAlternative": "B",
                "alternativesIntroduction": "Pergunta",
                "alternatives": [{"letter": "A", "text": "x", "file": None}],
            }
        )
    )
    [q] = load_enem_dev(tmp_path, 2023)
    assert q.index == 1 and q.language.value == "ingles" and q.correct == "B"
