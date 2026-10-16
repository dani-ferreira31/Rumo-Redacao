"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Markdown } from "@/components/markdown";
import { PrintToolbar } from "@/components/print-toolbar";
import { Alert, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { type AssessmentDetail, optionsOf } from "@/lib/assessments";

/** Prova pronta para imprimir ou salvar em PDF; com ?gabarito=1, o gabarito sai na última página. */
export function AssessmentPrint() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const [withKey, setWithKey] = useState(params.get("gabarito") === "1");
  const [detail, setDetail] = useState<AssessmentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.GET("/api/v1/teacher/assessments/{assessment_id}", { params: { path: { assessment_id: id } } }).then(({ data, error: e }) => {
      if (data) setDetail(data);
      else setError(errorMessage(e));
    });
  }, [id]);

  if (error) return <div className="p-6"><Alert>{error}</Alert></div>;
  if (!detail) return <div className="p-6"><Spinner /></div>;

  return (
    <>
      <PrintToolbar>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={withKey} onChange={(e) => setWithKey(e.target.checked)} />
          Incluir gabarito no final
        </label>
      </PrintToolbar>

      <article className="mx-auto max-w-3xl px-6 py-8 text-slate-900 print:max-w-none print:p-0">
        <header className="mb-6 space-y-3 border-b border-slate-400 pb-4">
          <h1 className="text-2xl font-semibold">{detail.title}</h1>
          <div className="grid grid-cols-[1fr_auto] gap-x-6 gap-y-2 text-sm">
            <p>Nome: ______________________________________________</p>
            <p>Data: ____/____/______</p>
            <p>Turma: _____________</p>
            <p>Acertos: ______ de {detail.question_count}</p>
          </div>
          {detail.instructions ? <p className="whitespace-pre-line text-sm">{detail.instructions}</p> : null}
        </header>

        <ol className="space-y-6">
          {detail.questions.map((q) => (
            <li key={q.id} className="space-y-2 break-inside-avoid-page">
              <p className="font-semibold">Questão {q.position}</p>
              <Markdown className="text-[15px]">{q.statement_md}</Markdown>
              {q.format === "true_false" ? (
                <p className="text-sm">( ) Certo &nbsp;&nbsp; ( ) Errado</p>
              ) : (
                <ul className="space-y-1">
                  {optionsOf(q).map((o) => (
                    <li key={o.letter} className="flex gap-2">
                      <span className="font-semibold">({o.letter})</span>
                      <Markdown className="flex-1 text-[15px]">{o.text_md}</Markdown>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ol>

        {withKey ? (
          <section className="mt-10 border-t border-slate-400 pt-4 print:break-before-page">
            <h2 className="mb-3 text-lg font-semibold">Gabarito</h2>
            <table className="border-collapse text-sm">
              <tbody>
                {Array.from({ length: Math.ceil(detail.questions.length / 10) }, (_, row) => (
                  <tr key={row}>
                    {detail.questions.slice(row * 10, row * 10 + 10).map((q) => (
                      <td key={q.id} className="border border-slate-300 px-3 py-1 text-center">
                        <span className="block text-xs text-slate-500">{q.position}</span>
                        <span className="font-semibold">{q.correct_option}</span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : null}
      </article>
    </>
  );
}
