"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { QuestionView } from "@/components/questions/question-view";
import { Alert, Button, Spinner } from "@/components/ui";
import {
  api,
  errorMessage,
  type PracticeSession,
  type Question,
  type SessionResult,
} from "@/lib/api";
import { AREA_LABEL } from "@/lib/questions";

type Letter = "A" | "B" | "C" | "D" | "E";

function useCountdown(deadline: number | null, onExpire: () => void) {
  const [left, setLeft] = useState<number | null>(null);
  useEffect(() => {
    if (deadline === null) return;
    const tick = () => {
      const s = Math.max(0, Math.round((deadline - Date.now()) / 1000));
      setLeft(s);
      if (s === 0) onExpire();
    };
    const timer = setInterval(tick, 1000);
    const first = setTimeout(tick, 0);
    return () => {
      clearInterval(timer);
      clearTimeout(first);
    };
  }, [deadline, onExpire]);
  return left;
}

function formatClock(s: number) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${h ? `${h}:` : ""}${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

export function PracticeRunner() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [session, setSession] = useState<PracticeSession | null>(null);
  const [index, setIndex] = useState(0);
  const [question, setQuestion] = useState<Question | null>(null);
  const [answers, setAnswers] = useState<Record<number, Letter>>({});
  const [result, setResult] = useState<SessionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);

  const finish = useCallback(
    () =>
      api
        .POST("/api/v1/practice-sessions/{session_id}/finish", {
          params: { path: { session_id: sessionId } },
        })
        .then(({ data, error: apiError }) => {
          setFinishing(false);
          if (data) setResult(data);
          else setError(errorMessage(apiError));
        }),
    [sessionId],
  );

  function requestFinish() {
    setFinishing(true);
    finish();
  }

  useEffect(() => {
    api
      .GET("/api/v1/practice-sessions/{session_id}", { params: { path: { session_id: sessionId } } })
      .then(({ data, error: apiError }) => {
        if (!data) return setError(errorMessage(apiError));
        setSession(data);
        setAnswers(data.answers as Record<number, Letter>);
        if (data.finished_at) finish();
      });
  }, [sessionId, finish]);

  const qid = session?.question_ids[index];
  useEffect(() => {
    if (!qid) return;
    api
      .GET("/api/v1/questions/{question_id}", { params: { path: { question_id: qid } } })
      .then(({ data, error: apiError }) => {
        if (data) setQuestion(data);
        else setError(errorMessage(apiError));
      });
  }, [qid]);

  const deadline =
    session && session.time_limit_seconds && !session.finished_at
      ? new Date(session.started_at).getTime() + session.time_limit_seconds * 1000
      : null;
  const left = useCountdown(result ? null : deadline, finish);

  if (error && !session) return <Alert>{error}</Alert>;
  if (!session) return <Spinner />;

  if (result) return <ResultView result={result} />;

  const total = session.question_ids.length;
  const hideFeedback = session.mode !== "livre";
  const answeredCount = Object.keys(answers).length;

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link href="/questoes" className="text-sm text-indigo-700 hover:underline">
          ← Questões
        </Link>
        <div className="flex items-center gap-3 text-sm text-slate-600">
          <span>
            Questão {index + 1} de {total} · {answeredCount} respondida(s)
          </span>
          {left !== null ? (
            <span className={`rounded px-2 py-0.5 font-mono ${left < 300 ? "bg-red-100 text-red-800" : "bg-slate-100"}`} aria-live="polite">
              ⏱ {formatClock(left)}
            </span>
          ) : null}
        </div>
      </div>

      {hideFeedback ? (
        <Alert kind="info">Modo lista: o gabarito aparece quando você encerrar.</Alert>
      ) : null}
      {error ? <Alert>{error}</Alert> : null}

      {question && question.id === qid ? (
        <QuestionView
          key={question.id}
          question={question}
          practiceSessionId={session.id}
          hideFeedback={hideFeedback}
          initialSelected={answers[question.id]}
          onAnswered={(sel) => setAnswers((prev) => ({ ...prev, [question.id]: sel }))}
        />
      ) : (
        <Spinner />
      )}

      <nav className="flex flex-wrap items-center gap-2 border-t border-slate-200 pt-4">
        <Button variant="secondary" onClick={() => setIndex((i) => Math.max(0, i - 1))} disabled={index === 0}>
          Anterior
        </Button>
        <Button variant="secondary" onClick={() => setIndex((i) => Math.min(total - 1, i + 1))} disabled={index === total - 1}>
          Próxima
        </Button>
        <div className="flex flex-wrap gap-1" aria-label="Ir para a questão">
          {session.question_ids.map((id, i) => (
            <button
              key={id}
              type="button"
              onClick={() => setIndex(i)}
              aria-current={i === index ? "step" : undefined}
              className={`h-7 w-7 rounded text-xs ${
                i === index ? "bg-indigo-600 text-white" : answers[id] ? "bg-indigo-100 text-indigo-900" : "bg-slate-100 text-slate-700"
              }`}
            >
              {i + 1}
            </button>
          ))}
        </div>
        <Button className="ml-auto" onClick={requestFinish} disabled={finishing}>
          {finishing ? "Encerrando..." : "Encerrar"}
        </Button>
      </nav>
    </div>
  );
}

function ResultView({ result }: { result: SessionResult }) {
  const pct = result.total ? Math.round((100 * result.correct) / result.total) : 0;
  return (
    <div className="max-w-3xl space-y-5">
      <Link href="/questoes" className="text-sm text-indigo-700 hover:underline">
        ← Questões
      </Link>
      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <p className="text-sm text-slate-500">Resultado</p>
        <p className="text-4xl font-bold tabular-nums text-slate-900">
          {result.correct}
          <span className="text-xl font-medium text-slate-400"> / {result.total}</span>
        </p>
        <p className="text-slate-600">
          {pct}% de acerto · {result.answered} respondida(s)
        </p>
        {result.by_area.length ? (
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {result.by_area.map((a) => (
              <li key={a.code} className="rounded-md bg-slate-50 p-3 text-sm">
                <span className="font-medium">{AREA_LABEL[a.code] ?? a.name}</span>: {a.correct}/{a.answered}
                {a.pct !== null && a.pct !== undefined ? ` (${a.pct}%)` : ""}
              </li>
            ))}
          </ul>
        ) : null}
      </section>
      <section className="rounded-lg border border-slate-200 bg-white">
        <h2 className="border-b border-slate-200 px-4 py-3 font-semibold">Gabarito</h2>
        <ol className="divide-y divide-slate-100">
          {result.items.map((item, i) => (
            <li key={item.question_id} className="flex items-center justify-between gap-3 px-4 py-2 text-sm">
              <span>
                {i + 1}. Sua resposta: <strong>{item.selected_option ?? "—"}</strong> · correta:{" "}
                <strong>{item.correct_option ?? "anulada"}</strong>
              </span>
              <span className="flex items-center gap-3">
                <span className={item.is_correct ? "text-green-700" : "text-red-700"}>
                  {item.is_correct ? "✓ acertou" : "✕"}
                </span>
                <Link href={`/questoes/${item.question_id}`} className="text-indigo-700 hover:underline">
                  ver
                </Link>
              </span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
