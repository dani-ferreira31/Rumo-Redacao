"use client";

import { FileUp } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AdminHeader, EmptyState, Section, StatusBadge } from "@/components/admin/kit";
import { Alert, Button, Spinner, TextField } from "@/components/ui";
import { CONTEST_STATUS, type ContestEstimate, type ContestExam, dateTime, money } from "@/lib/admin";
import { api, apiFetch, errorMessage } from "@/lib/api";

const inputCls = "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm";

export function ContestsAdmin() {
  const [exams, setExams] = useState<ContestExam[] | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const { data, error: e } = await api.GET("/api/v1/admin/contests");
    if (data) setExams(data);
    else setError(errorMessage(e));
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial
    void load();
  }, [load]);

  // enquanto alguma prova está sendo lida, atualiza a lista
  const processing = exams?.some((e) => e.status === "processing");
  useEffect(() => {
    if (!processing) return;
    const t = setInterval(() => void load(), 4000);
    return () => clearInterval(t);
  }, [processing, load]);

  return (
    <div className="space-y-6">
      <AdminHeader
        title="Concursos"
        description="Importe o PDF de uma prova e o do gabarito oficial. A IA separa as questões; você revisa e publica."
        actions={
          !showForm ? (
            <Button onClick={() => setShowForm(true)}>
              <FileUp aria-hidden className="mr-2 h-4 w-4" />
              Importar prova
            </Button>
          ) : null
        }
      />
      {error ? <Alert>{error}</Alert> : null}
      {showForm ? (
        <ImportForm
          onCancel={() => setShowForm(false)}
          onDone={async () => {
            setShowForm(false);
            await load();
          }}
        />
      ) : null}

      <Section title="Provas importadas">
        {!exams ? (
          <Spinner />
        ) : exams.length ? (
          <ul className="divide-y divide-slate-100">
            {exams.map((e) => {
              const status = CONTEST_STATUS[e.status];
              return (
                <li key={e.id}>
                  <Link href={`/admin/concursos/${e.id}`} className="flex flex-wrap items-center justify-between gap-3 rounded-lg px-2 py-3 hover:bg-slate-50">
                    <div className="min-w-0">
                      <p className="font-medium text-slate-900">
                        {e.board} · {e.organization} · {e.position}
                      </p>
                      <p className="text-sm text-slate-500">
                        {e.year}
                        {e.level ? ` · nível ${e.level === "medio" ? "médio" : "superior"}` : ""} · {e.page_count ?? "?"} páginas ·{" "}
                        {e.questions} questões{e.has_answer_key ? "" : " · sem gabarito"} · importada {dateTime(e.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {e.warnings ? <StatusBadge level="warning">{e.warnings} com aviso</StatusBadge> : null}
                      <StatusBadge level={status.level}>{status.label}</StatusBadge>
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        ) : (
          <EmptyState>Nenhuma prova importada ainda.</EmptyState>
        )}
      </Section>
    </div>
  );
}

function ImportForm({ onCancel, onDone }: { onCancel: () => void; onDone: () => Promise<void> }) {
  const [meta, setMeta] = useState({ board: "", organization: "", position: "", level: "", year: String(new Date().getFullYear()), booklet: "" });
  const [examPdf, setExamPdf] = useState<File | null>(null);
  const [keyPdf, setKeyPdf] = useState<File | null>(null);
  const [estimate, setEstimate] = useState<ContestEstimate | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pickExam(file: File | null) {
    setExamPdf(file);
    setEstimate(null);
    setError(null);
    if (!file) return;
    const body = new FormData();
    body.append("exam_pdf", file);
    const res = await apiFetch("/api/v1/admin/contests/estimate", { method: "POST", body });
    const json = await res.json();
    if (res.ok) setEstimate(json);
    else setError(errorMessage(json));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!examPdf) return;
    setBusy(true);
    setError(null);
    const body = new FormData();
    for (const [k, v] of Object.entries(meta)) if (v) body.append(k, v);
    body.append("exam_pdf", examPdf);
    if (keyPdf) body.append("answer_key_pdf", keyPdf);
    const res = await apiFetch("/api/v1/admin/contests", { method: "POST", body });
    setBusy(false);
    if (res.ok) await onDone();
    else setError(errorMessage(await res.json()));
  }

  const field = (key: keyof typeof meta) => ({
    value: meta[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setMeta({ ...meta, [key]: e.target.value }),
  });

  return (
    <Section title="Importar prova" description="Use os PDFs oficiais da banca. A leitura roda em segundo plano e leva alguns minutos.">
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <TextField label="Banca" placeholder="Cebraspe, FGV, FCC..." required {...field("board")} />
          <TextField label="Órgão" placeholder="Polícia Federal, INSS..." required {...field("organization")} />
          <TextField label="Cargo" placeholder="Agente de Polícia" required {...field("position")} />
          <label className="text-sm">
            <span className="mb-1 block font-medium text-slate-700">Nível</span>
            <select className={inputCls} value={meta.level} onChange={(e) => setMeta({ ...meta, level: e.target.value })}>
              <option value="">Não informado</option>
              <option value="medio">Médio</option>
              <option value="superior">Superior</option>
            </select>
          </label>
          <TextField label="Ano" type="number" min={1990} max={2100} required {...field("year")} />
          <TextField label="Tipo/cor do caderno" placeholder="Opcional (ex.: Tipo 1, Branca)" hint="Para ler a coluna certa do gabarito." {...field("booklet")} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm">
            <span className="mb-1 block font-medium text-slate-700">PDF da prova</span>
            <input type="file" accept="application/pdf" required onChange={(e) => void pickExam(e.target.files?.[0] ?? null)} className="block w-full text-sm" />
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium text-slate-700">PDF do gabarito (opcional)</span>
            <input type="file" accept="application/pdf" onChange={(e) => setKeyPdf(e.target.files?.[0] ?? null)} className="block w-full text-sm" />
            <span className="mt-1 block text-slate-500">Sem gabarito, você informa as respostas na revisão.</span>
          </label>
        </div>
        {estimate ? (
          <Alert kind={estimate.budget_exceeded ? "error" : "info"}>
            {estimate.pages} páginas, lidas em {estimate.chunks} parte(s) por {estimate.provider}/{estimate.model}. Custo estimado:{" "}
            {estimate.estimated_cost_usd === null || estimate.estimated_cost_usd === undefined
              ? "desconhecido (cadastre o preço do modelo em Admin → IA)"
              : money(estimate.estimated_cost_usd)}
            {estimate.budget_left_usd !== null && estimate.budget_left_usd !== undefined ? ` · saldo do orçamento: ${money(estimate.budget_left_usd)}` : ""}
            {estimate.budget_exceeded ? ". O orçamento do mês acabou: a importação está bloqueada." : "."}
          </Alert>
        ) : null}
        {error ? <Alert>{error}</Alert> : null}
        <div className="flex gap-2">
          <Button type="submit" disabled={busy || !examPdf || estimate?.budget_exceeded}>
            {busy ? "Enviando..." : "Importar"}
          </Button>
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancelar
          </Button>
        </div>
      </form>
    </Section>
  );
}
