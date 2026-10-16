"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert, Spinner } from "@/components/ui";
import { api, errorMessage, type QuestionItem } from "@/lib/api";
import { AREA_LABEL } from "@/lib/questions";

export function ReviewQueue() {
  const router = useRouter();
  const params = useSearchParams();
  const reviewed = params.get("reviewed") ?? "false";
  const [items, setItems] = useState<QuestionItem[] | null>(null);
  const [total, setTotal] = useState(0);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const query = reviewed === "all" ? {} : { reviewed: reviewed === "true" };
    api.GET("/api/v1/admin/questions", { params: { query: { ...query, limit: 50 } } }).then(({ data, error: e }) => {
      if (!data) return setError(errorMessage(e));
      setItems(data.items);
      setTotal(data.total);
      setCursor(data.next_cursor ?? null);
    });
  }, [reviewed]);

  async function loadMore() {
    if (!cursor) return;
    const query = reviewed === "all" ? {} : { reviewed: reviewed === "true" };
    const { data } = await api.GET("/api/v1/admin/questions", { params: { query: { ...query, limit: 50, cursor } } });
    if (data) {
      setItems((prev) => [...(prev ?? []), ...data.items]);
      setCursor(data.next_cursor ?? null);
    }
  }

  return (
    <div className="max-w-5xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Revisão de questões</h1>
        <select
          aria-label="Situação da revisão"
          value={reviewed}
          onChange={(e) => {
            setItems(null);
            router.replace(`/admin/questoes?reviewed=${e.target.value}`);
          }}
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="false">Não revisadas</option>
          <option value="true">Revisadas</option>
          <option value="all">Todas</option>
        </select>
      </div>
      {error ? <Alert>{error}</Alert> : null}
      {!items ? (
        <Spinner />
      ) : (
        <>
          <p className="text-sm text-slate-600">{total} questão(ões)</p>
          <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
            {items.map((q) => (
              <li key={q.id}>
                <Link href={`/admin/questoes/${q.id}`} className="block px-4 py-3 hover:bg-slate-50">
                  <p className="text-xs text-slate-500">
                    #{q.id} · {AREA_LABEL[q.area_code]} · ENEM {q.year}
                    {q.subject ? ` · ${q.subject.name}` : " · sem disciplina"}
                    {q.skill_code ? ` · H${q.skill_code}` : ""}
                  </p>
                  <p className="line-clamp-2 text-slate-800">{q.preview}</p>
                </Link>
              </li>
            ))}
          </ul>
          {cursor ? (
            <button type="button" onClick={loadMore} className="text-sm text-indigo-700 hover:underline">
              Carregar mais
            </button>
          ) : null}
        </>
      )}
    </div>
  );
}
