"""IA falsa para desenvolvimento sem chave (provedor "fake", AI_DRIVER=fake).

Devolve respostas de exemplo com o mesmo formato da IA real, para que todo o
fluxo (upload, revisão, correção, resultado, e-mail) funcione localmente sem
custo. As notas são determinísticas a partir do texto: a mesma redação recebe
sempre as mesmas notas.
"""

import hashlib
import json
from typing import Any

from app.ai.schemas import (
    AvaliacaoCompetencia,
    DesvioC1,
    ElementoC5,
    ElementosC5,
    GradingOutput,
    LinhaTranscrita,
    TranscriptionOutput,
    Trecho,
)
from app.ai.types import AIRequest, ModelInfo, ProviderReply, TextPart, Turn

FAKE_MODEL = "fake"

SAMPLE_LINES = [
    (True, "No Brasil, a valorização da educação ainda enfrenta desafios"),
    (False, "estruturais que impedem o pleno desenvolvimento dos jovens. Nesse"),
    (False, "contexto, é fundamental discutir as causas desse problema, como a"),
    (False, "falta de investimentos e a desigualdade social que concerteza"),
    (False, "afeta milhões de estudantes em todo o país."),
    (True, "Em primeiro lugar, cabe destacar que a ausência de recursos nas"),
    (False, "escolas públicas compromete a qualidade do ensino. Segundo dados"),
    (False, "do [?IBGE], grande parte das escolas não possui bibliotecas ou"),
    (False, "laboratórios, o que limita o aprendizado dos alunos e reforça a"),
    (False, "exclusão dos mais pobres."),
    (True, "Além disso, a desigualdade social faz com que muitos jovens precisem"),
    (False, "trabalhar cedo, abandonando os estudos. Dessa forma, o ciclo de"),
    (False, "pobreza se perpetua, pois sem formação esses jovens tem menos"),
    (False, "oportunidades no mercado de trabalho [ilegível] futuro."),
    (True, "Portanto, é necessário que o Ministério da Educação, em parceria"),
    (False, "com as secretarias estaduais, amplie os investimentos nas escolas"),
    (False, "públicas, por meio de verbas destinadas à infraestrutura, a fim de"),
    (False, "garantir um ensino de qualidade para todos os estudantes brasileiros."),
]

LEVELS = [0, 40, 80, 120, 160, 200]
NAMES = {
    1: "domínio da escrita formal",
    2: "compreensão da proposta e repertório",
    3: "organização dos argumentos",
    4: "coesão",
    5: "proposta de intervenção",
}


def _seed(request: AIRequest[Any]) -> int:
    payload = json.dumps([repr(p) for p in request.content])
    return int(hashlib.sha256(payload.encode()).hexdigest(), 16)


def _first_line(request: AIRequest[Any]) -> tuple[int, str]:
    for part in request.content:
        if isinstance(part, TextPart):
            for raw in part.text.splitlines():
                if raw.startswith("[L"):
                    number, _, text = raw.partition("]")
                    return int(number[2:]), text.strip()
    return 1, "texto"


def fake_transcription() -> TranscriptionOutput:
    return TranscriptionOutput(
        titulo=None,
        linhas=[LinhaTranscrita(texto=t, inicia_paragrafo=p) for p, t in SAMPLE_LINES],
        qtd_ilegiveis=1,
        confianca="media",
        possivel_identificacao=False,
        folha_em_branco=False,
        observacoes="Transcrição simulada (modo de desenvolvimento, sem IA real).",
    )


def fake_grading(request: AIRequest[Any]) -> GradingOutput:
    seed = _seed(request)
    line_no, line_text = _first_line(request)
    excerpt = line_text[:60]
    scores = []
    for i in range(5):
        # níveis entre 80 e 200, variando por competência
        scores.append(LEVELS[2 + (seed >> (i * 3)) % 4])
    present = {
        "agente": True,
        "acao": True,
        "meio": True,
        "finalidade": True,
        "detalhamento": scores[4] == 200,
    }
    count = sum(present.values())
    scores[4] = LEVELS[count]
    competencias = [
        AvaliacaoCompetencia(
            numero=n,
            nota=scores[n - 1],
            resumo_nivel=f"Nível {scores[n - 1]} em {NAMES[n]} (simulado).",
            justificativa=(
                "Esta é uma correção simulada, gerada sem IA real, só para testar o fluxo. "
                f"Na correção real, aqui aparece por que o texto ficou com {scores[n - 1]} "
                "pontos e o que faltou para o nível seguinte."
            ),
            pontos_fortes=[f"Ponto forte de exemplo em {NAMES[n]}."],
            pontos_melhoria=[f"Sugestão de melhoria de exemplo em {NAMES[n]}."],
            trechos=[Trecho(linha=line_no, trecho=excerpt, comentario="Comentário de exemplo.")],
        )
        for n in range(1, 6)
    ]
    return GradingOutput(
        anulada=False,
        motivo_anulacao=None,
        tangenciamento=False,
        competencias=competencias,
        desvios_c1=[
            DesvioC1(
                linha=line_no,
                trecho=excerpt,
                tipo="outro",
                sugestao="Desvio de exemplo (correção simulada).",
            )
        ],
        elementos_c5=ElementosC5(
            **{k: ElementoC5(presente=v, trecho=excerpt if v else None) for k, v in present.items()}
        ),
        desrespeito_direitos_humanos=False,
        comentario_geral=(
            "Correção simulada: o sistema está em modo de desenvolvimento (AI_DRIVER=fake). "
            "As notas e comentários são apenas exemplos."
        ),
        proximos_passos=[
            "Configure a chave da Anthropic para receber uma correção real.",
            "Revise a proposta de intervenção com os cinco elementos.",
        ],
    )


class FakeProvider:
    name = "fake"

    async def send(self, request: AIRequest[Any], history: list[Turn]) -> ProviderReply:
        output = fake_output(request)
        return ProviderReply(output=output, stop="ok", model=FAKE_MODEL, native=output)

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(FAKE_MODEL, "Simulado (sem custo)")]


def fake_output(request: AIRequest[Any]) -> Any:
    if request.output_type is TranscriptionOutput:
        return fake_transcription()
    if request.output_type is GradingOutput:
        return fake_grading(request)
    from app.ai import fake_contest  # importação tardia: só usada na importação de provas

    output = fake_contest.generate(request)
    if output is None:
        raise NotImplementedError(f"FakeProvider não sabe gerar {request.output_type}")
    return output
