"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Markdown } from "@/components/markdown";
import { Alert, Button, Card, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { type AssessmentPublic, type Attempt, type Letter, optionsOf } from "@/lib/assessments";

/** Prova aberta pelo link do professor: começar, responder (salva a cada escolha), entregar e ver o gabarito. */
export function AssessmentTaker() {
  const { code } = useParams<{ code: string }>();
  const [info, setInfo] = useState<AssessmentPublic | null>(null);
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [answers, setAnswers] = useState<Record<string, Letter>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState<number | null>(null);

  const open = useCallback((data: Attempt) => {
    setAttempt(data);
    setAnswers(data.answers as Record<string, Letter>);
  }, []);

  useEffect(() => {
    api.GET("/api/v1/assessments/by-code/{code}", { params: { path: { code } } }).then(async ({ data, error: e }) => {
      if (!data) {
        setError(errorMessage(e));
        return;
      }
      setInfo(data);
      if (data.attempt) {
        const res = await api.GET("/api/v1/assessments/attempts/{attempt_id}", {
          params: { path: { attempt_id: data.attempt.id } },
        });
        if (res.data) open(res.data);
      }
    });
  }, [code, open]);

  async function start() {
    setBusy(true);
    setError(null);
    const { data, error: e } = await api.POST("/api/v1/assessments/by-code/{code}/start", { params: { path: { code } } });
    setBusy(false);
    if (data) open(data);
    else setError(errorMessage(e));
  }

  async function choose(questionId: number, letter: Letter) {
    if (!attempt) return;
    const previous = answers[questionId];
    const next = previous === letter ? null : letter; // clicar de novo apaga a resposta
    setAnswers((prev) => {
      const copy = { ...prev };
      if (next) copy[questionId] = next;
      else delete copy[questionId];
      return copy;
    });
    setSaving(questionId);
    const { error: e } = await api.PUT("/api/v1/assessments/attempts/{attempt_id}/answers/{question_id}", {
      params: { path: { attempt_id: attempt.attempt.id, question_id: questionId } },
      body: { selected_option: next },
    });
    setSaving(null);
    if (e) {
      setError(errorMessage(e));
      // volta ao que está salvo no servidor (ex.: o professor fechou a prova)
      const res = await api.GET("/api/v1/assessments/attempts/{attempt_id}", {
        params: { path: { attempt_id: attempt.attempt.id } },
      });
      if (res.data) open(res.data);
    }
  }

  async function finish() {
    if (!attempt) return;
    const blank = attempt.questions.length - Object.keys(answers).length;
    const warning = blank > 0 ? `Você deixou ${blank} questão(ões) em branco. ` : "";
    if (!window.confirm(`${warning}Entregar a prova? Depois não dá para mudar as respostas.`)) return;
    setBusy(true);
    const { data, error: e } = await api.POST("/api/v1/assessments/attempts/{attempt_id}/finish", {
      params: { path: { attempt_id: attempt.attempt.id } },
    });
    setBusy(false);
    if (data) {
      open(data);
      window.scrollTo({ top: 0 });
    } else setError(errorMessage(e));
  }

  if (error && !info) return <Alert>{error}</Alert>;
  if (!info) return <Spinner />;

  if (!attempt) {
    return (
      <div className="max-w-2xl">
        <Card>
          <p className="text-sm text-slate-500">Prova de {info.teacher_name}</p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-900">{info.title}</h1>
          <p className="mt-1 text-slate-600">{info.question_count} questões</p>
          {info.instructions ? <p className="mt-3 whitespace-pre-line text-slate-800">{info.instructions}</p> : null}
          <div className="mt-4 space-y-3">
            {error ? <Alert>{error}</Alert> : null}
            {info.is_open ? (
              <>
                <Alert kind="info">
                  Seu nome, seu e-mail e suas respostas ficam visíveis para o professor. As respostas são salvas a
                  cada escolha; você vê o gabarito ao entregar.
                </Alert>
                <Button onClick={() => void start()} disabled={busy}>
                  {busy ? "Abrindo..." : "Começar a prova"}
                </Button>
              </>
            ) : (
              <Alert kind="warning">Esta prova não está aberta agora. Aguarde o professor liberar.</Alert>
            )}
          </div>
        </Card>
      </div>
    );
  }

  const finished = attempt.result !== null && attempt.result !== undefined;
  const result = Object.fromEntries((attempt.result ?? []).map((r) => [r.question_id, r]));
  const answered = Object.keys(answers).length;

  return (
    <div className="max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">{attempt.title}</h1>
        {attempt.instructions ? <p className="mt-1 whitespace-pre-line text-slate-600">{attempt.instructions}</p> : null}
      </header>

      {finished ? (
        <Card>
          <p className="text-sm text-slate-500">Prova entregue</p>
          <p className="text-4xl font-bold tabular-nums text-slate-900">
            {attempt.attempt.correct}
            <span className="text-xl font-medium text-slate-400"> / {attempt.attempt.total} acertos</span>
          </p>
          <p className="mt-1 text-sm text-slate-600">Confira abaixo o gabarito e a resolução de cada questão.</p>
        </Card>
      ) : !attempt.is_open ? (
        <Alert kind="warning">O professor fechou a prova: não dá mais para mudar as respostas. Entregue para ver o gabarito.</Alert>
      ) : null}
      {error ? <Alert>{error}</Alert> : null}

      <ol className="space-y-8">
        {attempt.questions.map((q, i) => {
          const r = result[q.id];
          const mine = finished ? r?.selected_option : answers[q.id];
          return (
            <li key={q.id} className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 sm:p-6">
              <p className="text-sm font-semibold text-slate-700">
                Questão {i + 1}
                {finished ? (
                  <span className={`ml-2 font-medium ${r?.is_correct ? "text-emerald-700" : "text-red-700"}`}>
                    {r?.is_correct ? "· acertou" : mine ? "· errou" : "· em branco"}
                  </span>
                ) : null}
              </p>
              <Markdown>{q.statement_md}</Markdown>
              <fieldset className="space-y-2" disabled={finished || !attempt.is_open}>
                <legend className="sr-only">Alternativas da questão {i + 1}</legend>
                {optionsOf(q).map((o) => {
                  const selected = mine === o.letter;
                  let tone = selected ? "border-indigo-500 bg-indigo-50" : "border-slate-200 bg-white hover:border-slate-300";
                  if (finished) {
                    if (o.letter === r?.correct_option) tone = "border-green-500 bg-green-50";
                    else if (selected) tone = "border-red-400 bg-red-50";
                    else tone = "border-slate-200 bg-white opacity-70";
                  }
                  return (
                    <label key={o.letter} className={`flex cursor-pointer gap-3 rounded-md border p-3 ${tone}`}>
                      <input
                        type="radio"
                        name={`q-${q.id}`}
                        checked={selected}
                        onChange={() => void choose(q.id, o.letter as Letter)}
                        onClick={() => {
                          if (selected && !finished) void choose(q.id, o.letter as Letter);
                        }}
                        className="mt-1"
                      />
                      {q.format === "true_false" ? null : <span className="font-semibold text-slate-700">{o.letter}</span>}
                      <Markdown className="flex-1">{o.text_md}</Markdown>
                    </label>
                  );
                })}
              </fieldset>
              {saving === q.id ? <p className="text-xs text-slate-500">Salvando...</p> : null}
              {finished && r?.explanation_md ? (
                <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <h3 className="mb-1 text-sm font-medium">Resolução</h3>
                  <Markdown>{r.explanation_md}</Markdown>
                </div>
              ) : null}
            </li>
          );
        })}
      </ol>

      {!finished ? (
        <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur md:mx-0 md:rounded-lg md:border">
          <span className="text-sm text-slate-600">
            {answered} de {attempt.questions.length} respondidas
          </span>
          <Button onClick={() => void finish()} disabled={busy}>
            {busy ? "Entregando..." : "Entregar prova"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
