"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { QuestionView } from "@/components/questions/question-view";
import { Alert, Spinner } from "@/components/ui";
import { api, errorMessage, type Question } from "@/lib/api";

export function QuestionPage() {
  const { id } = useParams<{ id: string }>();
  const [question, setQuestion] = useState<Question | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .GET("/api/v1/questions/{question_id}", { params: { path: { question_id: Number(id) } } })
      .then(({ data, error: apiError }) => {
        if (data) setQuestion(data);
        else setError(errorMessage(apiError));
      });
  }, [id]);

  return (
    <div className="max-w-3xl space-y-4">
      <Link href="/questoes" className="text-sm text-indigo-700 hover:underline">
        ← Questões
      </Link>
      {error ? <Alert>{error}</Alert> : !question ? <Spinner /> : <QuestionView key={question.id} question={question} />}
    </div>
  );
}
