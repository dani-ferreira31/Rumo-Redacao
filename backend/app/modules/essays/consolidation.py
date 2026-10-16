"""ETAPAS 3 a 5: validação de cada correção e consolidação das notas (sem IO).

Regras (docs/05 e Cartilha do INEP):
- discrepância: total difere em mais de 100 ou alguma competência em mais de 80,
  ou só uma das correções anula (ou anulam por motivos diferentes);
- com 3 correções, usa as duas de total mais próximo;
- anulação só se a maioria anular pelo mesmo motivo;
- o feedback textual vem de uma só correção (a de total mais próximo da nota final).
"""

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from app.ai.schemas import GradingOutput

C5_BY_ELEMENTS = {5: 200, 4: 160, 3: 120, 2: 80, 1: 40, 0: 0}
ELEMENT_KEYS = ("agente", "acao", "meio", "finalidade", "detalhamento")


@dataclass
class Run:
    number: int
    scores: list[int]  # c1..c5
    annulled: bool
    zero_reason: str | None
    output: GradingOutput
    warnings: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(self.scores)


@dataclass
class Consolidated:
    scores: list[int]
    annulled: bool
    zero_reason: str | None
    runs_used: list[int]
    voice: Run | None
    deviations: list[dict[str, Any]]

    @property
    def total(self) -> int:
        return sum(self.scores)


def validate_grading(output: GradingOutput) -> list[str]:
    """Problemas que exigem pedir de novo à IA (o schema não consegue expressar)."""
    problems = []
    numbers = [c.numero for c in output.competencias]
    if sorted(numbers) != [1, 2, 3, 4, 5]:
        problems.append(
            "`competencias` deve ter exatamente as competências 1 a 5, uma vez cada "
            f"(veio {numbers})"
        )
    if output.anulada and output.motivo_anulacao is None:
        problems.append("`anulada` é true mas `motivo_anulacao` está vazio")
    if not output.anulada and output.motivo_anulacao is not None:
        problems.append("`motivo_anulacao` preenchido mas `anulada` é false")
    return problems


def elements_present(output: GradingOutput) -> int:
    return sum(getattr(output.elementos_c5, k).presente for k in ELEMENT_KEYS)


def normalize_run(number: int, output: GradingOutput) -> Run:
    """Aplica as regras cruzadas da grade à saída da IA."""
    by_number = {c.numero: c.nota for c in output.competencias}
    scores = [int(by_number[n]) for n in range(1, 6)]
    warnings: list[str] = []

    if output.anulada:
        return Run(number, [0] * 5, True, output.motivo_anulacao, output, warnings)

    if output.tangenciamento:
        if scores[1] != 40:
            warnings.append(f"tangenciamento: C2 ajustada de {scores[1]} para 40")
        scores[1] = 40
        for idx in (2, 4):
            if scores[idx] > 40:
                warnings.append(f"tangenciamento: C{idx + 1} limitada a 40 (era {scores[idx]})")
                scores[idx] = 40

    if output.desrespeito_direitos_humanos and scores[4] != 0:
        warnings.append(f"desrespeito aos direitos humanos: C5 ajustada de {scores[4]} para 0")
        scores[4] = 0
    elif not output.desrespeito_direitos_humanos and not output.tangenciamento:
        expected = C5_BY_ELEMENTS[elements_present(output)]
        if expected != scores[4]:
            warnings.append(
                f"C5: nota {scores[4]} diverge da contagem de elementos "
                f"({elements_present(output)} "
                f"→ {expected})"
            )
    return Run(number, scores, False, None, output, warnings)


def is_discrepant(a: Run, b: Run) -> bool:
    if a.annulled != b.annulled:
        return True
    if a.annulled and b.annulled:
        return a.zero_reason != b.zero_reason
    if abs(a.total - b.total) > 100:
        return True
    return any(abs(x - y) > 80 for x, y in zip(a.scores, b.scores, strict=True))


def _merge_deviations(runs: list[Run]) -> list[dict[str, Any]]:
    seen: set[tuple[int, str]] = set()
    merged = []
    for run in runs:
        for d in run.output.desvios_c1:
            key = (d.linha, " ".join(d.trecho.lower().split()))
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                {"line": d.linha, "text": d.trecho, "type": d.tipo, "suggestion": d.sugestao}
            )
    return sorted(merged, key=lambda d: d["line"])


def consolidate(runs: list[Run]) -> Consolidated:
    """Consolida 2 ou 3 correções numa nota final."""
    if len(runs) < 2:
        raise ValueError("São necessárias ao menos 2 correções")

    # Anulação por maioria com o mesmo motivo
    reasons = [r.zero_reason for r in runs if r.annulled]
    for reason in set(reasons):
        if reasons.count(reason) * 2 > len(runs):
            voters = [r for r in runs if r.annulled and r.zero_reason == reason]
            return Consolidated([0] * 5, True, reason, [r.number for r in voters], voters[0], [])
    if len(reasons) == len(runs):
        # todas anularam, mas por motivos diferentes: anula pelo motivo da 1ª correção
        return Consolidated([0] * 5, True, runs[0].zero_reason, [runs[0].number], runs[0], [])

    candidates = [r for r in runs if not r.annulled] if len(runs) > 2 else runs
    if len(candidates) < 2:
        candidates = runs
    pair = min(
        combinations(candidates, 2),
        key=lambda p: (abs(p[0].total - p[1].total), p[0].number + p[1].number),
    )
    scores = [round((x + y) / 2) for x, y in zip(pair[0].scores, pair[1].scores, strict=True)]
    final_total = sum(scores)
    voice = min(pair, key=lambda r: (abs(r.total - final_total), r.number))
    return Consolidated(
        scores=scores,
        annulled=False,
        zero_reason=None,
        runs_used=sorted(r.number for r in pair),
        voice=voice,
        deviations=_merge_deviations(list(pair)),
    )


def feedback_from(consolidated: Consolidated) -> dict[str, Any]:
    """Feedback consolidado no formato da API (docs/04-api.md)."""
    voice = consolidated.voice
    if voice is None:
        return {}
    out = voice.output
    by_number = {c.numero: c for c in out.competencias}
    competencies = []
    for n in range(1, 6):
        c = by_number[n]
        competencies.append(
            {
                "number": n,
                "score": consolidated.scores[n - 1],
                "level_summary": c.resumo_nivel,
                "justification": c.justificativa,
                "strengths": c.pontos_fortes,
                "improvements": c.pontos_melhoria,
                "excerpts": [
                    {"line": t.linha, "text": t.trecho, "comment": t.comentario} for t in c.trechos
                ],
            }
        )
    return {
        "competencies": competencies,
        "c1_deviations": consolidated.deviations,
        "c5_elements": {
            k: {
                "present": getattr(out.elementos_c5, k).presente,
                "excerpt": getattr(out.elementos_c5, k).trecho,
            }
            for k in ELEMENT_KEYS
        },
        "tangent": out.tangenciamento,
        "human_rights_violation": out.desrespeito_direitos_humanos,
        "general_comment": out.comentario_geral,
        "next_steps": out.proximos_passos,
    }
