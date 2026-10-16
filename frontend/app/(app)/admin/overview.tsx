"use client";

import { AlertTriangle, BookOpenCheck, CircleDollarSign, PenLine, Users, XCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AdminHeader, BudgetBar, EmptyState, Section, StatCard } from "@/components/admin/kit";
import { BarChart, dayRange, shortDay } from "@/components/admin/bar-chart";
import { Alert, Spinner } from "@/components/ui";
import { type Overview, type SystemEvent, dateTime, fmtInt, money } from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";

export function AdminOverview() {
  const [data, setData] = useState<Overview | null>(null);
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.GET("/api/v1/admin/overview").then(({ data: d, error: e }) => (d ? setData(d) : setError(errorMessage(e))));
    api.GET("/api/v1/admin/events", { params: { query: { limit: 8 } } }).then(({ data: d }) => setEvents(d ?? []));
  }, []);

  if (error) return <Alert>{error}</Alert>;
  if (!data) return <Spinner />;

  const today = new Date();
  const start = new Date(today);
  start.setDate(today.getDate() - 29);
  const answers = new Map(data.answers_by_day.map((d) => [d.day, d.count]));
  const answerBars = dayRange(start, today).map((day) => ({
    key: day,
    label: shortDay(day),
    values: { answers: answers.get(day) ?? 0 },
  }));
  const signupBars = data.signups.map((w) => ({
    key: w.week,
    label: shortDay(w.week),
    values: { signups: w.count },
  }));
  const b = data.budget;

  return (
    <div className="space-y-6">
      <AdminHeader
        title="Visão geral"
        description="Números agregados da plataforma. Nenhum dado pessoal de aluno aparece no painel."
      />

      {data.alerts.length ? (
        <ul className="space-y-2">
          {data.alerts.map((a) => (
            <li
              key={a.message}
              className={`flex items-center gap-3 rounded-lg border px-4 py-3 text-sm ${
                a.level === "error" ? "border-red-200 bg-red-50 text-red-900" : "border-amber-200 bg-amber-50 text-amber-900"
              }`}
            >
              {a.level === "error" ? <XCircle aria-hidden className="h-4 w-4 shrink-0" /> : <AlertTriangle aria-hidden className="h-4 w-4 shrink-0" />}
              <span className="flex-1">{a.message}</span>
              {a.href ? (
                <Link href={a.href} className="font-medium underline-offset-2 hover:underline">
                  Ver
                </Link>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Alunos"
          icon={Users}
          value={fmtInt(data.students_total)}
          hint={`${fmtInt(data.active_7d)} ativos em 7 dias · ${fmtInt(data.active_30d)} em 30`}
        />
        <StatCard
          label="Redações (30 dias)"
          icon={PenLine}
          value={fmtInt(data.essays_submitted_30d)}
          hint={`${fmtInt(data.essays_graded_30d)} corrigidas${
            data.essays_failed_30d ? ` · ${fmtInt(data.essays_failed_30d)} com falha` : ""
          }${data.avg_grading_minutes !== null && data.avg_grading_minutes !== undefined ? ` · ${data.avg_grading_minutes} min em média` : ""}`}
          tone={data.essays_failed_30d ? "warning" : "default"}
        />
        <StatCard
          label="Questões respondidas (30 dias)"
          icon={BookOpenCheck}
          value={fmtInt(data.answers_30d)}
        />
        <StatCard
          label="Gasto com IA no mês"
          icon={CircleDollarSign}
          value={money(b.spent_usd)}
          tone={b.exceeded ? "error" : b.warning ? "warning" : "default"}
          hint={
            <span className="block space-y-1.5">
              <span className="block">
                {b.budget_usd ? `de ${money(b.budget_usd)} · ` : "sem teto · "}projeção {money(b.projected_usd)}
              </span>
              <BudgetBar pct={b.pct} />
            </span>
          }
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section title="Questões respondidas por dia" description="Últimos 30 dias">
          {data.answers_30d ? (
            <BarChart
              ariaLabel="Questões respondidas por dia"
              data={answerBars}
              series={[{ id: "answers", label: "Respostas", color: "#2a78d6" }]}
              format={(n) => fmtInt(Math.round(n))}
            />
          ) : (
            <EmptyState>Nenhuma questão respondida nos últimos 30 dias.</EmptyState>
          )}
        </Section>
        <Section title="Novos cadastros por semana" description="Últimas 8 semanas">
          {signupBars.length ? (
            <BarChart
              ariaLabel="Novos cadastros por semana"
              data={signupBars}
              series={[{ id: "signups", label: "Cadastros", color: "#2a78d6" }]}
              format={(n) => fmtInt(Math.round(n))}
            />
          ) : (
            <EmptyState>Nenhum cadastro nas últimas 8 semanas.</EmptyState>
          )}
        </Section>
      </div>

      <Section title="Atividade recente do painel" description="Mudanças de configuração e ações na fila">
        {events.length ? (
          <ul className="divide-y divide-slate-100 text-sm">
            {events.map((e) => (
              <li key={e.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
                <span className="text-slate-800">{e.message}</span>
                <span className="text-xs text-slate-500">{dateTime(e.created_at)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState>Nenhuma alteração registrada ainda.</EmptyState>
        )}
      </Section>
    </div>
  );
}
