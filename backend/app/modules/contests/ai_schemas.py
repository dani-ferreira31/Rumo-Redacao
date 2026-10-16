"""Saídas estruturadas da importação de provas (lidas pela IA; nomes em português)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AlternativaExtraida(_Strict):
    letra: Literal["A", "B", "C", "D", "E"]
    texto: str = Field(description="Texto da alternativa, sem a letra.")


class QuestaoExtraida(_Strict):
    numero: int = Field(description="Número da questão/item como impresso na prova.")
    formato: Literal["multiple_choice", "true_false"]
    enunciado: str = Field(description="Enunciado completo em markdown, com o texto-base.")
    alternativas: list[AlternativaExtraida] = Field(
        description="Alternativas (vazio nos itens Certo/Errado)."
    )
    disciplina_sugerida: str | None
    tem_figura: bool
    pagina: int = Field(description="Página do PDF (deste trecho) em que a questão começa.")


class ExtracaoProva(_Strict):
    questoes: list[QuestaoExtraida]
    observacoes: str


class RespostaGabarito(_Strict):
    numero: int
    resposta: Literal["A", "B", "C", "D", "E", "X"] = Field(description="X = anulada.")


class Gabarito(_Strict):
    respostas: list[RespostaGabarito]
    observacoes: str


def validate_extraction(out: ExtracaoProva) -> list[str]:
    problems = []
    seen: set[int] = set()
    for q in out.questoes:
        if q.numero in seen:
            problems.append(f"questão {q.numero} repetida")
        seen.add(q.numero)
        letters = [a.letra for a in q.alternativas]
        if q.formato == "multiple_choice" and len(letters) < 2:
            problems.append(f"questão {q.numero}: múltipla escolha sem alternativas")
        if q.formato == "true_false" and letters:
            problems.append(f"questão {q.numero}: item Certo/Errado não tem alternativas")
        if len(set(letters)) != len(letters):
            problems.append(f"questão {q.numero}: letras de alternativa repetidas")
        if not q.enunciado.strip():
            problems.append(f"questão {q.numero}: enunciado vazio")
    return problems
