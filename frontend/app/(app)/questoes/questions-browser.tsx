"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { type ContestFilters, FiltersBar } from "@/components/questions/filters-bar";
import { Alert, Button, Spinner } from "@/components/ui";
import { api, errorMessage, type Area, type QuestionItem } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isEnabled, useFeatures } from "@/lib/features";
import {
  AREA_LABEL,
  DIFFICULTY_LABEL,
  FILTER_KEYS,
  type FilterState,
  filtersFromParams,
  toApiFilters,
} from "@/lib/questions";

export function QuestionsBrowser() {
  const router = useRouter();
  const params = useSearchParams();
  const filters = filtersFromParams(params);
  const filtersKey = params.toString();
  const features = useFeatures();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const enemOn = isAdmin || isEnabled(features, ["questions_enem"]);
  const contestOn = isAdmin || isEnabled(features, ["questions_concursos"]);
  // sem escolha explícita, abre na trilha que estiver ligada
  const track = filters.track === "concurso" || (!enemOn && contestOn) ? "concurso" : "enem";
  const effective: FilterState = { ...filters, track };
  const effectiveKey = `${filtersKey}|${track}`;

  const [areas, setAreas] = useState<Area[]>([]);
  const [contest, setContest] = useState<ContestFilters | null>(null);
  const [items, setItems] = useState<QuestionItem[] | null>(null);
  const [total, setTotal] = useState(0);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [listSize, setListSize] = useState(10);
  const [timer, setTimer] = useState(0);

  useEffect(() => {
    api.GET("/api/v1/catalog/areas").then(({ data }) => setAreas(data ?? []));
  }, []);

  useEffect(() => {
    if (track !== "concurso" || contest) return;
    api.GET("/api/v1/contests/filters").then(({ data }) => setContest(data ?? null));
  }, [track, contest]);

  useEffect(() => {
    const [query, t] = effectiveKey.split("|");
    const f = { ...filtersFromParams(new URLSearchParams(query)), track: t };
    api
      .GET("/api/v1/questions", { params: { query: { ...toApiFilters(f), limit: 20 } } })
      .then(({ data, error: apiError }) => {
        if (!data) {
          setError(errorMessage(apiError));
          return;
        }
        setError(null);
        setItems(data.items);
        setTotal(data.total);
        setCursor(data.next_cursor ?? null);
      });
  }, [effectiveKey]);

  function applyFilters(next: FilterState) {
    const sp = new URLSearchParams();
    for (const k of FILTER_KEYS) if (next[k]) sp.set(k, next[k]!);
    setItems(null);
    router.replace(`/questoes${sp.size ? `?${sp}` : ""}`);
  }

  async function loadMore() {
    if (!cursor) return;
    const { data } = await api.GET("/api/v1/questions", {
      params: { query: { ...toApiFilters(effective), limit: 20, cursor } },
    });
    if (data) {
      setItems((prev) => [...(prev ?? []), ...data.items]);
      setCursor(data.next_cursor ?? null);
    }
  }

  async function start(mode: "livre" | "lista" | "simulado") {
    setStarting(true);
    setError(null);
    const { data, error: apiError } = await api.POST("/api/v1/practice-sessions", {
      body: {
        mode,
        filters: toApiFilters(effective),
        size: mode === "livre" ? 20 : listSize,
        time_limit_seconds: mode === "simulado" && timer ? timer * 60 : undefined,
      },
    });
    setStarting(false);
    if (data) router.push(`/questoes/pratica/${data.id}`);
    else setError(errorMessage(apiError));
  }

  return (
    <div className="max-w-5xl space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader
          title="Questões"
          description={
            track === "concurso"
              ? "Questões de provas de concursos públicos, com gabarito oficial."
              : "Questões oficiais do ENEM de 2009 a 2023."
          }
        />
        <Link href="/questoes/estatisticas" className="text-sm text-indigo-700 hover:underline">
          Minhas estatísticas →
        </Link>
      </div>

      {enemOn && contestOn ? (
        <div role="tablist" aria-label="Banco de questões" className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5">
          {(["enem", "concurso"] as const).map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={track === t}
              onClick={() => applyFilters(t === "concurso" ? { track: "concurso" } : {})}
              className={`rounded-md px-4 py-1.5 text-sm font-medium ${
                track === t ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {t === "enem" ? "ENEM" : "Concursos"}
            </button>
          ))}
        </div>
      ) : null}

      <FiltersBar key={filtersKey} areas={areas} contest={contest} value={effective} onChange={applyFilters} />

      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-3">
        <Button onClick={() => start("livre")} disabled={starting || total === 0}>
          Praticar (correção na hora)
        </Button>
        <span className="text-sm text-slate-500">ou</span>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          Lista de
          <select value={listSize} onChange={(e) => setListSize(Number(e.target.value))} className="rounded-md border border-slate-300 px-2 py-1">
            {[5, 10, 20, 45].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          questões
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          cronômetro
          <select value={timer} onChange={(e) => setTimer(Number(e.target.value))} className="rounded-md border border-slate-300 px-2 py-1">
            <option value={0}>sem</option>
            {[15, 30, 60, 90, 180].map((m) => (
              <option key={m} value={m}>
                {m} min
              </option>
            ))}
          </select>
        </label>
        <Button variant="secondary" onClick={() => start(timer ? "simulado" : "lista")} disabled={starting || total === 0}>
          Fazer lista (gabarito no final)
        </Button>
      </div>

      {error ? <Alert>{error}</Alert> : null}
      {!items ? (
        <Spinner />
      ) : (
        <>
          <p className="text-sm text-slate-600">{total} questão(ões) encontradas</p>
          {items.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-slate-600">
              Nenhuma questão com esses filtros.
            </div>
          ) : (
            <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
              {items.map((q) => (
                <li key={q.id}>
                  <Link href={`/questoes/${q.id}`} className="block px-4 py-3 hover:bg-slate-50">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      {q.track === "concurso" ? (
                        <>
                          <span className="font-medium text-rose-800">{q.contest ?? "Concurso"}</span>
                          <span>{q.year}</span>
                          {q.format === "true_false" ? <span>· Certo ou errado</span> : null}
                        </>
                      ) : (
                        <>
                          <span className="font-medium text-indigo-800">{AREA_LABEL[q.area_code]}</span>
                          <span>ENEM {q.year}</span>
                        </>
                      )}
                      {q.subject ? <span>· {q.subject.name}</span> : null}
                      {q.difficulty ? <span>· {DIFFICULTY_LABEL[q.difficulty]}</span> : null}
                      {q.bookmarked ? <span aria-label="Favorita">★</span> : null}
                      {q.last_attempt_correct === true ? (
                        <span className="text-green-700">✓ acertou</span>
                      ) : q.last_attempt_correct === false ? (
                        <span className="text-red-700">✕ errou</span>
                      ) : null}
                    </div>
                    <p className="mt-1 line-clamp-2 text-slate-800">{q.preview}</p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
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
