"use client";

import { useEffect, useRef, useState } from "react";

import { Markdown } from "@/components/markdown";
import { Alert, Button } from "@/components/ui";
import { api, errorMessage, type AnswerResult, type Question } from "@/lib/api";
import { AREA_LABEL, DIFFICULTY_LABEL, LANGUAGE_LABEL } from "@/lib/questions";

type Letter = "A" | "B" | "C" | "D" | "E";

export function QuestionView({
  question,
  practiceSessionId,
  initialSelected,
  onAnswered,
  hideFeedback = false,
}: {
  question: Question;
  practiceSessionId?: string;
  initialSelected?: Letter;
  onAnswered?: (selected: Letter, result: AnswerResult) => void;
  /** Lista/simulado: registra a resposta sem mostrar o gabarito. */
  hideFeedback?: boolean;
}) {
  const [selected, setSelected] = useState<Letter | null>(initialSelected ?? null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  // Lista/simulado: a última resposta enviada (pode ser trocada até encerrar).
  const [registered, setRegistered] = useState<Letter | null>(initialSelected ?? null);
  const [bookmarked, setBookmarked] = useState(question.bookmarked);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const startedAt = useRef(0);

  useEffect(() => {
    startedAt.current = performance.now();
  }, [question.id]);

  const locked = result !== null && !hideFeedback; // na prática livre, responde uma vez
  const unchanged = hideFeedback && selected !== null && selected === registered;

  async function submit() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    const { data, error: apiError } = await api.POST("/api/v1/questions/{question_id}/answer", {
      params: { path: { question_id: question.id } },
      body: {
        selected_option: selected,
        time_spent_seconds: Math.round((performance.now() - startedAt.current) / 1000),
        practice_session_id: practiceSessionId,
      },
    });
    setBusy(false);
    if (!data) {
      setError(errorMessage(apiError));
      return;
    }
    setResult(data);
    setRegistered(selected);
    onAnswered?.(selected, data);
  }

  async function toggleBookmark() {
    const next = !bookmarked;
    setBookmarked(next);
    const method = next ? api.PUT : api.DELETE;
    const { response } = await method("/api/v1/questions/{question_id}/bookmark", {
      params: { path: { question_id: question.id } },
    });
    if (!response.ok) setBookmarked(!next);
  }

  const showFeedback = result !== null && !hideFeedback && result.correct_option;
  const trueFalse = question.format === "true_false";
  const options = trueFalse
    ? [
        { letter: "C", text_md: "**Certo**" },
        { letter: "E", text_md: "**Errado**" },
      ]
    : question.options;
  const contestLabel = question.track === "concurso" ? question.positions[0]?.label : null;

  return (
    <article className="space-y-4">
      <header className="flex flex-wrap items-center gap-2 text-sm">
        {contestLabel ? (
          <span className="rounded-full bg-rose-50 px-2 py-0.5 font-medium text-rose-800">{contestLabel}</span>
        ) : (
          <>
            <span className="rounded-full bg-indigo-50 px-2 py-0.5 font-medium text-indigo-800">
              {AREA_LABEL[question.area_code] ?? question.area_code}
            </span>
            <span className="text-slate-600">ENEM {question.year}</span>
          </>
        )}
        {question.subject ? <span className="text-slate-600">· {question.subject.name}</span> : null}
        {question.foreign_language ? (
          <span className="text-slate-600">· {LANGUAGE_LABEL[question.foreign_language]}</span>
        ) : null}
        {question.difficulty ? (
          <span className="text-slate-600">· {DIFFICULTY_LABEL[question.difficulty]}</span>
        ) : null}
        {question.skill_code ? <span className="text-slate-600">· H{question.skill_code}</span> : null}
        {question.positions[0] ? (
          <span className="text-slate-500">· questão {question.positions[0].position}</span>
        ) : null}
        <button
          type="button"
          onClick={toggleBookmark}
          aria-pressed={bookmarked}
          className="ml-auto rounded-md px-2 py-1 text-sm text-slate-700 hover:bg-slate-100"
        >
          {bookmarked ? "★ Favorita" : "☆ Favoritar"}
        </button>
      </header>

      <Markdown>{question.statement_md}</Markdown>

      <fieldset className={trueFalse ? "grid grid-cols-2 gap-2 sm:max-w-sm" : "space-y-2"}>
        <legend className="sr-only">{trueFalse ? "Julgue o item" : "Alternativas"}</legend>
        {options.map((opt) => {
          const isSelected = selected === opt.letter;
          let tone = isSelected ? "border-indigo-500 bg-indigo-50" : "border-slate-200 bg-white hover:border-slate-300";
          if (showFeedback) {
            if (opt.letter === result!.correct_option) tone = "border-green-500 bg-green-50";
            else if (isSelected) tone = "border-red-400 bg-red-50";
            else tone = "border-slate-200 bg-white opacity-70";
          }
          return (
            <label key={opt.letter} className={`flex cursor-pointer gap-3 rounded-md border p-3 ${tone}`}>
              <input
                type="radio"
                name={`q-${question.id}`}
                value={opt.letter}
                checked={isSelected}
                disabled={locked}
                onChange={() => setSelected(opt.letter as Letter)}
                className="mt-1"
              />
              {trueFalse ? null : <span className="font-semibold text-slate-700">{opt.letter}</span>}
              <Markdown className="flex-1">{opt.text_md}</Markdown>
            </label>
          );
        })}
      </fieldset>

      {error ? <Alert>{error}</Alert> : null}

      {showFeedback ? (
        <div className="space-y-2">
          <Alert kind={result!.is_correct ? "success" : "error"}>
            {result!.is_correct
              ? "Você acertou!"
              : trueFalse
                ? `Resposta errada. O gabarito é ${result!.correct_option === "C" ? "Certo" : "Errado"}.`
                : `Resposta errada. A alternativa correta é a ${result!.correct_option}.`}
          </Alert>
          {result!.explanation_md ? (
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <h3 className="mb-1 font-medium">Resolução</h3>
              <Markdown>{result!.explanation_md}</Markdown>
            </div>
          ) : null}
        </div>
      ) : null}

      {!locked ? (
        <Button onClick={submit} disabled={!selected || busy || unchanged}>
          {busy
            ? "Enviando..."
            : unchanged
              ? "Resposta registrada"
              : hideFeedback && registered
                ? "Trocar resposta"
                : "Responder"}
        </Button>
      ) : null}
    </article>
  );
}
