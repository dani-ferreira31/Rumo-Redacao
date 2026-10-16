"use client";

import { ArrowDown, ArrowUp, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { type ContestFilters, FiltersBar } from "@/components/questions/filters-bar";
import { Alert, Button, Spinner, TextField } from "@/components/ui";
import { api, errorMessage, type Area, type QuestionItem } from "@/lib/api";
import type { AssessmentDetail } from "@/lib/assessments";
import { AREA_LABEL, DIFFICULTY_LABEL, type FilterState, toApiFilters } from "@/lib/questions";

const MAX_QUESTIONS = 120;

type Picked = { id: number; label: string; preview: string };

function labelOf(q: { year: number; area_code: string; track?: string; contest?: string | null; subject?: { name: string } | null }) {
  const origin = q.track === "concurso" ? (q.contest ?? "Concurso") : `${AREA_LABEL[q.area_code] ?? q.area_code} · ENEM`;
  return `${origin} ${q.year}${q.subject ? ` · ${q.subject.name}` : ""}`;
}

function previewOf(md: string) {
  return md
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "[imagem]")
    .replace(/[*_`#>]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 220);
}

/** Monta (ou edita) uma prova escolhendo questões do banco. */
export function AssessmentBuilder({ initial }: { initial?: AssessmentDetail }) {
  const router = useRouter();
  const [title, setTitle] = useState(initial?.title ?? "");
  const [instructions, setInstructions] = useState(initial?.instructions ?? "");
  const [picked, setPicked] = useState<Picked[]>(
    initial?.questions.map((q) => ({ id: q.id, label: labelOf(q), preview: previewOf(q.statement_md) })) ?? [],
  );
  const [filters, setFilters] = useState<FilterState>({});
  const [areas, setAreas] = useState<Area[]>([]);
  const [contest, setContest] = useState<ContestFilters | null>(null);
  const [items, setItems] = useState<QuestionItem[] | null>(null);
  const [total, setTotal] = useState(0);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const filtersKey = JSON.stringify(filters);
  const track = filters.track === "concurso" ? "concurso" : "enem";

  useEffect(() => {
    api.GET("/api/v1/catalog/areas").then(({ data }) => setAreas(data ?? []));
  }, []);

  useEffect(() => {
    if (track !== "concurso" || contest) return;
    api.GET("/api/v1/contests/filters").then(({ data }) => setContest(data ?? null));
  }, [track, contest]);

  useEffect(() => {
    const f = JSON.parse(filtersKey) as FilterState;
    api.GET("/api/v1/questions", { params: { query: { ...toApiFilters(f), limit: 20 } } }).then(({ data, error: e }) => {
      if (!data) {
        setError(errorMessage(e));
        return;
      }
      setItems(data.items);
      setTotal(data.total);
      setCursor(data.next_cursor ?? null);
    });
  }, [filtersKey]);

  async function loadMore() {
    if (!cursor) return;
    const { data } = await api.GET("/api/v1/questions", {
      params: { query: { ...toApiFilters(filters), limit: 20, cursor } },
    });
    if (data) {
      setItems((prev) => [...(prev ?? []), ...data.items]);
      setCursor(data.next_cursor ?? null);
    }
  }

  const pickedIds = new Set(picked.map((p) => p.id));

  function toggle(q: QuestionItem) {
    if (pickedIds.has(q.id)) setPicked(picked.filter((p) => p.id !== q.id));
    else if (picked.length < MAX_QUESTIONS) setPicked([...picked, { id: q.id, label: labelOf(q), preview: q.preview }]);
  }

  function move(index: number, delta: number) {
    const next = [...picked];
    const [item] = next.splice(index, 1);
    next.splice(index + delta, 0, item);
    setPicked(next);
  }

  async function save() {
    setSaving(true);
    setError(null);
    const ids = picked.map((p) => p.id);
    const body = { title: title.trim(), instructions: instructions.trim() || null, question_ids: ids };
    // na edição, só manda as questões se mudaram (com alunos na prova elas ficam travadas)
    const sameQuestions = initial?.questions.map((q) => q.id).join(",") === ids.join(",");
    const res = initial
      ? await api.PATCH("/api/v1/teacher/assessments/{assessment_id}", {
          params: { path: { assessment_id: initial.id } },
          body: sameQuestions ? { title: body.title, instructions: body.instructions } : body,
        })
      : await api.POST("/api/v1/teacher/assessments", { body });
    setSaving(false);
    if (res.data) router.push(`/professor/provas/${res.data.id}`);
    else setError(errorMessage(res.error));
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <section className="min-w-0 space-y-4">
        <div role="tablist" aria-label="Banco de questões" className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5">
          {(["enem", "concurso"] as const).map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={track === t}
              onClick={() => {
                setItems(null);
                setFilters(t === "concurso" ? { track: "concurso" } : {});
              }}
              className={`rounded-md px-4 py-1.5 text-sm font-medium ${
                track === t ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {t === "enem" ? "ENEM" : "Concursos"}
            </button>
          ))}
        </div>
        <FiltersBar
          key={filtersKey}
          areas={areas}
          contest={contest}
          value={{ ...filters, track }}
          onChange={(next) => {
            setItems(null);
            setFilters(next);
          }}
        />
        {!items ? (
          <Spinner />
        ) : (
          <>
            <p className="text-sm text-slate-600">{total} questão(ões) encontradas</p>
            {items.length === 0 ? (
              <p className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-slate-600">
                Nenhuma questão com esses filtros.
              </p>
            ) : (
              <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
                {items.map((q) => {
                  const on = pickedIds.has(q.id);
                  return (
                    <li key={q.id} className="flex gap-3 px-4 py-3">
                      <div className="min-w-0 flex-1">
                        <p className="text-xs text-slate-500">
                          {labelOf(q)}
                          {q.difficulty ? ` · ${DIFFICULTY_LABEL[q.difficulty]}` : ""}
                          {" · "}
                          <Link href={`/questoes/${q.id}`} target="_blank" className="text-indigo-700 hover:underline">
                            ver questão
                          </Link>
                        </p>
                        <p className="mt-0.5 line-clamp-3 text-sm text-slate-800">{q.preview}</p>
                      </div>
                      <Button
                        variant={on ? "secondary" : "primary"}
                        className="shrink-0 self-start"
                        onClick={() => toggle(q)}
                        aria-pressed={on}
                        disabled={!on && picked.length >= MAX_QUESTIONS}
                      >
                        {on ? "Remover" : "Adicionar"}
                      </Button>
                    </li>
                  );
                })}
              </ul>
            )}
            {cursor ? (
              <Button variant="secondary" onClick={() => void loadMore()}>
                Carregar mais
              </Button>
            ) : null}
          </>
        )}
      </section>

      <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
        <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <TextField label="Título da prova" value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
          <div>
            <label htmlFor="instructions" className="mb-1 block text-sm font-medium text-slate-700">
              Instruções (opcional)
            </label>
            <textarea
              id="instructions"
              rows={3}
              maxLength={5000}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="Ex.: Sem consulta. Tempo: 50 minutos."
              className="block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm"
            />
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-slate-700">
              Questões escolhidas ({picked.length})
            </p>
            {picked.length === 0 ? (
              <p className="text-sm text-slate-500">Adicione questões da lista ao lado.</p>
            ) : (
              <ol className="max-h-[50vh] space-y-2 overflow-y-auto pr-1">
                {picked.map((p, i) => (
                  <li key={p.id} className="flex gap-2 rounded-md border border-slate-200 p-2">
                    <span className="w-6 shrink-0 text-sm font-semibold tabular-nums text-slate-500">{i + 1}.</span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs text-slate-500">{p.label}</p>
                      <p className="line-clamp-2 text-xs text-slate-800">{p.preview}</p>
                    </div>
                    <div className="flex shrink-0 flex-col">
                      <button type="button" aria-label="Subir" disabled={i === 0} onClick={() => move(i, -1)} className="rounded p-0.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30">
                        <ArrowUp aria-hidden className="h-3.5 w-3.5" />
                      </button>
                      <button type="button" aria-label="Descer" disabled={i === picked.length - 1} onClick={() => move(i, 1)} className="rounded p-0.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30">
                        <ArrowDown aria-hidden className="h-3.5 w-3.5" />
                      </button>
                      <button type="button" aria-label="Remover" onClick={() => setPicked(picked.filter((x) => x.id !== p.id))} className="rounded p-0.5 text-slate-500 hover:bg-slate-100">
                        <X aria-hidden className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </div>
          {error ? <Alert>{error}</Alert> : null}
          <Button className="w-full" onClick={() => void save()} disabled={saving || !title.trim() || picked.length === 0}>
            {saving ? "Salvando..." : initial ? "Salvar alterações" : "Criar prova"}
          </Button>
        </div>
      </aside>
    </div>
  );
}
