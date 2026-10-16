"""Saídas simuladas da importação de provas de concurso (provedor "fake").

Gera 2 questões por página principal do trecho: a cada 3, um item Certo/Errado;
a questão 5 tem figura. O gabarito simulado anula a questão 4.
"""

import re
from typing import Any

from app.ai.types import AIRequest, TextPart


def _text(request: AIRequest[Any]) -> str:
    return "\n".join(p.text for p in request.content if isinstance(p, TextPart))


def _answer(n: int) -> str:
    if n == 4:
        return "X"
    if n % 3 == 0:
        return "C" if n % 2 else "E"
    return "ABCDE"[n % 5]


def generate(request: AIRequest[Any]) -> Any:
    from app.modules.contests.ai_schemas import (
        AlternativaExtraida,
        ExtracaoProva,
        Gabarito,
        QuestaoExtraida,
        RespostaGabarito,
    )

    text = _text(request)
    if request.output_type is ExtracaoProva:
        first = int(re.search(r"páginas (\d+) a \d+ da prova", text).group(1))
        primary = int(re.search(r"Páginas principais: 1 a (\d+)", text).group(1))
        subjects = re.search(r"Disciplinas disponíveis: (.*)\.", text).group(1).split(", ")
        questions = []
        for page in range(1, primary + 1):
            for k in (1, 2):
                n = (first + page - 2) * 2 + k
                tf = n % 3 == 0
                questions.append(
                    QuestaoExtraida(
                        numero=n,
                        formato="true_false" if tf else "multiple_choice",
                        enunciado=(
                            f"Questão simulada {n} (importação de teste, sem IA real)."
                            + (" [Figura: gráfico de exemplo]" if n == 5 else "")
                            + ("\n\nJulgue o item a seguir." if tf else "\n\nAssinale a correta.")
                        ),
                        alternativas=[]
                        if tf
                        else [
                            AlternativaExtraida(letra=letter, texto=f"Alternativa {letter} da {n}")
                            for letter in "ABCDE"
                        ],
                        disciplina_sugerida=subjects[n % len(subjects)],
                        tem_figura=n == 5,
                        pagina=page,
                    )
                )
        return ExtracaoProva(questoes=questions, observacoes="")
    if request.output_type is Gabarito:
        match = re.search(r"Questões esperadas: (\d+) a (\d+)", text)
        lo, hi = (int(match.group(1)), int(match.group(2))) if match else (1, 0)
        return Gabarito(
            respostas=[RespostaGabarito(numero=n, resposta=_answer(n)) for n in range(lo, hi + 1)],
            observacoes="Gabarito simulado.",
        )
    return None
