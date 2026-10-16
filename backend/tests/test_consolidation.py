import pytest

from app.modules.essays.consolidation import (
    consolidate,
    feedback_from,
    is_discrepant,
    normalize_run,
    validate_grading,
)
from tests.grading_factory import grading


def run(n, *args, **kwargs):
    return normalize_run(n, grading(*args, **kwargs))


def test_sem_discrepancia_faz_media():
    a = run(1, (160, 120, 160, 160, 160))
    b = run(2, (200, 160, 120, 160, 160))
    assert not is_discrepant(a, b)
    final = consolidate([a, b])
    assert final.scores == [180, 140, 140, 160, 160]
    assert final.total == 780
    assert not final.annulled


def test_discrepancia_por_total_e_por_competencia():
    a = run(1, (200, 200, 200, 200, 200))
    assert is_discrepant(a, run(2, (160, 160, 160, 160, 120)))  # total 200 de diferença
    assert not is_discrepant(a, run(2, (160, 160, 200, 200, 200)))  # 40 em duas, total 80
    assert is_discrepant(a, run(2, (80, 200, 200, 200, 200)))  # 120 numa competência


def test_tres_correcoes_usa_as_duas_mais_proximas():
    a = run(1, (200, 200, 200, 200, 200), elementos=5)  # 1000
    b = run(2, (120, 120, 120, 120, 120), elementos=3)  # 600
    c = run(3, (120, 160, 120, 120, 120), elementos=3)  # 640
    final = consolidate([a, b, c])
    assert final.runs_used == [2, 3]
    assert final.scores == [120, 140, 120, 120, 120]
    assert final.voice.number in (2, 3)


def test_anulacao_de_uma_so_correcao_e_discrepancia():
    a = run(1, (0, 0, 0, 0, 0), anulada=True, motivo="fuga_total_ao_tema")
    b = run(2, (120, 120, 120, 120, 120), elementos=3)
    assert is_discrepant(a, b)
    # 3ª não anula: vale a média das duas que não anularam
    c = run(3, (160, 120, 120, 120, 120), elementos=3)
    final = consolidate([a, b, c])
    assert not final.annulled
    assert final.runs_used == [2, 3]


def test_anulacao_por_maioria_com_mesmo_motivo():
    a = run(1, (0,) * 5, anulada=True, motivo="fuga_total_ao_tema")
    b = run(2, (120,) * 5, elementos=3)
    c = run(3, (0,) * 5, anulada=True, motivo="fuga_total_ao_tema")
    final = consolidate([a, b, c])
    assert final.annulled
    assert final.zero_reason == "fuga_total_ao_tema"
    assert final.scores == [0] * 5


def test_motivos_de_anulacao_diferentes_sao_discrepantes():
    a = run(1, (0,) * 5, anulada=True, motivo="fuga_total_ao_tema")
    b = run(2, (0,) * 5, anulada=True, motivo="identificacao")
    assert is_discrepant(a, b)


def test_anulada_zera_todas_as_notas():
    r = run(1, (160, 160, 160, 160, 160), anulada=True, motivo="parte_desconectada")
    assert r.scores == [0] * 5 and r.annulled


def test_tangenciamento_limita_c2_c3_c5():
    r = run(1, (160, 120, 160, 160, 160), tangenciamento=True)
    assert r.scores == [160, 40, 40, 160, 40]
    assert r.warnings


def test_direitos_humanos_zera_c5():
    r = run(1, (160, 160, 160, 160, 160), dh=True, elementos=5)
    assert r.scores[4] == 0


def test_c5_incoerente_com_elementos_gera_aviso():
    r = run(1, (160, 160, 160, 160, 200), elementos=3)
    assert any("C5" in w for w in r.warnings)
    assert r.scores[4] == 200  # só avisa, não muda


def test_feedback_usa_uma_voz_e_une_desvios():
    a = run(1, (160,) * 5, desvios=[(3, "concerteza"), (5, "agente")], comentario="voz A")
    b = run(
        2, (120, 160, 160, 160, 160), desvios=[(3, "Concerteza "), (7, "mais")], comentario="voz B"
    )
    final = consolidate([a, b])
    fb = feedback_from(final)
    assert fb["general_comment"] in ("voz A", "voz B")
    assert [d["line"] for d in fb["c1_deviations"]] == [3, 5, 7]
    assert [c["score"] for c in fb["competencies"]] == final.scores


def test_validacao_exige_cinco_competencias_unicas():
    g = grading()
    g.competencias[4].numero = 1
    assert validate_grading(g)
    assert validate_grading(grading(anulada=True, motivo=None))
    assert validate_grading(grading()) == []


def test_consolidar_exige_duas_correcoes():
    with pytest.raises(ValueError):
        consolidate([run(1)])
