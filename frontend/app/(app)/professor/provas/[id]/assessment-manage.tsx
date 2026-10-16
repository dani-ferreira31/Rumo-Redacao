"use client";

import { FileDown } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { EmptyState, Section, StatCard, StatusBadge, Toggle } from "@/components/admin/kit";
import { CopyButton } from "@/components/copy-button";
import { Markdown } from "@/components/markdown";
import { Alert, Button, Spinner } from "@/components/ui";
import { dateTime } from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";
import { type AssessmentDetail, type AssessmentResults, optionsOf, pct } from "@/lib/assessments";

export function AssessmentManage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [detail, setDetail] = useState<AssessmentDetail | null>(null);
  const [results, setResults] = useState<AssessmentResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showQuestions, setShowQuestions] = useState(false);

  const load = useCallback(async () => {
    const path = { params: { path: { assessment_id: id } } };
    const [d, r] = await Promise.all([
      api.GET("/api/v1/teacher/assessments/{assessment_id}", path),
      api.GET("/api/v1/teacher/assessments/{assessment_id}/results", path),
    ]);
    if (d.data) setDetail(d.data);
    else setError(errorMessage(d.error));
    if (r.data) setResults(r.data);
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial
    void load();
  }, [load]);

  async function setOpen(is_open: boolean) {
    const { data, error: e } = await api.PATCH("/api/v1/teacher/assessments/{assessment_id}", {
      params: { path: { assessment_id: id } },
      body: { is_open },
    });
    if (data) setDetail(data);
    else setError(errorMessage(e));
  }

  async function remove() {
    if (!window.confirm("Excluir esta prova e todas as respostas dos alunos? Não dá para desfazer.")) return;
    const { response, error: e } = await api.DELETE("/api/v1/teacher/assessments/{assessment_id}", {
      params: { path: { assessment_id: id } },
    });
    if (response.ok) router.replace("/professor");
    else setError(errorMessage(e));
  }

  if (error && !detail) return <Alert>{error}</Alert>;
  if (!detail) return <Spinner />;
  const position = Object.fromEntries(detail.questions.map((q) => [q.id, q.position]));

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <Link href="/professor" className="text-sm text-indigo-700 hover:underline">
          ← Área do professor
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-slate-900">{detail.title}</h1>
          <StatusBadge level={detail.is_open ? "ok" : "warning"}>{detail.is_open ? "Aberta" : "Fechada"}</StatusBadge>
        </div>
        <p className="text-sm text-slate-500">
          {detail.question_count} questões · criada em {dateTime(detail.created_at)}
        </p>
      </div>
      {error ? <Alert>{error}</Alert> : null}

      <Section title="Aplicar com a turma">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <code className="min-w-0 flex-1 break-all rounded bg-slate-100 px-2 py-1.5 text-sm">{detail.url}</code>
            <CopyButton text={detail.url} />
          </div>
          <p className="text-sm text-slate-600">
            Os alunos entram com a própria conta, respondem e veem o gabarito ao entregar. Cada aluno faz a prova uma vez.
          </p>
          <Toggle
            label="Prova aberta para respostas"
            description="Fechada, ninguém novo começa e quem não entregou não consegue mais responder."
            checked={detail.is_open}
            onChange={(v) => void setOpen(v)}
          />
        </div>
      </Section>

      <div className="flex flex-wrap gap-2">
        <a
          href={`/imprimir/prova/${detail.id}`}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
        >
          <FileDown aria-hidden className="h-4 w-4" />
          Exportar prova em PDF
        </a>
        <a
          href={`/imprimir/prova/${detail.id}?gabarito=1`}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
        >
          <FileDown aria-hidden className="h-4 w-4" />
          Prova com gabarito
        </a>
        <Link
          href={`/professor/provas/${detail.id}/editar`}
          className="inline-flex items-center rounded-md px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
        >
          Editar
        </Link>
        <Button variant="ghost" className="text-red-700" onClick={() => void remove()}>
          Excluir
        </Button>
      </div>

      <Section title="Resultados" actions={<Button variant="secondary" onClick={() => void load()}>Atualizar</Button>}>
        {!results ? (
          <Spinner />
        ) : results.attempts.length === 0 ? (
          <EmptyState>Nenhum aluno abriu a prova ainda.</EmptyState>
        ) : (
          <div className="space-y-6">
            <div className="grid gap-3 sm:grid-cols-3">
              <StatCard label="Alunos que abriram" value={results.attempts.length} />
              <StatCard label="Entregaram" value={results.finished} />
              <StatCard label="Média de acerto" value={pct(results.avg_pct)} />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[32rem] text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                    <th className="py-2 pr-3 font-medium">Aluno</th>
                    <th className="py-2 pr-3 font-medium">Situação</th>
                    <th className="py-2 pr-3 text-right font-medium">Acertos</th>
                    <th className="py-2 text-right font-medium">%</th>
                  </tr>
                </thead>
                <tbody>
                  {results.attempts.map((a) => (
                    <tr key={a.id} className="border-b border-slate-100 last:border-0">
                      <td className="py-2 pr-3">
                        <span className="font-medium text-slate-900">{a.student_name}</span>
                        <span className="block text-xs text-slate-500">{a.student_email}</span>
                      </td>
                      <td className="py-2 pr-3 text-slate-600">
                        {a.finished_at
                          ? `Entregou em ${dateTime(a.finished_at)}`
                          : `Respondendo (${a.answered} de ${a.total})`}
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">{a.correct === null ? "—" : `${a.correct} / ${a.total}`}</td>
                      <td className="py-2 text-right tabular-nums font-medium">{pct(a.pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <h3 className="mb-2 text-sm font-medium text-slate-700">Acerto por questão (só quem entregou)</h3>
              <ul className="grid gap-2 sm:grid-cols-2">
                {results.questions.map((q) => {
                  const tone = q.pct === null ? "bg-slate-300" : q.pct >= 70 ? "bg-emerald-500" : q.pct >= 40 ? "bg-amber-500" : "bg-red-500";
                  const wrong = Object.entries(q.distribution)
                    .filter(([letter]) => letter !== q.correct_option)
                    .sort((a, b) => b[1] - a[1])[0];
                  return (
                    <li key={q.question_id} className="rounded-md border border-slate-200 p-2 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">Questão {position[q.question_id] ?? q.position}</span>
                        <span className="tabular-nums text-slate-700">
                          {q.correct}/{q.answered} · {pct(q.pct)}
                        </span>
                      </div>
                      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100" aria-hidden>
                        <div className={`h-full ${tone}`} style={{ width: `${q.pct ?? 0}%` }} />
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        Gabarito {q.correct_option}
                        {wrong ? ` · erro mais comum: ${wrong[0]} (${wrong[1]})` : ""}
                      </p>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        )}
      </Section>

      <Section
        title="Questões"
        actions={
          <Button variant="secondary" onClick={() => setShowQuestions((v) => !v)}>
            {showQuestions ? "Esconder" : "Mostrar com gabarito"}
          </Button>
        }
      >
        {detail.instructions ? <p className="mb-3 whitespace-pre-line text-sm text-slate-700">{detail.instructions}</p> : null}
        {!showQuestions ? (
          <p className="text-sm text-slate-500">{detail.question_count} questões.</p>
        ) : (
          <ol className="space-y-6">
            {detail.questions.map((q) => (
              <li key={q.id} className="space-y-2 border-b border-slate-100 pb-6 last:border-0">
                <p className="text-sm font-semibold text-slate-700">
                  Questão {q.position} <span className="font-normal text-slate-500">· gabarito {q.correct_option}</span>
                </p>
                <Markdown>{q.statement_md}</Markdown>
                <ul className="space-y-1">
                  {optionsOf(q).map((o) => (
                    <li
                      key={o.letter}
                      className={`flex gap-2 rounded-md border p-2 ${o.letter === q.correct_option ? "border-emerald-400 bg-emerald-50" : "border-slate-200"}`}
                    >
                      {q.format === "true_false" ? null : <span className="font-semibold">{o.letter}</span>}
                      <Markdown className="flex-1">{o.text_md}</Markdown>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        )}
      </Section>
    </div>
  );
}
