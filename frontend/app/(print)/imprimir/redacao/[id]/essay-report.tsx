"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { PrintToolbar } from "@/components/print-toolbar";
import { Alert, Spinner } from "@/components/ui";
import { api, errorMessage, type Essay } from "@/lib/api";
import {
  C5_ELEMENT_LABEL,
  COMPETENCY_NAMES,
  DEVIATION_LABEL,
  ZERO_REASON_LABEL,
  formatDate,
} from "@/lib/essays";

/** Devolutiva completa da correção (as 5 competências numa página), para imprimir ou salvar em PDF. */
export function EssayReport() {
  const { id } = useParams<{ id: string }>();
  const [essay, setEssay] = useState<Essay | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [student, setStudent] = useState("");
  const [withText, setWithText] = useState(true);

  useEffect(() => {
    api.GET("/api/v1/essays/{essay_id}", { params: { path: { essay_id: id } } }).then(({ data, error: e }) => {
      if (data) setEssay(data);
      else setError(errorMessage(e));
    });
  }, [id]);

  if (error) return <div className="p-6"><Alert>{error}</Alert></div>;
  if (!essay) return <div className="p-6"><Spinner /></div>;
  const result = essay.result;
  if (essay.status !== "graded" || !result) {
    return <div className="p-6"><Alert kind="info">A redação ainda não foi corrigida.</Alert></div>;
  }

  return (
    <>
      <PrintToolbar>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          Nome do aluno
          <input
            value={student}
            onChange={(e) => setStudent(e.target.value)}
            placeholder="opcional"
            className="w-48 rounded-md border border-slate-300 bg-white px-2 py-1"
          />
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={withText} onChange={(e) => setWithText(e.target.checked)} />
          Incluir o texto avaliado
        </label>
      </PrintToolbar>

      <article className="mx-auto max-w-3xl space-y-6 px-6 py-8 text-slate-900 print:max-w-none print:px-0 print:py-0">
        <header className="border-b border-slate-300 pb-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-indigo-700">Rumo1000 · Devolutiva da redação</p>
          <h1 className="mt-1 text-2xl font-semibold">{essay.theme_title}</h1>
          <p className="mt-1 text-sm text-slate-600">
            {student ? <><strong>{student}</strong> · </> : null}
            Corrigida em {formatDate(essay.graded_at ?? essay.created_at)}
            {essay.line_count ? ` · ${essay.line_count} linhas` : ""}
          </p>
        </header>

        <section className="break-inside-avoid">
          <div className="flex flex-wrap items-end gap-6">
            <p className="text-5xl font-bold tabular-nums">
              {result.total}
              <span className="text-xl font-medium text-slate-400"> / 1000</span>
            </p>
            {result.annulled ? (
              <p className="font-medium text-red-700">
                Redação anulada: {ZERO_REASON_LABEL[result.zero_reason ?? ""] ?? result.zero_reason}
              </p>
            ) : null}
          </div>
          {!result.annulled ? (
            <table className="mt-4 w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-300 text-left">
                  <th className="py-1.5 pr-3 font-medium">Competência</th>
                  <th className="py-1.5 text-right font-medium">Nota</th>
                </tr>
              </thead>
              <tbody>
                {result.scores.map((s, i) => (
                  <tr key={i} className="border-b border-slate-100">
                    <td className="py-1.5 pr-3">
                      C{i + 1} · {COMPETENCY_NAMES[i + 1]}
                    </td>
                    <td className="py-1.5 text-right tabular-nums font-medium">{s}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          {result.tangent ? <p className="mt-2 text-sm text-amber-800">Houve tangenciamento do tema.</p> : null}
          {result.human_rights_violation ? (
            <p className="mt-2 text-sm text-red-700">A proposta de intervenção desrespeita os direitos humanos: C5 com nota 0.</p>
          ) : null}
          {result.simulated ? <p className="mt-2 text-sm text-amber-800">Correção simulada (modo de desenvolvimento).</p> : null}
        </section>

        {result.general_comment ? (
          <section className="break-inside-avoid">
            <h2 className="mb-1 text-lg font-semibold">Comentário geral</h2>
            <p className="whitespace-pre-line">{result.general_comment}</p>
            {result.next_steps.length ? (
              <>
                <h3 className="mt-3 font-medium">Próximos passos</h3>
                <ol className="mt-1 list-decimal space-y-1 pl-5">
                  {result.next_steps.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
              </>
            ) : null}
          </section>
        ) : null}

        {!result.annulled
          ? result.competencies.map((c) => (
              <section key={c.number} className="space-y-3 border-t border-slate-200 pt-4">
                <h2 className="text-lg font-semibold">
                  Competência {c.number}: {COMPETENCY_NAMES[c.number]} · {c.score}
                </h2>
                <p className="text-slate-600">{c.level_summary}</p>
                <p className="whitespace-pre-line">{c.justification}</p>
                <div className="grid gap-4 sm:grid-cols-2 print:grid-cols-2">
                  <div className="break-inside-avoid">
                    <h3 className="font-medium text-green-800">Pontos fortes</h3>
                    <ul className="mt-1 list-disc space-y-1 pl-5">
                      {c.strengths.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="break-inside-avoid">
                    <h3 className="font-medium text-amber-800">O que melhorar</h3>
                    <ul className="mt-1 list-disc space-y-1 pl-5">
                      {c.improvements.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                </div>
                {c.excerpts.length ? (
                  <div>
                    <h3 className="font-medium">Trechos comentados</h3>
                    <ul className="mt-1 space-y-2">
                      {c.excerpts.map((e, i) => (
                        <li key={i} className="break-inside-avoid border-l-2 border-slate-300 pl-3">
                          <p className="font-serif">
                            {e.line ? <span className="mr-2 text-xs text-slate-500">L{e.line}</span> : null}“{e.text}”
                          </p>
                          <p className="text-sm text-slate-700">{e.comment}</p>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {c.number === 1 && result.c1_deviations.length ? (
                  <div>
                    <h3 className="font-medium">Desvios encontrados ({result.c1_deviations.length})</h3>
                    <table className="mt-1 w-full border-collapse text-left text-sm">
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
                          <tr key={i} className="break-inside-avoid border-t border-slate-100 align-top">
                            <td className="py-1 pr-3 tabular-nums">{d.line ?? "-"}</td>
                            <td className="py-1 pr-3 font-serif">{d.text}</td>
                            <td className="py-1 pr-3">{DEVIATION_LABEL[d.type] ?? d.type}</td>
                            <td className="py-1">{d.suggestion}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
                {c.number === 5 && result.c5_elements ? (
                  <div>
                    <h3 className="font-medium">Elementos da proposta de intervenção</h3>
                    <ul className="mt-1 space-y-1 text-sm">
                      {Object.entries(result.c5_elements).map(([key, el]) => (
                        <li key={key}>
                          <strong>{el.present ? "✓" : "✕"} {C5_ELEMENT_LABEL[key] ?? key}</strong>
                          {el.present ? "" : " (ausente)"}
                          {el.excerpt ? <span className="font-serif text-slate-700">: “{el.excerpt}”</span> : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </section>
            ))
          : null}

        {withText && essay.transcription_text ? (
          <section className="border-t border-slate-200 pt-4 print:break-before-page">
            <h2 className="mb-2 text-lg font-semibold">Texto avaliado</h2>
            <ol className="font-serif text-sm leading-relaxed">
              {essay.transcription_text.split("\n").map((line, i) => (
                <li key={i} className="flex gap-3">
                  <span className="w-6 shrink-0 text-right text-xs tabular-nums text-slate-400">{i + 1}</span>
                  <span className="whitespace-pre-wrap">{line || " "}</span>
                </li>
              ))}
            </ol>
          </section>
        ) : null}

        <footer className="border-t border-slate-200 pt-3 text-xs text-slate-500">
          Correção feita por inteligência artificial com base na matriz de referência do ENEM. A nota é uma estimativa.
        </footer>
      </article>
    </>
  );
}
