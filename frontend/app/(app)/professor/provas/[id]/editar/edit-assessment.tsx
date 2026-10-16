"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Alert, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { AssessmentDetail } from "@/lib/assessments";

import { AssessmentBuilder } from "../../../assessment-builder";

export function EditAssessment() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<AssessmentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.GET("/api/v1/teacher/assessments/{assessment_id}", { params: { path: { assessment_id: id } } }).then(({ data, error: e }) => {
      if (data) setDetail(data);
      else setError(errorMessage(e));
    });
  }, [id]);

  if (error) return <Alert>{error}</Alert>;
  if (!detail) return <Spinner />;
  return (
    <div className="max-w-7xl">
      <Link href={`/professor/provas/${id}`} className="text-sm text-indigo-700 hover:underline">
        ← Voltar à prova
      </Link>
      <PageHeader title="Editar prova" />
      {detail.attempts > 0 ? (
        <div className="mb-4">
          <Alert kind="warning">
            Alunos já abriram esta prova: dá para mudar o título e as instruções, mas não as questões.
          </Alert>
        </div>
      ) : null}
      <AssessmentBuilder initial={detail} />
    </div>
  );
}
