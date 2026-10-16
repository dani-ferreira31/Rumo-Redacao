"use client";

import { FileDown } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { EssayResultView } from "@/components/essays/essay-result";
import { StatusBadge } from "@/components/essays/status-badge";
import { TranscriptionReview } from "@/components/essays/transcription-review";
import { Alert, Button, Spinner } from "@/components/ui";
import { api, errorMessage, type Essay } from "@/lib/api";
import { PROCESSING_STATUSES, formatDate } from "@/lib/essays";

const POLL_MS = 3000;

const PROCESSING_TEXT: Record<string, string> = {
  uploaded: "Recebemos sua foto. A transcrição começa em instantes.",
  transcribing: "Lendo a sua letra e transcrevendo o texto. Isso leva cerca de 1 minuto.",
  grading: "Corrigindo nas 5 competências. Isso pode levar 1 a 2 minutos; avisaremos por e-mail.",
};

export function EssayDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [essay, setEssay] = useState<Essay | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () =>
      api
        .GET("/api/v1/essays/{essay_id}", { params: { path: { essay_id: id } } })
        .then(({ data, error: apiError }) => {
          if (data) setEssay(data);
          else setError(errorMessage(apiError));
        }),
    [id],
  );

  useEffect(() => {
    load();
  }, [load]);

  // Consulta de novo enquanto o worker estiver processando.
  const processing = essay ? PROCESSING_STATUSES.includes(essay.status) : false;
  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(() => load(), POLL_MS);
    return () => clearInterval(timer);
  }, [processing, load]);

  async function retry() {
    setBusy(true);
    const { data, error: apiError } = await api.POST("/api/v1/essays/{essay_id}/retry", {
      params: { path: { essay_id: id } },
    });
    setBusy(false);
    if (data) setEssay(data);
    else setError(errorMessage(apiError));
  }

  async function remove() {
    setBusy(true);
    const { response, error: apiError } = await api.DELETE("/api/v1/essays/{essay_id}", {
      params: { path: { essay_id: id } },
    });
    setBusy(false);
    if (response.ok) router.replace("/redacoes");
    else setError(errorMessage(apiError));
  }

  if (error && !essay) return <Alert>{error}</Alert>;
  if (!essay) return <Spinner />;

  return (
    <div className="max-w-6xl space-y-6">
      <div>
        <Link href="/redacoes" className="text-sm text-indigo-700 hover:underline">
          ← Redações
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-slate-900">{essay.theme_title}</h1>
          <StatusBadge status={essay.status} />
        </div>
        <p className="text-sm text-slate-500">
          Enviada em {formatDate(essay.created_at)} ·{" "}
          {essay.input_type === "photo" ? "foto" : "texto digitado"}
          {essay.line_count ? ` · ${essay.line_count} linhas` : ""}
        </p>
      </div>

      {error ? <Alert>{error}</Alert> : null}

      {processing ? (
        <div className="rounded-lg border border-slate-200 bg-white p-6">
          <Spinner label={PROCESSING_TEXT[essay.status]} />
        </div>
      ) : null}

      {essay.status === "awaiting_review" ? (
        <TranscriptionReview essay={essay} onChange={setEssay} />
      ) : null}

      {essay.status === "failed" ? (
        <div className="space-y-3">
          <Alert>{essay.error_message ?? "Algo deu errado no processamento."}</Alert>
          <Button onClick={retry} disabled={busy}>
            {busy ? "Reenviando..." : "Tentar de novo"}
          </Button>
        </div>
      ) : null}

      {essay.status === "graded" && essay.result ? (
        <>
          <div>
            <a
              href={`/imprimir/redacao/${essay.id}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
            >
              <FileDown aria-hidden className="h-4 w-4" />
              Exportar devolutiva em PDF
            </a>
          </div>
          <EssayResultView result={essay.result} />
        </>
      ) : null}

      {essay.status === "graded" && essay.transcription_text ? (
        <details className="rounded-lg border border-slate-200 bg-white p-4">
          <summary className="cursor-pointer font-medium">Texto avaliado</summary>
          <pre className="mt-3 whitespace-pre-wrap font-serif text-slate-800">{essay.transcription_text}</pre>
        </details>
      ) : null}

      <div className="border-t border-slate-200 pt-4">
        {confirmDelete ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-slate-700">Excluir esta redação e as fotos?</span>
            <Button variant="danger" onClick={remove} disabled={busy}>
              Sim, excluir
            </Button>
            <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
              Cancelar
            </Button>
          </div>
        ) : (
          <Button variant="ghost" onClick={() => setConfirmDelete(true)} className="text-red-700">
            Excluir redação
          </Button>
        )}
      </div>
    </div>
  );
}
