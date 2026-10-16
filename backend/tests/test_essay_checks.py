from app.core.enums import EssayInputType, EssayZeroReason
from app.modules.essays.checks import copied_line_numbers, find_markers, run_checks

PHOTO = EssayInputType.photo
TEXT = EssayInputType.text


def _lines(n: int) -> str:
    return "\n".join(f"Linha {i} da redação com algumas palavras de conteúdo." for i in range(n))


def test_texto_em_branco_e_anulado():
    r = run_checks("   \n  ", PHOTO)
    assert r.zero_reason == EssayZeroReason.folha_em_branco


def test_sete_linhas_anula_oito_nao():
    assert run_checks(_lines(7), PHOTO).zero_reason == EssayZeroReason.texto_insuficiente
    r = run_checks(_lines(8), PHOTO)
    assert r.zero_reason is None
    assert r.line_count == 8


def test_linhas_em_branco_entre_paragrafos_nao_contam():
    text = _lines(4) + "\n\n" + _lines(4)
    r = run_checks(text, PHOTO)
    assert r.line_count == 8
    assert r.paragraph_count == 2


def test_aviso_acima_de_30_linhas():
    r = run_checks(_lines(31), PHOTO)
    assert r.zero_reason is None
    assert any("linha 30" in w for w in r.warnings)


def test_redacao_digitada_estima_linhas():
    paragraph = " ".join(["palavra"] * 45)  # 45 palavras -> 5 linhas
    r = run_checks(paragraph, TEXT)
    assert r.estimated_lines
    assert r.line_count == 5
    assert r.zero_reason == EssayZeroReason.texto_insuficiente
    r = run_checks(paragraph + "\n\n" + paragraph, TEXT)
    assert r.line_count == 10 and r.zero_reason is None


MOTIVADOR = (
    "As culturas africanas e afro-brasileiras foram relegadas ao campo do folclore com o "
    "propósito de confiná-las ao gueto fossilizado da memória."
)


def test_detecta_copia_que_atravessa_linhas():
    lines = [
        "Segundo o texto, as culturas africanas e afro-brasileiras foram",
        "relegadas ao campo do folclore com o propósito de confinar tudo.",
        "Isso é um problema próprio do aluno sem relação com o motivador.",
    ]
    assert copied_line_numbers(lines, MOTIVADOR) == [1, 2]
    assert copied_line_numbers(lines, None) == []


def test_copia_que_deixa_ate_7_linhas_proprias_anula():
    copied = [
        "As culturas africanas e afro-brasileiras foram relegadas ao campo",
        "do folclore com o propósito de confiná-las ao gueto fossilizado da memória.",
    ]
    text = "\n".join(copied + _lines(6).splitlines())
    r = run_checks(text, PHOTO, MOTIVADOR)
    assert r.line_count == 8
    assert r.own_line_count == 6
    assert r.zero_reason == EssayZeroReason.copia_textos_motivadores

    text = "\n".join(copied + _lines(9).splitlines())
    r = run_checks(text, PHOTO, MOTIVADOR)
    assert r.zero_reason is None
    assert r.copied_lines == [1, 2]
    assert any("copiados" in w for w in r.warnings)


def test_marcadores():
    text = "linha um [ilegível] ok\nlinha [?sociedade] dois\nlinha três"
    assert find_markers(text) == [(1, "[ilegível]"), (2, "[?sociedade]")]
