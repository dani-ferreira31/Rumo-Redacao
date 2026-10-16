"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Alert, Spinner } from "@/components/ui";
import { api, errorMessage, type QuestionStats } from "@/lib/api";
import { AREA_LABEL } from "@/lib/questions";

/** % de acerto por grupo: uma medida só, barras horizontais da mesma cor com rótulo. */
function PctBars({ rows }: { rows: { key: string; label: string; answered: number; correct: number; pct?: number | null }[] }) {
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.key}>
          <div className="mb-1 flex justify-between text-sm">
            <span className="text-slate-800">{r.label}</span>
            <span className="tabular-nums text-slate-600">
              {r.pct !== null && r.pct !== undefined ? `${r.pct}%` : "—"} · {r.correct}/{r.answered}
            </span>
          </div>
          <div className="h-2.5 rounded-full bg-slate-100" aria-hidden>
            <div className="h-2.5 rounded-full bg-indigo-600" style={{ width: `${r.pct ?? 0}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function QuestionStatsView() {
  const [stats, setStats] = useState<QuestionStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.GET("/api/v1/questions/stats").then(({ data, error: apiError }) => {
      if (data) setStats(data);
      else setError(errorMessage(apiError));
    });
  }, []);

  if (error) return <Alert>{error}</Alert>;
  if (!stats) return <Spinner />;

  return (
    <div className="max-w-4xl space-y-6">
      <Link href="/questoes" className="text-sm text-indigo-700 hover:underline">
        ← Questões
      </Link>
      <PageHeader
        title="Minhas estatísticas"
        description="Acerto considerando a última resposta de cada questão."
      />
      {stats.answered === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-slate-600">
          Você ainda não respondeu questões.{" "}
          <Link href="/questoes" className="text-indigo-700 hover:underline">
            Começar a praticar
          </Link>
        </div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-sm text-slate-500">Questões respondidas</p>
              <p className="text-3xl font-semibold tabular-nums">{stats.answered}</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-sm text-slate-500">Acertos</p>
              <p className="text-3xl font-semibold tabular-nums">{stats.correct}</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-sm text-slate-500">Aproveitamento</p>
              <p className="text-3xl font-semibold tabular-nums">{stats.pct ?? 0}%</p>
            </div>
          </div>

          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="mb-4 font-semibold">Por área</h2>
            <PctBars
              rows={stats.by_area.map((a) => ({
                key: a.code,
                label: AREA_LABEL[a.code] ?? a.name,
                answered: a.answered,
                correct: a.correct,
                pct: a.pct,
              }))}
            />
          </section>

          {stats.by_subject.length ? (
            <section className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="mb-4 font-semibold">Por disciplina</h2>
              <PctBars
                rows={stats.by_subject.map((s) => ({
                  key: String(s.id),
                  label: s.name,
                  answered: s.answered,
                  correct: s.correct,
                  pct: s.pct,
                }))}
              />
            </section>
          ) : null}

          {stats.by_topic.length ? (
            <section className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="mb-4 font-semibold">Por tópico</h2>
              <PctBars
                rows={stats.by_topic.map((t) => ({
                  key: String(t.id),
                  label: t.name,
                  answered: t.answered,
                  correct: t.correct,
                  pct: t.pct,
                }))}
              />
            </section>
          ) : null}

          {stats.timeline.length ? (
            <section className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="mb-3 font-semibold">Últimas semanas</h2>
              <table className="w-full text-left text-sm">
                <thead className="text-slate-500">
                  <tr>
                    <th className="py-1 font-medium">Semana de</th>
                    <th className="py-1 text-right font-medium">Respondidas</th>
                    <th className="py-1 text-right font-medium">Acertos</th>
                    <th className="py-1 text-right font-medium">%</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.timeline.map((p) => (
                    <tr key={p.week} className="border-t border-slate-100">
                      <td className="py-1">{new Date(`${p.week}T12:00:00`).toLocaleDateString("pt-BR")}</td>
                      <td className="py-1 text-right tabular-nums">{p.answered}</td>
                      <td className="py-1 text-right tabular-nums">{p.correct}</td>
                      <td className="py-1 text-right tabular-nums">
                        {p.answered ? Math.round((100 * p.correct) / p.answered) : 0}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
