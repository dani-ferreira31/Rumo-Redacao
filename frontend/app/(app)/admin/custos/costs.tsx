"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { BarChart, dayRange, shortDay } from "@/components/admin/bar-chart";
import { AdminHeader, BudgetBar, EmptyState, Section, StatCard } from "@/components/admin/kit";
import { Alert, Spinner } from "@/components/ui";
import { type CostReport, PERIODS, PURPOSES, type Period, fmtCompact, fmtInt, money, purposeOf } from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";

const PROVIDER_LABEL: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  google: "Google",
  fake: "Simulado",
};

export function CostsDashboard() {
  const [period, setPeriod] = useState<Period>("month");
  const [report, setReport] = useState<CostReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.GET("/api/v1/admin/costs", { params: { query: { period } } }).then(({ data, error: e }) => {
      if (data) {
        setReport(data);
        setError(null);
      } else setError(errorMessage(e));
    });
  }, [period]);

  const periodPicker = (
    <div role="group" aria-label="Período" className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5">
      {PERIODS.map((p) => (
        <button
          key={p.id}
          type="button"
          aria-pressed={period === p.id}
          onClick={() => setPeriod(p.id)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium ${
            period === p.id ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );

  return (
    <div className="space-y-6">
      <AdminHeader
        title="Custos de IA"
        description="Estimativa pela tabela de preços (Admin → IA). A cobrança oficial fica no console de cada provedor."
        actions={periodPicker}
      />
      {error ? <Alert>{error}</Alert> : null}
      {!report ? <Spinner /> : <Report report={report} />}
    </div>
  );
}

function Report({ report }: { report: CostReport }) {
  const end = new Date(new Date(report.end).getTime() - 1);
  const byDay = new Map<string, Record<string, number>>();
  for (const row of report.by_day) {
    const values = byDay.get(row.day) ?? {};
    const id = purposeOf(row.purpose).id;
    values[id] = (values[id] ?? 0) + row.cost_usd;
    byDay.set(row.day, values);
  }
  const bars = dayRange(new Date(report.start), end).map((day) => ({
    key: day,
    label: shortDay(day),
    values: byDay.get(day) ?? {},
  }));
  const essays = report.by_purpose.find((p) => p.purpose === "grading");
  const transcriptions = report.by_purpose.find((p) => p.purpose === "transcription");
  const contests = report.by_purpose.find((p) => p.purpose === "contest_extraction");
  const b = report.budget;

  return (
    <>
      {report.unknown_cost_calls ? (
        <Alert kind="warning">
          {fmtInt(report.unknown_cost_calls)} chamada(s) usaram modelos sem preço cadastrado e não entram no total.{" "}
          <Link href="/admin/ia#precos" className="font-medium underline">
            Cadastrar preços
          </Link>
        </Alert>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Total no período" value={money(report.total_cost_usd)} hint={`${fmtInt(report.total_calls)} chamadas`} />
        <StatCard
          label="Por redação corrigida"
          value={money(essays?.avg_cost_per_unit_usd)}
          hint={essays ? `${fmtInt(essays.units)} redações` : "nenhuma no período"}
        />
        <StatCard
          label="Por transcrição de foto"
          value={money(transcriptions?.avg_cost_per_unit_usd)}
          hint={
            transcriptions ? `${fmtInt(transcriptions.units)} fotos` : "nenhuma no período"
          }
        />
        <StatCard
          label="Por prova de concurso importada"
          value={money(contests?.avg_cost_per_unit_usd)}
          hint={contests ? `${fmtInt(contests.units)} provas` : "nenhuma no período"}
        />
        <StatCard
          label="Orçamento do mês"
          value={b.budget_usd ? money(b.budget_usd) : "Sem teto"}
          tone={b.exceeded ? "error" : b.warning ? "warning" : "default"}
          hint={
            <span className="block space-y-1.5">
              <span className="block">
                Gasto {money(b.spent_usd)}
                {b.pct !== null && b.pct !== undefined ? ` (${b.pct}%)` : ""} · projeção {money(b.projected_usd)}
              </span>
              <BudgetBar pct={b.pct} />
              <Link href="/admin/modulos" className="block text-indigo-700 hover:underline">
                Alterar orçamento
              </Link>
            </span>
          }
        />
      </div>

      <Section title="Gasto por dia" description="Empilhado por tarefa">
        {report.total_cost_usd > 0 ? (
          <BarChart
            ariaLabel="Gasto com IA por dia, por tarefa"
            data={bars}
            series={PURPOSES.map((p) => ({ id: p.id, label: p.label, color: p.color }))}
            format={money}
          />
        ) : (
          <EmptyState>Nenhum gasto no período.</EmptyState>
        )}
      </Section>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section title="Por tarefa">
          {report.by_purpose.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                    <th className="py-2 pr-3 font-medium">Tarefa</th>
                    <th className="py-2 pr-3 text-right font-medium">Chamadas</th>
                    <th className="py-2 pr-3 text-right font-medium">Custo</th>
                    <th className="py-2 text-right font-medium">Médio por unidade</th>
                  </tr>
                </thead>
                <tbody>
                  {report.by_purpose.map((p) => {
                    const meta = purposeOf(p.purpose);
                    return (
                      <tr key={p.purpose} className="border-b border-slate-100 last:border-0">
                        <td className="py-2 pr-3">
                          <span className="flex items-center gap-2">
                            <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: meta.color }} aria-hidden />
                            {meta.label}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums">{fmtInt(p.calls)}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{money(p.cost_usd)}</td>
                        <td className="py-2 text-right tabular-nums">{money(p.avg_cost_per_unit_usd)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState>Nenhuma chamada no período.</EmptyState>
          )}
        </Section>

        <Section title="Por provedor e modelo">
          {report.by_model.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                    <th className="py-2 pr-3 font-medium">Modelo</th>
                    <th className="py-2 pr-3 text-right font-medium">Chamadas</th>
                    <th className="py-2 pr-3 text-right font-medium">Tokens (entrada / saída / cache)</th>
                    <th className="py-2 text-right font-medium">Custo</th>
                  </tr>
                </thead>
                <tbody>
                  {report.by_model.map((m) => (
                    <tr key={`${m.provider}/${m.model}`} className="border-b border-slate-100 last:border-0">
                      <td className="py-2 pr-3">
                        <span className="block font-medium text-slate-900">{m.model}</span>
                        <span className="text-xs text-slate-500">{PROVIDER_LABEL[m.provider] ?? m.provider}</span>
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">{fmtInt(m.calls)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums text-slate-600">
                        {fmtCompact(m.input_tokens)} / {fmtCompact(m.output_tokens)} / {fmtCompact(m.cache_read_tokens)}
                      </td>
                      <td className="py-2 text-right tabular-nums">
                        {money(m.cost_usd)}
                        {m.unknown_cost_calls ? <span className="block text-xs text-amber-700">{m.unknown_cost_calls} sem preço</span> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState>Nenhuma chamada no período.</EmptyState>
          )}
        </Section>
      </div>
    </>
  );
}
