"use client";

import { ClipboardList, PenLine } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState, StatusBadge } from "@/components/admin/kit";
import { CopyButton } from "@/components/copy-button";
import { PageHeader } from "@/components/page-header";
import { Alert, Spinner } from "@/components/ui";
import { dateTime } from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";
import type { AssessmentSummary } from "@/lib/assessments";

export function TeacherHome() {
  const [items, setItems] = useState<AssessmentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.GET("/api/v1/teacher/assessments").then(({ data, error: e }) => {
      if (data) setItems(data);
      else setError(errorMessage(e));
    });
  }, []);

  return (
    <div className="max-w-5xl space-y-6">
      <PageHeader
        title="Área do professor"
        description="Corrija as redações das suas turmas e monte provas com as questões do banco."
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <Link
          href="/redacoes/nova"
          className="flex gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm hover:border-indigo-300"
        >
          <PenLine aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-indigo-600" />
          <span>
            <span className="block font-medium text-slate-900">Corrigir uma redação</span>
            <span className="block text-sm text-slate-600">
              Envie a foto da folha. Depois de corrigida, exporte a devolutiva em PDF para entregar ao aluno.
            </span>
          </span>
        </Link>
        <Link
          href="/professor/provas/nova"
          className="flex gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm hover:border-indigo-300"
        >
          <ClipboardList aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-indigo-600" />
          <span>
            <span className="block font-medium text-slate-900">Montar uma prova</span>
            <span className="block text-sm text-slate-600">
              Escolha as questões, mande o link para a turma ou imprima.
            </span>
          </span>
        </Link>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-900">Minhas provas</h2>
        {error ? <Alert>{error}</Alert> : null}
        {!items ? (
          <Spinner />
        ) : items.length === 0 ? (
          <EmptyState>Nenhuma prova ainda. Comece em “Montar uma prova”.</EmptyState>
        ) : (
          <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
            {items.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <Link href={`/professor/provas/${a.id}`} className="font-medium text-indigo-700 hover:underline">
                    {a.title}
                  </Link>
                  <p className="text-xs text-slate-500">
                    {a.question_count} questões · {a.finished} entregue(s) de {a.attempts} aluno(s) · criada em{" "}
                    {dateTime(a.created_at)}
                  </p>
                </div>
                <StatusBadge level={a.is_open ? "ok" : "warning"}>{a.is_open ? "Aberta" : "Fechada"}</StatusBadge>
                <CopyButton text={a.url} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
