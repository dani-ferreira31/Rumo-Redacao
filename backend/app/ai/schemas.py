"""Formatos de saída estruturada pedidos à IA (validados pelo SDK com Pydantic).

Os nomes dos campos ficam em português porque fazem parte do prompt: a IA lê o
schema. Os textos dos campos são o que o aluno vai ver.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Score = Literal[0, 40, 80, 120, 160, 200]

ZeroReasonAI = Literal[
    "fuga_total_ao_tema",
    "nao_dissertativo_argumentativo",
    "parte_desconectada",
    "copia_textos_motivadores",
    "lingua_estrangeira",
    "identificacao",
    "improperios_ou_anulacao",
    "ilegivel",
]

DeviationType = Literal[
    "ortografia",
    "acentuacao",
    "pontuacao",
    "concordancia",
    "regencia",
    "crase",
    "sintaxe",
    "vocabulario",
    "registro",
    "outro",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- ETAPA 1: transcrição ---------------------------------------------------


class LinhaTranscrita(_Strict):
    texto: str = Field(description="Conteúdo literal da linha física, com os erros do aluno.")
    inicia_paragrafo: bool = Field(
        description="true se esta linha começa um parágrafo (recuo ou quebra visível)."
    )


class TranscriptionOutput(_Strict):
    titulo: str | None = Field(description="Título, se houver (não conta como linha de texto).")
    linhas: list[LinhaTranscrita] = Field(
        description="Uma entrada por linha física escrita, na ordem da folha."
    )
    qtd_ilegiveis: int = Field(description="Quantidade de marcadores [ilegível] usados.")
    confianca: Literal["alta", "media", "baixa"]
    possivel_identificacao: bool = Field(
        description="true se houver nome, assinatura ou outro sinal que identifique o aluno."
    )
    folha_em_branco: bool
    observacoes: str = Field(description="Observações sobre a imagem ou a leitura, em português.")


# ---- ETAPA 3: correção ------------------------------------------------------


class Trecho(_Strict):
    linha: int = Field(description="Número da linha, como em [L07].")
    trecho: str = Field(description="Cópia exata do trecho comentado.")
    comentario: str


class AvaliacaoCompetencia(_Strict):
    numero: Literal[1, 2, 3, 4, 5]
    nota: Score
    resumo_nivel: str = Field(description="Descritor do nível atingido, em uma frase.")
    justificativa: str = Field(
        description="Por que o texto está neste nível e não no nível acima, citando linhas."
    )
    pontos_fortes: list[str]
    pontos_melhoria: list[str]
    trechos: list[Trecho]


class DesvioC1(_Strict):
    linha: int
    trecho: str
    tipo: DeviationType
    sugestao: str


class ElementoC5(_Strict):
    presente: bool
    trecho: str | None


class ElementosC5(_Strict):
    agente: ElementoC5
    acao: ElementoC5
    meio: ElementoC5
    finalidade: ElementoC5
    detalhamento: ElementoC5


class GradingOutput(_Strict):
    anulada: bool
    motivo_anulacao: ZeroReasonAI | None
    tangenciamento: bool
    competencias: list[AvaliacaoCompetencia] = Field(
        description="Exatamente 5 itens, um por competência, na ordem 1 a 5."
    )
    desvios_c1: list[DesvioC1]
    elementos_c5: ElementosC5
    desrespeito_direitos_humanos: bool
    comentario_geral: str
    proximos_passos: list[str] = Field(
        description="De 2 a 4 ações concretas para a próxima redação."
    )
