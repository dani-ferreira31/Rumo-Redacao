from app.ai.schemas import (
    AvaliacaoCompetencia,
    DesvioC1,
    ElementoC5,
    ElementosC5,
    GradingOutput,
    Trecho,
)


def grading(
    scores=(160, 160, 160, 160, 160),
    *,
    anulada=False,
    motivo=None,
    tangenciamento=False,
    elementos=4,
    dh=False,
    desvios=(),
    comentario="Comentário geral.",
):
    keys = ["agente", "acao", "meio", "finalidade", "detalhamento"]
    return GradingOutput(
        anulada=anulada,
        motivo_anulacao=motivo,
        tangenciamento=tangenciamento,
        competencias=[
            AvaliacaoCompetencia(
                numero=n,
                nota=s,
                resumo_nivel=f"Nível C{n}",
                justificativa="Justificativa.",
                pontos_fortes=["forte"],
                pontos_melhoria=["melhorar"],
                trechos=[Trecho(linha=1, trecho="trecho", comentario="comentário")],
            )
            for n, s in enumerate(scores, start=1)
        ],
        desvios_c1=[
            DesvioC1(linha=line, trecho=t, tipo="ortografia", sugestao="corrigir")
            for line, t in desvios
        ],
        elementos_c5=ElementosC5(
            **{
                k: ElementoC5(presente=i < elementos, trecho="t" if i < elementos else None)
                for i, k in enumerate(keys)
            }
        ),
        desrespeito_direitos_humanos=dh,
        comentario_geral=comentario,
        proximos_passos=["passo 1", "passo 2"],
    )
