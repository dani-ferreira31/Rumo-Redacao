"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { EvolutionChart } from "@/components/essays/evolution-chart";
import { StatusBadge } from "@/components/essays/status-badge";
import { PageHeader } from "@/components/page-header";
import { Alert, Spinner } from "@/components/ui";
import { api, errorMessage, type EssayStats, type EssaySummary } from "@/lib/api";
import { COMPETENCY_NAMES, formatDate } from "@/lib/essays";

export function EssaysHome() {
  const [items, setItems] = useState<EssaySummary[] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [stats, setStats] = useState<EssayStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    Promise.all([api.GET("/api/v1/essays"), api.GET("/api/v1/essays/stats")]).then(
      ([list, st]) => {
        if (!list.data || !st.data) {
          setError(errorMessage(list.error ?? st.error));
          return;
        }
        setItems(list.data.items);
        setCursor(list.data.next_cursor ?? null);
        setStats(st.data);
      },
    );
  }, []);

  async function loadMore() {
    if (!cursor) return;
    setLoadingMore(true);
    const { data } = await api.GET("/api/v1/essays", { params: { query: { cursor } } });
    setLoadingMore(false);
    if (data) {
      setItems((prev) => [...(prev ?? []), ...data.items]);
      setCursor(data.next_cursor ?? null);
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader
          title="Redações"
          description="Envie a foto da sua redação e receba a correção nas 5 competências."
        />
        <Link
          href="/redacoes/nova"
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          Nova redação
        </Link>
      </div>

      {error ? <Alert>{error}</Alert> : null}
      {!items || !stats ? (
        error ? null : <Spinner />
      ) : (
        <>
          {stats.points.length > 0 ? (
            <section className="space-y-3">
              <EvolutionChart points={stats.points} />
              {stats.averages ? (
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-6">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <div key={n} className="rounded-lg border border-slate-200 bg-white p-3" title={COMPETENCY_NAMES[n]}>
                      <p className="text-xs text-slate-500">Média C{n}</p>
                      <p className="text-lg font-semibold tabular-nums text-slate-900">
                        {Math.round(stats.averages![`c${n}`])}
                      </p>
                    </div>
                  ))}
                  <div className="rounded-lg border border-slate-200 bg-white p-3">
                    <p className="text-xs text-slate-500">Média total</p>
                    <p className="text-lg font-semibold tabular-nums text-slate-900">
                      {Math.round(stats.averages.total)}
                    </p>
                  </div>
                </div>
              ) : null}
            </section>
          ) : null}

          {items.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
              <p className="text-slate-700">Você ainda não enviou nenhuma redação.</p>
              <Link href="/redacoes/nova" className="mt-2 inline-block text-indigo-700 hover:underline">
                Enviar a primeira
              </Link>
            </div>
          ) : (
            <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
              {items.map((e) => (
                <li key={e.id}>
                  <Link
                    href={`/redacoes/${e.id}`}
                    className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 hover:bg-slate-50"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-900">{e.theme_title}</p>
                      <p className="text-sm text-slate-500">
                        {formatDate(e.created_at)} · {e.input_type === "photo" ? "foto" : "texto digitado"}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      {e.total !== null && e.total !== undefined ? (
                        <span className="text-lg font-semibold tabular-nums text-slate-900">
                          {e.total}
                          {e.annulled ? <span className="ml-1 text-xs text-red-700">anulada</span> : null}
                        </span>
                      ) : null}
                      <StatusBadge status={e.status} />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {cursor ? (
            <button
              type="button"
              onClick={loadMore}
              disabled={loadingMore}
              className="text-sm text-indigo-700 hover:underline disabled:opacity-60"
            >
              {loadingMore ? "Carregando..." : "Carregar mais"}
            </button>
          ) : null}
        </>
      )}
    </div>
  );
}
