"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/essays/status-badge";
import { Alert, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { useAuth } from "@/lib/auth";
import { WEEKDAYS, toHHMM, toMin } from "@/lib/planner";

type DashboardData = components["schemas"]["DashboardOut"];

function Tile({ title, children, href, cta }: { title: string; children: React.ReactNode; href: string; cta: string }) {
  return (
    <section className="flex flex-col rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="mb-3 text-sm font-medium text-slate-500">{title}</h2>
      <div className="flex-1">{children}</div>
      <Link href={href} className="mt-4 text-sm font-medium text-indigo-700 hover:underline">
        {cta} →
      </Link>
    </section>
  );
}

export function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.GET("/api/v1/dashboard").then(({ data: d, error: e }) => {
      if (d) setData(d);
      else setError(errorMessage(e));
    });
  }, []);

  if (error) return <Alert>{error}</Alert>;
  if (!data) return <Spinner />;

  const firstName = user?.name.split(" ")[0] ?? "";
  const weekday = WEEKDAYS[data.weekday - 1].long.toLowerCase();

  return (
    <div className="max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Olá, {firstName}!</h1>
        <p className="text-slate-600">
          {data.streak_days > 0
            ? `Você está há ${data.streak_days} dia${data.streak_days > 1 ? "s" : ""} seguido${data.streak_days > 1 ? "s" : ""} estudando${data.studied_today ? "" : ". Estude hoje para não perder a sequência"}.`
            : "Que tal começar uma sequência de estudos hoje?"}
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        <Tile title={`Hoje (${weekday})`} href="/cronograma" cta="Abrir cronograma">
          {data.today_blocks.length === 0 ? (
            <p className="text-sm text-slate-600">Nenhum bloco de estudo hoje.</p>
          ) : (
            <ul className="space-y-2">
              {data.today_blocks.map((b) => (
                <li key={b.id} className={`flex items-center gap-2 text-sm ${b.id === data.next_block_id ? "font-medium text-slate-900" : "text-slate-600"}`}>
                  <span className="h-6 w-1 rounded-full" style={{ backgroundColor: b.color }} aria-hidden />
                  <span className="tabular-nums">
                    {toHHMM(toMin(b.start_time))}–{toHHMM(toMin(b.end_time))}
                  </span>
                  <span className="truncate">{b.subject_name ?? b.title ?? "Estudo"}</span>
                  {b.id === data.next_block_id ? <span className="ml-auto text-xs text-indigo-700">próximo</span> : null}
                </li>
              ))}
            </ul>
          )}
        </Tile>

        <Tile title="Última redação" href={data.last_essay ? `/redacoes/${data.last_essay.id}` : "/redacoes/nova"} cta={data.last_essay ? "Ver redação" : "Enviar redação"}>
          {data.last_essay ? (
            <div className="space-y-2">
              <p className="line-clamp-2 text-sm text-slate-800">{data.last_essay.theme_title}</p>
              <div className="flex items-center gap-3">
                {data.last_essay.total !== null && data.last_essay.total !== undefined ? (
                  <span className="text-3xl font-semibold tabular-nums">{data.last_essay.total}</span>
                ) : null}
                <StatusBadge status={data.last_essay.status as never} />
              </div>
              <p className="text-xs text-slate-500">{data.essays_graded} redação(ões) corrigida(s) no total</p>
            </div>
          ) : (
            <p className="text-sm text-slate-600">Você ainda não enviou redações.</p>
          )}
        </Tile>

        <Tile title="Questões nesta semana" href="/questoes?status=nao_respondidas" cta="Praticar">
          {data.week_accuracy.answered ? (
            <div>
              <p className="text-3xl font-semibold tabular-nums">{data.week_accuracy.pct}%</p>
              <p className="text-sm text-slate-600">
                {data.week_accuracy.correct} de {data.week_accuracy.answered} certas
              </p>
            </div>
          ) : (
            <p className="text-sm text-slate-600">Nenhuma questão respondida nesta semana.</p>
          )}
        </Tile>
      </div>
    </div>
  );
}
