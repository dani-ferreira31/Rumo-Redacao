"use client";

import { RefreshCw, RotateCcw, Ban } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AdminHeader, EmptyState, Section, StatusBadge } from "@/components/admin/kit";
import { Alert, Button, Spinner } from "@/components/ui";
import {
  type HealthReport,
  JOB_STATUS_LABEL,
  type JobsReport,
  QUEUE_LABEL,
  dateTime,
  fmtInt,
  relativeTime,
} from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";

const FILTERS = [
  { id: "", label: "Abertos" },
  { id: "failed", label: "Com falha" },
  { id: "running", label: "Rodando" },
  { id: "pending", label: "Na fila" },
  { id: "cancelled", label: "Cancelados" },
  { id: "done", label: "Concluídos" },
] as const;

type Filter = (typeof FILTERS)[number]["id"];

export function SystemPanel() {
  const [health, setHealth] = useState<HealthReport | null>(null);
  const [jobs, setJobs] = useState<JobsReport | null>(null);
  const [filter, setFilter] = useState<Filter>("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    const [h, j] = await Promise.all([
      api.GET("/api/v1/admin/system/health"),
      api.GET("/api/v1/admin/jobs", { params: { query: filter ? { status: filter, limit: 100 } : { limit: 100 } } }),
    ]);
    if (h.data) setHealth(h.data);
    if (j.data) setJobs(j.data);
    setError(h.error || j.error ? errorMessage(h.error ?? j.error) : null);
  }, [filter]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial e ao trocar o filtro
    void load();
  }, [load]);

  async function act(id: number, action: "retry" | "cancel") {
    setBusy(id);
    const { error: e } = await api.POST(`/api/v1/admin/jobs/{job_id}/${action}`, {
      params: { path: { job_id: id } },
    });
    setBusy(null);
    if (e) setError(errorMessage(e));
    await load();
  }

  return (
    <div className="space-y-6">
      <AdminHeader
        title="Sistema"
        description="Saúde dos serviços e fila de trabalhos (transcrições, correções, e-mails)."
        actions={
          <Button variant="secondary" onClick={() => void load()}>
            <RefreshCw aria-hidden className="mr-2 h-4 w-4" />
            Atualizar
          </Button>
        }
      />
      {error ? <Alert>{error}</Alert> : null}

      <Section title="Saúde">
        {!health ? (
          <Spinner />
        ) : (
          <>
            <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {health.checks.map((c) => (
                <li key={c.name} className="rounded-lg border border-slate-200 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-slate-900">{c.name}</span>
                    <StatusBadge level={c.level} />
                  </div>
                  <p className="mt-1 text-sm text-slate-600">{c.detail}</p>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-sm text-slate-500">
              Worker visto {relativeTime(health.worker_last_seen)}
              {health.disk_free_gb !== null && health.disk_free_gb !== undefined
                ? ` · disco: ${health.disk_free_gb} GB livres de ${health.disk_total_gb} GB`
                : ""}
            </p>
          </>
        )}
      </Section>

      <Section title="Fila por tipo">
        {!jobs ? (
          <Spinner />
        ) : jobs.counts.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                  <th className="py-2 pr-3 font-medium">Tipo</th>
                  {(["pending", "running", "done", "failed", "cancelled"] as const).map((s) => (
                    <th key={s} className="py-2 pr-3 text-right font-medium">
                      {JOB_STATUS_LABEL[s]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {jobs.counts.map((c) => (
                  <tr key={c.queue} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 pr-3">{QUEUE_LABEL[c.queue] ?? c.queue}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{fmtInt(c.pending)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{fmtInt(c.running)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums text-slate-500">{fmtInt(c.done)}</td>
                    <td className={`py-2 pr-3 text-right tabular-nums ${c.failed ? "font-semibold text-red-700" : ""}`}>
                      {fmtInt(c.failed)}
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums text-slate-500">{fmtInt(c.cancelled)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState>A fila ainda não recebeu trabalhos.</EmptyState>
        )}
      </Section>

      <Section
        title="Trabalhos"
        description="O conteúdo de cada trabalho fica oculto; e-mails nas mensagens de erro aparecem mascarados."
        actions={
          <select
            aria-label="Filtrar trabalhos"
            value={filter}
            onChange={(e) => setFilter(e.target.value as Filter)}
            className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
          >
            {FILTERS.map((f) => (
              <option key={f.id} value={f.id}>
                {f.label}
              </option>
            ))}
          </select>
        }
      >
        {!jobs ? (
          <Spinner />
        ) : jobs.jobs.length ? (
          <ul className="divide-y divide-slate-100">
            {jobs.jobs.map((j) => (
              <li key={j.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="font-medium text-slate-900">{QUEUE_LABEL[j.queue] ?? j.queue}</span>
                    <span className="text-xs text-slate-400">#{j.id}</span>
                    <StatusBadge level={j.status === "failed" ? "error" : j.status === "cancelled" ? "warning" : "ok"}>
                      {JOB_STATUS_LABEL[j.status] ?? j.status}
                    </StatusBadge>
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Tentativas {j.attempts}/{j.max_attempts} · criado {dateTime(j.created_at)} · atualizado{" "}
                    {relativeTime(j.updated_at)}
                  </p>
                  {j.last_error ? (
                    <p className="mt-1 break-words rounded bg-slate-50 px-2 py-1 font-mono text-xs text-slate-700">{j.last_error}</p>
                  ) : null}
                </div>
                <div className="flex gap-2">
                  {j.status === "failed" || j.status === "cancelled" ? (
                    <Button variant="secondary" className="px-3 py-1.5" disabled={busy === j.id} onClick={() => void act(j.id, "retry")}>
                      <RotateCcw aria-hidden className="mr-1.5 h-4 w-4" />
                      Reprocessar
                    </Button>
                  ) : null}
                  {j.status === "failed" || j.status === "pending" ? (
                    <Button variant="ghost" className="px-3 py-1.5 text-red-700" disabled={busy === j.id} onClick={() => void act(j.id, "cancel")}>
                      <Ban aria-hidden className="mr-1.5 h-4 w-4" />
                      Cancelar
                    </Button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState>Nenhum trabalho com esse filtro.</EmptyState>
        )}
      </Section>
    </div>
  );
}
