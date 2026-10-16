"use client";

import { AlertTriangle, Crop, Pencil, RotateCcw, Send, Trash2, Undo2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { AdminHeader, StatusBadge } from "@/components/admin/kit";
import { Alert, Button, Spinner } from "@/components/ui";
import { CONTEST_STATUS, type ContestExamDetail, type ContestQuestion } from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";

type Rect = { x: number; y: number; width: number; height: number };

export function ContestReview() {
  const { id } = useParams<{ id: string }>();
  const examId = Number(id);
  const router = useRouter();
  const [exam, setExam] = useState<ContestExamDetail | null>(null);
  const [selected, setSelected] = useState<ContestQuestion | null>(null);
  const [page, setPage] = useState(1);
  const [cropping, setCropping] = useState(false);
  const [filter, setFilter] = useState<"all" | "warnings">("all");
  const [message, setMessage] = useState<{ kind: "error" | "success"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const { data, error } = await api.GET("/api/v1/admin/contests/{exam_id}", { params: { path: { exam_id: examId } } });
    if (data) setExam(data);
    else setMessage({ kind: "error", text: errorMessage(error) });
  }, [examId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial
    void load();
  }, [load]);

  useEffect(() => {
    if (exam?.status !== "processing") return;
    const t = setInterval(() => void load(), 4000);
    return () => clearInterval(t);
  }, [exam?.status, load]);

  async function action(kind: "publish" | "unpublish" | "retry") {
    setBusy(true);
    setMessage(null);
    const path = `/api/v1/admin/contests/{exam_id}/${kind}` as const;
    const { error } = await api.POST(path, { params: { path: { exam_id: examId } } });
    setBusy(false);
    if (error) setMessage({ kind: "error", text: errorMessage(error) });
    else
      setMessage({
        kind: "success",
        text: { publish: "Prova publicada: os alunos já veem as questões.", unpublish: "Prova voltou para revisão.", retry: "Leitura reiniciada." }[kind],
      });
    await load();
  }

  async function remove() {
    if (!window.confirm("Excluir a prova e todas as questões dela? Isso não pode ser desfeito.")) return;
    setBusy(true);
    await api.DELETE("/api/v1/admin/contests/{exam_id}", { params: { path: { exam_id: examId } } });
    router.push("/admin/concursos");
  }

  async function saveFigure(rect: Rect) {
    if (!selected) return;
    const { error } = await api.POST("/api/v1/admin/contests/{exam_id}/questions/{question_id}/figure", {
      params: { path: { exam_id: examId, question_id: selected.id } },
      body: { page, ...rect, alt: "Figura da questão" },
    });
    setCropping(false);
    if (error) setMessage({ kind: "error", text: errorMessage(error) });
    else setMessage({ kind: "success", text: `Figura adicionada à questão ${selected.position}.` });
    await load();
  }

  if (!exam) return message ? <Alert>{message.text}</Alert> : <Spinner />;
  const status = CONTEST_STATUS[exam.status];
  const questions = exam.questions_list.filter((q) => filter === "all" || q.warnings.length);
  const pageUrl = exam.page_urls[page - 1];

  return (
    <div className="space-y-5">
      <Link href="/admin/concursos" className="text-sm text-indigo-700 hover:underline">
        ← Concursos
      </Link>
      <AdminHeader
        title={`${exam.board} · ${exam.organization}`}
        description={`${exam.position} · ${exam.year}${exam.booklet ? ` · caderno ${exam.booklet}` : ""} · ${exam.page_count ?? "?"} páginas`}
        actions={
          <>
            <StatusBadge level={status.level}>{status.label}</StatusBadge>
            {exam.status === "review" ? (
              <Button onClick={() => void action("publish")} disabled={busy}>
                <Send aria-hidden className="mr-2 h-4 w-4" />
                Publicar prova
              </Button>
            ) : null}
            {exam.status === "published" ? (
              <Button variant="secondary" onClick={() => void action("unpublish")} disabled={busy}>
                <Undo2 aria-hidden className="mr-2 h-4 w-4" />
                Despublicar
              </Button>
            ) : null}
            {exam.status === "failed" ? (
              <Button variant="secondary" onClick={() => void action("retry")} disabled={busy}>
                <RotateCcw aria-hidden className="mr-2 h-4 w-4" />
                Tentar de novo
              </Button>
            ) : null}
            <Button variant="ghost" className="text-red-700" onClick={() => void remove()} disabled={busy}>
              <Trash2 aria-hidden className="mr-2 h-4 w-4" />
              Excluir
            </Button>
          </>
        }
      />
      {message ? <Alert kind={message.kind}>{message.text}</Alert> : null}
      {exam.status === "processing" ? (
        <Alert kind="info">A IA está lendo o PDF. Esta página atualiza sozinha.</Alert>
      ) : null}
      {exam.error ? <Alert>{exam.error}</Alert> : null}

      {exam.status !== "processing" && exam.questions_list.length ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-slate-600">
                {exam.questions} questões · {exam.warnings} com aviso
              </p>
              <div role="group" aria-label="Filtro" className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 text-sm">
                {(["all", "warnings"] as const).map((f) => (
                  <button
                    key={f}
                    type="button"
                    aria-pressed={filter === f}
                    onClick={() => setFilter(f)}
                    className={`rounded-md px-3 py-1 ${filter === f ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}
                  >
                    {f === "all" ? "Todas" : "Com aviso"}
                  </button>
                ))}
              </div>
            </div>
            <ul className="space-y-2">
              {questions.map((q) => (
                <li key={q.id}>
                  <div
                    className={`rounded-lg border bg-white p-3 ${selected?.id === q.id ? "border-indigo-400 ring-1 ring-indigo-400" : "border-slate-200"}`}
                  >
                    <button
                      type="button"
                      className="w-full text-left"
                      onClick={() => {
                        setSelected(q);
                        if (q.page) setPage(q.page);
                        setCropping(false);
                      }}
                    >
                      <p className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                        <span className="font-semibold text-slate-900">Questão {q.position}</span>
                        <span>{q.format === "true_false" ? "Certo ou errado" : `${q.options} alternativas`}</span>
                        <span>· {q.subject_name ?? "sem disciplina"}</span>
                        <span>
                          · gabarito{" "}
                          <strong className="text-slate-800">
                            {q.is_annulled ? "anulada" : q.correct_option ? (q.format === "true_false" ? (q.correct_option === "C" ? "Certo" : "Errado") : q.correct_option) : "—"}
                          </strong>
                        </span>
                        {q.page ? <span>· pág. {q.page}</span> : null}
                        {q.assets ? <span>· {q.assets} figura(s)</span> : null}
                      </p>
                      <p className="mt-1 line-clamp-3 text-sm text-slate-800">{q.preview}</p>
                    </button>
                    {q.warnings.length ? (
                      <ul className="mt-2 space-y-1">
                        {q.warnings.map((w) => (
                          <li key={w} className="flex items-start gap-1.5 text-xs text-amber-800">
                            <AlertTriangle aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                            {w}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    <div className="mt-2 flex gap-3 text-sm">
                      <Link
                        href={`/admin/questoes/${q.id}?voltar=${encodeURIComponent(`/admin/concursos/${examId}`)}`}
                        className="inline-flex items-center gap-1 text-indigo-700 hover:underline"
                      >
                        <Pencil aria-hidden className="h-3.5 w-3.5" /> Editar
                      </Link>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 text-indigo-700 hover:underline"
                        onClick={() => {
                          setSelected(q);
                          if (q.page) setPage(q.page);
                          setCropping(true);
                        }}
                      >
                        <Crop aria-hidden className="h-3.5 w-3.5" /> Recortar figura
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="min-w-0 xl:sticky xl:top-4 xl:self-start">
            <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">
                <div className="flex items-center gap-2">
                  <Button variant="secondary" className="px-2 py-1" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Página anterior">
                    ‹
                  </Button>
                  <span className="tabular-nums">
                    Página {page} de {exam.page_urls.length}
                  </span>
                  <Button variant="secondary" className="px-2 py-1" disabled={page >= exam.page_urls.length} onClick={() => setPage(page + 1)} aria-label="Próxima página">
                    ›
                  </Button>
                </div>
                {cropping && selected ? (
                  <span className="text-indigo-700">Arraste sobre a figura da questão {selected.position}</span>
                ) : null}
              </div>
              {pageUrl ? (
                <PageImage key={pageUrl} src={pageUrl} cropping={cropping} onCrop={saveFigure} onCancel={() => setCropping(false)} />
              ) : null}
            </div>
          </div>
        </div>
      ) : exam.status !== "processing" ? (
        <Alert kind="warning">Nenhuma questão foi encontrada neste PDF.</Alert>
      ) : null}
    </div>
  );
}

/** Imagem da página; no modo recorte, arrastar desenha a área (coordenadas de 0 a 1). */
function PageImage({
  src,
  cropping,
  onCrop,
  onCancel,
}: {
  src: string;
  cropping: boolean;
  onCrop: (rect: Rect) => void;
  onCancel: () => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [start, setStart] = useState<{ x: number; y: number } | null>(null);
  const [rect, setRect] = useState<Rect | null>(null);

  function point(e: React.PointerEvent) {
    const r = box.current!.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
      y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)),
    };
  }

  return (
    <div className="space-y-2">
      <div
        ref={box}
        className={`relative select-none overflow-hidden rounded border border-slate-200 ${cropping ? "cursor-crosshair touch-none" : ""}`}
        onPointerDown={(e) => {
          if (!cropping) return;
          (e.target as HTMLElement).setPointerCapture(e.pointerId);
          const p = point(e);
          setStart(p);
          setRect({ x: p.x, y: p.y, width: 0, height: 0 });
        }}
        onPointerMove={(e) => {
          if (!cropping || !start) return;
          const p = point(e);
          setRect({ x: Math.min(start.x, p.x), y: Math.min(start.y, p.y), width: Math.abs(p.x - start.x), height: Math.abs(p.y - start.y) });
        }}
        onPointerUp={() => setStart(null)}
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- URL assinada do storage */}
        <img src={src} alt="Página da prova" className="block w-full" draggable={false} />
        {cropping && rect ? (
          <div
            className="pointer-events-none absolute border-2 border-indigo-600 bg-indigo-500/15"
            style={{ left: `${rect.x * 100}%`, top: `${rect.y * 100}%`, width: `${rect.width * 100}%`, height: `${rect.height * 100}%` }}
          />
        ) : null}
      </div>
      {cropping ? (
        <div className="flex gap-2">
          <Button disabled={!rect || rect.width < 0.02 || rect.height < 0.02} onClick={() => rect && onCrop(rect)}>
            Usar esta área
          </Button>
          <Button variant="secondary" onClick={onCancel}>
            Cancelar
          </Button>
        </div>
      ) : null}
    </div>
  );
}
