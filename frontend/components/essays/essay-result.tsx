"use client";

import { useState } from "react";

import { Alert } from "@/components/ui";
import type { EssayResult } from "@/lib/api";
import {
  C5_ELEMENT_LABEL,
  COMPETENCY_NAMES,
  DEVIATION_LABEL,
  ZERO_REASON_LABEL,
} from "@/lib/essays";

function ScoreBar({ value }: { value: number }) {
  return (
    <div className="h-2 w-full rounded-full bg-slate-100" aria-hidden>
      <div className="h-2 rounded-full bg-indigo-600" style={{ width: `${(value / 200) * 100}%` }} />
    </div>
  );
}

export function EssayResultView({ result }: { result: EssayResult }) {
  const [tab, setTab] = useState(1);
  const competency = result.competencies.find((c) => c.number === tab);

  return (
    <div className="space-y-6">
      {result.simulated ? (
        <Alert kind="warning">
          Correção simulada: o sistema está em modo de desenvolvimento, sem IA real. As notas e os
          comentários abaixo são apenas exemplos.
        </Alert>
      ) : null}

      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <p className="text-sm text-slate-500">Nota total</p>
        <p className="text-5xl font-bold tabular-nums text-slate-900">
          {result.total}
          <span className="text-xl font-medium text-slate-400"> / 1000</span>
        </p>
        {result.annulled ? (
          <p className="mt-2 font-medium text-red-700">
            Redação anulada: {ZERO_REASON_LABEL[result.zero_reason ?? ""] ?? result.zero_reason}
          </p>
        ) : null}
        {result.tangent ? (
          <p className="mt-2 text-sm text-amber-800">
            Tangenciamento do tema: limita a C2 a 40 e as C3 e C5 a no máximo 40.
          </p>
        ) : null}
        {result.human_rights_violation ? (
          <p className="mt-2 text-sm text-red-700">
            A proposta de intervenção desrespeita os direitos humanos: a C5 fica com nota 0.
          </p>
        ) : null}
        {!result.annulled ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-5">
            {result.scores.map((s, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setTab(i + 1)}
                className="rounded-md border border-slate-200 p-3 text-left hover:border-indigo-400"
              >
                <p className="text-xs text-slate-500">C{i + 1}</p>
                <p className="text-xl font-semibold tabular-nums text-slate-900">{s}</p>
                <ScoreBar value={s} />
                <p className="mt-1 text-xs text-slate-500">{COMPETENCY_NAMES[i + 1]}</p>
              </button>
            ))}
          </div>
        ) : null}
        {result.needed_third_run ? (
          <p className="mt-3 text-xs text-slate-500">
            Houve divergência entre as duas primeiras correções, e uma terceira foi feita, como no
            ENEM. A nota final é a média das duas mais próximas.
          </p>
        ) : null}
      </section>

      {result.general_comment ? (
        <section className="rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="mb-2 text-lg font-semibold">Comentário geral</h2>
          <p className="whitespace-pre-line text-slate-800">{result.general_comment}</p>
          {result.next_steps.length ? (
            <>
              <h3 className="mt-4 font-medium">Próximos passos</h3>
              <ol className="mt-1 list-decimal space-y-1 pl-5 text-slate-800">
                {result.next_steps.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ol>
            </>
          ) : null}
        </section>
      ) : null}

      {result.warnings.length ? (
        <ul className="space-y-1 text-sm text-slate-600">
          {result.warnings.map((w, i) => (
            <li key={i}>• {w}</li>
          ))}
        </ul>
      ) : null}

      {competency && !result.annulled ? (
        <section className="rounded-lg border border-slate-200 bg-white">
          <div role="tablist" className="flex overflow-x-auto border-b border-slate-200">
            {result.competencies.map((c) => (
              <button
                key={c.number}
                role="tab"
                aria-selected={tab === c.number}
                type="button"
                onClick={() => setTab(c.number)}
                className={`whitespace-nowrap px-4 py-3 text-sm font-medium ${
                  tab === c.number
                    ? "border-b-2 border-indigo-600 text-indigo-700"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                C{c.number} · {c.score}
              </button>
            ))}
          </div>
          <div className="space-y-4 p-6">
            <div>
              <h2 className="text-lg font-semibold">
                Competência {competency.number}: {COMPETENCY_NAMES[competency.number]}
              </h2>
              <p className="text-slate-600">{competency.level_summary}</p>
            </div>
            <p className="whitespace-pre-line text-slate-800">{competency.justification}</p>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <h3 className="font-medium text-green-800">Pontos fortes</h3>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-800">
                  {competency.strengths.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h3 className="font-medium text-amber-800">O que melhorar</h3>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-800">
                  {competency.improvements.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            </div>
            {competency.excerpts.length ? (
              <div>
                <h3 className="font-medium">Trechos comentados</h3>
                <ul className="mt-2 space-y-2">
                  {competency.excerpts.map((e, i) => (
                    <li key={i} className="rounded-md bg-slate-50 p-3">
                      <p className="font-serif text-slate-900">
                        {e.line ? <span className="mr-2 text-xs text-slate-500">L{e.line}</span> : null}“{e.text}”
                      </p>
                      <p className="mt-1 text-sm text-slate-700">{e.comment}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {competency.number === 1 && result.c1_deviations.length ? (
              <div>
                <h3 className="font-medium">Desvios encontrados ({result.c1_deviations.length})</h3>
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="text-slate-500">
                      <tr>
                        <th className="py-1 pr-3 font-medium">Linha</th>
                        <th className="py-1 pr-3 font-medium">Trecho</th>
                        <th className="py-1 pr-3 font-medium">Tipo</th>
                        <th className="py-1 font-medium">Sugestão</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.c1_deviations.map((d, i) => (
                        <tr key={i} className="border-t border-slate-100 align-top">
                          <td className="py-1 pr-3 tabular-nums">{d.line ?? "-"}</td>
                          <td className="py-1 pr-3 font-serif">{d.text}</td>
                          <td className="py-1 pr-3">{DEVIATION_LABEL[d.type] ?? d.type}</td>
                          <td className="py-1">{d.suggestion}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}

            {competency.number === 5 && result.c5_elements ? (
              <div>
                <h3 className="font-medium">Elementos da proposta de intervenção</h3>
                <ul className="mt-2 space-y-2">
                  {Object.entries(result.c5_elements).map(([key, el]) => (
                    <li key={key} className="flex gap-3">
                      <span
                        className={`mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                          el.present ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                        }`}
                        aria-hidden
                      >
                        {el.present ? "✓" : "✕"}
                      </span>
                      <div>
                        <p className="font-medium text-slate-900">
                          {C5_ELEMENT_LABEL[key] ?? key}
                          <span className="sr-only">{el.present ? ": presente" : ": ausente"}</span>
                        </p>
                        {el.excerpt ? <p className="font-serif text-sm text-slate-700">“{el.excerpt}”</p> : (
                          <p className="text-sm text-slate-500">Não encontrado no texto.</p>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}
