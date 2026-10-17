"""Calibração da correção: compara as notas da IA com notas humanas (Essay-BR).

Roda as ETAPAS 2 a 5 (checagens, 2 ou 3 correções, consolidação) em N redações
sorteadas e gera um relatório com QWK, % de acerto exato, % dentro de ±40, MAE,
viés e matriz de confusão por competência.

Uso:
    python -m scripts.eval_grading --dataset data/essay-br --n 200
    python -m scripts.eval_grading --dataset data/essay-br --n 5 --yes
    python -m scripts.eval_grading --n 5 --yes --provider openai --model <id-do-modelo>

Sem --provider, usa o provedor e o modelo de correção configurados no painel
(Admin → IA) ou, se não houver, os do .env. Com um provedor real cada redação
custa de 2 a 3 chamadas de correção, por isso o script pede `--yes` para
confirmar o gasto. O uso fica em `ai_usage`, e um resumo `.json` acompanha o
relatório (o painel mostra a última calibração de cada modelo).
"""

import argparse
import ast
import asyncio
import csv
import json
import random
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import app.models  # noqa: F401  (registra todas as tabelas no SQLAlchemy)
from app.ai.client import TaskConfig, save_usage
from app.ai.config import resolve_task
from app.ai.grading import GradingInput, grade_once, prompt_version
from app.core.db import SessionLocal, engine
from app.core.enums import EssayInputType
from app.modules.essays.checks import run_checks
from app.modules.essays.consolidation import (
    consolidate,
    is_discrepant,
    normalize_run,
)

LEVELS = [0, 40, 80, 120, 160, 200]
PRED_GRID = list(range(0, 201, 20))  # médias de duas correções caem em múltiplos de 20


@dataclass
class Sample:
    idx: int
    prompt_id: str
    theme: str
    motivating: str | None
    text: str
    gold: list[int]


@dataclass
class Prediction:
    sample: Sample
    scores: list[int]
    annulled: bool
    zero_reason: str | None
    third_run: bool
    cost_usd: Decimal
    error: str | None = None


# ---- dados ----------------------------------------------------------------------


def _paragraphs(raw: str) -> list[str]:
    # A maioria das células é uma lista Python; algumas são texto puro.
    # literal_eval só avalia literais, nunca executa código.
    try:
        value = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        value = raw.splitlines()
    if isinstance(value, str):
        value = value.splitlines()
    return [str(p).strip() for p in value if str(p).strip()]


def load_essay_br(root: Path) -> list[Sample]:
    csv.field_size_limit(sys.maxsize)
    base = root / "essay-br" if (root / "essay-br" / "essay-br.csv").exists() else root
    prompts: dict[str, list[str]] = {}
    with open(base / "prompts.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            prompts[row["id"]] = _paragraphs(row["description"])
    samples = []
    with open(base / "essay-br.csv", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            desc = prompts.get(row["prompt"], [])
            samples.append(
                Sample(
                    idx=i,
                    prompt_id=row["prompt"],
                    # A proposta (último parágrafo da descrição) costuma trazer o tema.
                    theme=desc[-1] if desc else (row.get("title") or "Tema não informado"),
                    motivating="\n\n".join(desc[:-1]) or None,
                    text="\n\n".join(_paragraphs(row["essay"])),
                    gold=[int(v) for v in ast.literal_eval(row["competence"])],
                )
            )
    return samples


# ---- execução -------------------------------------------------------------------


class Pacer:
    """Espaça as chamadas para não passar de `rpm` por minuto (cota do plano gratuito)."""

    def __init__(self, rpm: int | None):
        self.interval = 60.0 / rpm if rpm else 0.0
        self.next_at = 0.0
        self.lock = asyncio.Lock()

    async def wait(self) -> None:
        if not self.interval:
            return
        async with self.lock:
            now = time.monotonic()
            delay = max(0.0, self.next_at - now)
            self.next_at = max(now, self.next_at) + self.interval
        if delay:
            await asyncio.sleep(delay)


PACER = Pacer(None)


async def _grade(data: GradingInput, config: TaskConfig):
    await PACER.wait()
    return await grade_once(data, config=config, user_id=None, essay_id=None)


async def predict(sample: Sample, sem: asyncio.Semaphore, config: TaskConfig) -> Prediction:
    async with sem:
        checks = run_checks(sample.text, EssayInputType.text, sample.motivating)
        if checks.annulled:
            return Prediction(sample, [0] * 5, True, str(checks.zero_reason), False, Decimal(0))
        data = GradingInput(sample.theme, sample.motivating, sample.text, checks)
        cost = Decimal(0)
        try:
            results = list(await asyncio.gather(*(_grade(data, config) for _ in "ab")))
            runs = [normalize_run(i, r.output) for i, r in enumerate(results, start=1)]
            third = is_discrepant(runs[0], runs[1])
            if third:
                r3 = await _grade(data, config)
                results.append(r3)
                runs.append(normalize_run(3, r3.output))
            async with SessionLocal() as session:
                for r in results:
                    await save_usage(session, r)
                    cost += sum((u.cost_usd or Decimal(0)) for u in r.usage)
                await session.commit()
            final = consolidate(runs)
            return Prediction(sample, final.scores, final.annulled, final.zero_reason, third, cost)
        except Exception as exc:  # uma redação com erro não derruba o eval inteiro
            return Prediction(sample, [], False, None, False, cost, f"{type(exc).__name__}: {exc}")


# ---- métricas -------------------------------------------------------------------


def qwk(gold: list[int], pred: list[int], labels: list[int]) -> float:
    """Quadratic Weighted Kappa (Cohen) sobre um conjunto ordenado de rótulos."""
    index = {v: i for i, v in enumerate(labels)}
    n = len(labels)
    if not gold:
        return float("nan")
    obs = [[0.0] * n for _ in range(n)]
    for g, p in zip(gold, pred, strict=True):
        obs[index[g]][index[p]] += 1
    total = len(gold)
    hist_g = [sum(row) for row in obs]
    hist_p = [sum(obs[i][j] for i in range(n)) for j in range(n)]
    num = den = 0.0
    for i in range(n):
        for j in range(n):
            w = ((i - j) ** 2) / ((n - 1) ** 2)
            num += w * obs[i][j]
            den += w * hist_g[i] * hist_p[j] / total
    return 1.0 - num / den if den else 1.0


def snap(value: int, grid: list[int]) -> int:
    return min(grid, key=lambda g: (abs(g - value), g))


def metrics(gold: list[int], pred: list[int], labels: list[int], tolerance: int) -> dict:
    n = len(gold)
    diffs = [p - g for g, p in zip(gold, pred, strict=True)]
    return {
        "n": n,
        "qwk": round(qwk(gold, [snap(p, labels) for p in pred], labels), 3),
        "exact": round(100 * sum(d == 0 for d in diffs) / n, 1),
        "within": round(100 * sum(abs(d) <= tolerance for d in diffs) / n, 1),
        "mae": round(sum(abs(d) for d in diffs) / n, 1),
        "bias": round(sum(diffs) / n, 1),
    }


def confusion(gold: list[int], pred: list[int]) -> list[list[int]]:
    m = [[0] * len(LEVELS) for _ in LEVELS]
    for g, p in zip(gold, pred, strict=True):
        m[LEVELS.index(g)][LEVELS.index(snap(p, LEVELS))] += 1
    return m


# ---- relatório ------------------------------------------------------------------


def write_report(preds: list[Prediction], args, out_dir: Path, elapsed: float) -> Path:
    ok = [p for p in preds if p.error is None]
    version = prompt_version()
    config: TaskConfig = args.config
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / f"eval_{stamp}_{version.replace('+', '_')}"

    with open(f"{base}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "idx",
                "prompt",
                *[f"gold_c{i}" for i in range(1, 6)],
                "gold_total",
                *[f"pred_c{i}" for i in range(1, 6)],
                "pred_total",
                "annulled",
                "third_run",
                "cost_usd",
                "error",
            ]
        )
        for p in preds:
            w.writerow(
                [
                    p.sample.idx,
                    p.sample.prompt_id,
                    *p.sample.gold,
                    sum(p.sample.gold),
                    *(p.scores or [""] * 5),
                    sum(p.scores) if p.scores else "",
                    p.annulled,
                    p.third_run,
                    p.cost_usd,
                    p.error or "",
                ]
            )

    lines = [
        f"# Calibração da correção: {stamp}",
        "",
        f"- Prompt: `{version}`",
        f"- Modelo: `{config.model}` (provedor `{config.provider}`, "
        f"esforço `{config.effort or 'padrão'}`)",
        f"- Dataset: `{args.dataset}`; amostra de {len(preds)} redações (seed {args.seed})",
        f"- Concluídas: {len(ok)}; com erro: {len(preds) - len(ok)}; "
        f"3ª correção: {sum(p.third_run for p in ok)}",
        f"- Custo estimado: US$ {sum(p.cost_usd for p in preds):.4f}; tempo: {elapsed:.0f} s",
        "",
        "## Métricas",
        "",
        "| | QWK | exato % | ±40 % (total: ±80) | MAE | viés (pred − real) |",
        "|---|---|---|---|---|---|",
    ]
    summary: dict = {
        "created_at": datetime.now(UTC).isoformat(),
        "provider": config.provider,
        "model": config.model,
        "effort": config.effort,
        "prompt_version": version,
        "n": len(preds),
        "ok": len(ok),
        "cost_usd": float(sum(p.cost_usd for p in preds)),
        "report": f"{base.name}.md",
        "competencies": [],
        "total": None,
    }
    if ok:
        for c in range(5):
            m = metrics([p.sample.gold[c] for p in ok], [p.scores[c] for p in ok], PRED_GRID, 40)
            summary["competencies"].append(m)
            row = [m["qwk"], m["exact"], m["within"], m["mae"], m["bias"]]
            lines.append(f"| C{c + 1} | " + " | ".join(map(str, row)) + " |")
        totals = list(range(0, 1001, 20))
        m = metrics([sum(p.sample.gold) for p in ok], [sum(p.scores) for p in ok], totals, 80)
        summary["total"] = m
        lines.append(
            f"| **Total** | {m['qwk']} | {m['exact']} | {m['within']} | {m['mae']} | {m['bias']} |"
        )
        lines += [
            "",
            "Metas iniciais (docs/05): total com ≥ 70% dentro de ±80; cada competência com "
            "≥ 75% dentro de ±40 e QWK ≥ 0,6. Viés negativo/positivo grande indica que a IA "
            "puxa as notas para baixo/cima; previsões concentradas em 120 indicam achatamento.",
            "",
            "## Matrizes de confusão (linhas = nota real, colunas = prevista)",
        ]
        for c in range(5):
            m = confusion([p.sample.gold[c] for p in ok], [p.scores[c] for p in ok])
            lines += [
                "",
                f"### C{c + 1}",
                "",
                "| real \\ prev | " + " | ".join(map(str, LEVELS)) + " |",
                "|---" * (len(LEVELS) + 1) + "|",
            ]
            for lvl, row in zip(LEVELS, m, strict=True):
                lines.append(f"| {lvl} | " + " | ".join(map(str, row)) + " |")
    errors = [p for p in preds if p.error]
    if errors:
        lines += ["", "## Erros", ""] + [
            f"- redação {p.sample.idx}: {p.error}" for p in errors[:20]
        ]
    lines += ["", f"Predições completas: `{base.name}.csv`"]
    path = Path(f"{base}.md")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    Path(f"{base}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
    return path


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--dataset", default="data/essay-br")
    parser.add_argument("--n", type=int, default=200, help="quantas redações sortear")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument(
        "--rpm",
        type=int,
        help="máximo de chamadas por minuto (ex.: 10 no plano gratuito do Gemini, que permite 15)",
    )
    parser.add_argument("--out", default="reports")
    parser.add_argument("--yes", action="store_true", help="confirma o gasto com a API real")
    parser.add_argument("--provider", choices=["anthropic", "openai", "google", "fake"])
    parser.add_argument("--model", help="ID do modelo (padrão: o configurado para a correção)")
    args = parser.parse_args()

    async with SessionLocal() as session:
        args.config = await resolve_task(
            session, "grading", provider=args.provider, model=args.model
        )
    config: TaskConfig = args.config
    print(f"Provedor: {config.provider}; modelo: {config.model}")
    if config.provider != "fake" and not args.yes:
        print(
            f"Serão feitas de {2 * args.n} a {3 * args.n} chamadas de correção pagas "
            f"({config.provider}). Rode de novo com --yes para confirmar."
        )
        return
    if config.provider == "fake":
        print(
            "Aviso: provedor simulado. As métricas não significam nada "
            "(serve só para testar o script)."
        )

    samples = load_essay_br(Path(args.dataset))
    chosen = random.Random(args.seed).sample(samples, min(args.n, len(samples)))
    sem = asyncio.Semaphore(args.concurrency)
    global PACER
    PACER = Pacer(args.rpm)
    started = time.monotonic()
    preds: list[Prediction] = []
    for done, coro in enumerate(
        asyncio.as_completed([predict(s, sem, config) for s in chosen]), start=1
    ):
        preds.append(await coro)
        if done % 10 == 0 or done == len(chosen):
            print(f"{done}/{len(chosen)} redações", flush=True)
    preds.sort(key=lambda p: p.sample.idx)
    report = write_report(preds, args, Path(args.out), time.monotonic() - started)
    await engine.dispose()
    print(f"Relatório: {report}")
    print(json.dumps({"erros": sum(1 for p in preds if p.error)}))


if __name__ == "__main__":
    asyncio.run(main())
