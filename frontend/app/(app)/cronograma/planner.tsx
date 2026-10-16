"use client";

import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { BlockModal, type BlockDraft, draftFromBlock, draftToBody } from "@/components/planner/block-modal";
import { type BlockChange, WeekGrid } from "@/components/planner/week-grid";
import { Alert, Button, Spinner, TextField } from "@/components/ui";
import {
  api,
  errorMessage,
  type Area,
  type PlanSummary,
  type StudyBlock,
  type StudyPlan,
  type StudyPlanItem,
} from "@/lib/api";
import { AREA_LABEL } from "@/lib/questions";
import { WEEKDAYS, isoWeekday, toHHMM, toMin } from "@/lib/planner";

type ModalState = { draft: BlockDraft; block: StudyBlock | null } | null;

function conflictMessage(err: unknown): string {
  const e = err as { error?: { code?: string; message?: string; details?: { conflict?: StudyBlock } } };
  const c = e?.error?.details?.conflict;
  if (e?.error?.code === "block_overlap" && c) {
    const name = c.subject_name ?? c.title ?? "outro bloco";
    return `Esse horário se sobrepõe a "${name}" (${toHHMM(toMin(c.start_time))}–${toHHMM(toMin(c.end_time))}).`;
  }
  return errorMessage(err);
}

export function Planner() {
  const [plans, setPlans] = useState<StudyPlanItem[] | null>(null);
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [summary, setSummary] = useState<PlanSummary | null>(null);
  const [areas, setAreas] = useState<Area[]>([]);
  const [modal, setModal] = useState<ModalState>(null);
  const [modalError, setModalError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ kind: "error" | "success"; text: string } | null>(null);
  const [newName, setNewName] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [mobileDay, setMobileDay] = useState(() => isoWeekday());

  const loadPlan = useCallback(async (id: string) => {
    const [p, s] = await Promise.all([
      api.GET("/api/v1/study-plans/{plan_id}", { params: { path: { plan_id: id } } }),
      api.GET("/api/v1/study-plans/{plan_id}/summary", { params: { path: { plan_id: id } } }),
    ]);
    if (p.data) setPlan(p.data);
    if (s.data) setSummary(s.data);
  }, []);

  const loadPlans = useCallback(
    async (selectId?: string) => {
      const { data } = await api.GET("/api/v1/study-plans");
      setPlans(data ?? []);
      const target = selectId ?? data?.find((p) => p.is_active)?.id ?? data?.[0]?.id;
      if (target) await loadPlan(target);
      else setPlan(null);
    },
    [loadPlan],
  );

  useEffect(() => {
    api.GET("/api/v1/catalog/areas").then(({ data }) => setAreas(data ?? []));
    api.GET("/api/v1/study-plans").then(({ data }) => {
      setPlans(data ?? []);
      const target = data?.find((p) => p.is_active)?.id ?? data?.[0]?.id;
      if (target) loadPlan(target);
    });
  }, [loadPlan]);

  async function refresh() {
    if (!plan) return;
    await Promise.all([loadPlan(plan.id), api.GET("/api/v1/study-plans").then(({ data }) => setPlans(data ?? []))]);
  }

  // ---- planos -------------------------------------------------------------

  async function createPlan(name: string) {
    const { data, error } = await api.POST("/api/v1/study-plans", {
      body: { name, grid_start: "06:00", grid_end: "23:30" },
    });
    if (!data) return setNotice({ kind: "error", text: errorMessage(error) });
    setNewName("");
    await loadPlans(data.id);
  }

  async function planAction(action: "activate" | "duplicate") {
    if (!plan) return;
    const path = { params: { path: { plan_id: plan.id } } };
    const { data, error } =
      action === "activate"
        ? await api.POST("/api/v1/study-plans/{plan_id}/activate", path)
        : await api.POST("/api/v1/study-plans/{plan_id}/duplicate", path);
    if (!data) return setNotice({ kind: "error", text: errorMessage(error) });
    setNotice({ kind: "success", text: action === "activate" ? "Este é agora o cronograma ativo." : "Cópia criada." });
    await loadPlans(data.id);
  }

  async function renamePlan(name: string) {
    if (!plan) return;
    const { data, error } = await api.PATCH("/api/v1/study-plans/{plan_id}", {
      params: { path: { plan_id: plan.id } },
      body: { name },
    });
    if (!data) return setNotice({ kind: "error", text: errorMessage(error) });
    setRenaming(false);
    await refresh();
  }

  async function deletePlan() {
    if (!plan) return;
    const { response, error } = await api.DELETE("/api/v1/study-plans/{plan_id}", {
      params: { path: { plan_id: plan.id } },
    });
    if (!response.ok) return setNotice({ kind: "error", text: errorMessage(error) });
    await loadPlans();
  }

  // ---- blocos -------------------------------------------------------------

  function openNew(weekday: number, start: number, end: number) {
    setModalError(null);
    setModal({
      block: null,
      draft: { weekday, start, end, area_id: "", subject_id: "", title: "", color: "#4f46e5", notes: "", reminder: "" },
    });
  }

  function openEdit(block: StudyBlock) {
    setModalError(null);
    setModal({ block, draft: draftFromBlock(block) });
  }

  async function saveModal(draft: BlockDraft, colorTouched: boolean) {
    if (!plan || !modal) return;
    setSaving(true);
    setModalError(null);
    const body = draftToBody(draft, colorTouched);
    const res = modal.block
      ? await api.PATCH("/api/v1/study-plans/{plan_id}/blocks/{block_id}", {
          params: { path: { plan_id: plan.id, block_id: modal.block.id } },
          body,
        })
      : await api.POST("/api/v1/study-plans/{plan_id}/blocks", {
          params: { path: { plan_id: plan.id } },
          body,
        });
    setSaving(false);
    if (!res.data) return setModalError(conflictMessage(res.error));
    setModal(null);
    await refresh();
  }

  async function deleteBlock() {
    if (!plan || !modal?.block) return;
    setSaving(true);
    await api.DELETE("/api/v1/study-plans/{plan_id}/blocks/{block_id}", {
      params: { path: { plan_id: plan.id, block_id: modal.block.id } },
    });
    setSaving(false);
    setModal(null);
    await refresh();
  }

  async function moveBlock(block: StudyBlock, change: BlockChange) {
    if (!plan) return;
    // atualização otimista; desfaz se a API recusar (ex.: sobreposição)
    const previous = plan;
    setPlan({
      ...plan,
      blocks: plan.blocks.map((b) =>
        b.id === block.id
          ? { ...b, weekday: change.weekday, start_time: toHHMM(change.start), end_time: toHHMM(change.end) }
          : b,
      ),
    });
    const { data, error } = await api.PATCH("/api/v1/study-plans/{plan_id}/blocks/{block_id}", {
      params: { path: { plan_id: plan.id, block_id: block.id } },
      body: { weekday: change.weekday, start_time: toHHMM(change.start), end_time: toHHMM(change.end) },
    });
    if (!data) {
      setPlan(previous);
      setNotice({ kind: "error", text: conflictMessage(error) });
      return;
    }
    setNotice(null);
    await refresh();
  }

  // ---- render -------------------------------------------------------------

  if (!plans) return <Spinner />;

  if (plans.length === 0) {
    return (
      <div className="max-w-xl space-y-4">
        <PageHeader title="Cronograma" description="Monte sua grade semanal de estudos." />
        <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-6">
          <p className="text-slate-700">Você ainda não tem um cronograma. Dê um nome para começar:</p>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              createPlan(newName.trim() || "Meu cronograma");
            }}
          >
            <input
              aria-label="Nome do cronograma"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Ex.: Período de aulas"
              maxLength={80}
              className="flex-1 rounded-md border border-slate-300 px-3 py-2"
            />
            <Button type="submit">Criar</Button>
          </form>
        </div>
      </div>
    );
  }

  if (!plan) return <Spinner />;

  const gridStart = toMin(plan.grid_start);
  const gridEnd = toMin(plan.grid_end) + 30;
  const dayBlocks = plan.blocks.filter((b) => b.weekday === mobileDay);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader title="Cronograma" description="Clique e arraste na grade para criar um bloco. Arraste um bloco para mover e puxe a borda de baixo para mudar a duração." />
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3">
        <label className="flex items-center gap-2 text-sm">
          <span className="text-slate-600">Cronograma</span>
          <select
            value={plan.id}
            onChange={(e) => loadPlan(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          >
            {plans.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
                {p.is_active ? " (ativo)" : ""}
              </option>
            ))}
          </select>
        </label>
        {plan.is_active ? (
          <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">Ativo: os lembretes valem para este</span>
        ) : (
          <Button variant="secondary" onClick={() => planAction("activate")}>
            Tornar ativo
          </Button>
        )}
        <Button variant="ghost" onClick={() => setRenaming((v) => !v)}>
          Renomear
        </Button>
        <Button variant="ghost" onClick={() => planAction("duplicate")}>
          Duplicar
        </Button>
        <Button variant="ghost" onClick={() => createPlan(`Cronograma ${plans.length + 1}`)}>
          Novo
        </Button>
        {!plan.is_active ? (
          <Button variant="ghost" className="text-red-700" onClick={deletePlan}>
            Excluir
          </Button>
        ) : null}
      </div>
      {renaming ? (
        <form
          className="flex max-w-md items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            const name = new FormData(e.currentTarget).get("name");
            if (typeof name === "string" && name.trim()) renamePlan(name.trim());
          }}
        >
          <TextField label="Novo nome" name="name" defaultValue={plan.name} maxLength={80} className="flex-1" />
          <Button type="submit">Salvar</Button>
        </form>
      ) : null}

      {notice ? <Alert kind={notice.kind}>{notice.text}</Alert> : null}

      {/* Desktop: grade semanal */}
      <div className="hidden md:block">
        <WeekGrid
          blocks={plan.blocks}
          gridStart={gridStart}
          gridEnd={gridEnd}
          onCreate={openNew}
          onEdit={openEdit}
          onChange={moveBlock}
        />
      </div>

      {/* Mobile: um dia por vez, em lista */}
      <div className="space-y-3 md:hidden">
        <div className="flex gap-1 overflow-x-auto" role="tablist">
          {WEEKDAYS.map((w) => (
            <button
              key={w.n}
              type="button"
              role="tab"
              aria-selected={mobileDay === w.n}
              onClick={() => setMobileDay(w.n)}
              className={`rounded-md px-3 py-1.5 text-sm ${mobileDay === w.n ? "bg-indigo-600 text-white" : "bg-white text-slate-700"}`}
            >
              {w.short}
            </button>
          ))}
        </div>
        {dayBlocks.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-600">
            Nenhum bloco na {WEEKDAYS[mobileDay - 1].long.toLowerCase()}.
          </p>
        ) : (
          <ul className="space-y-2">
            {dayBlocks.map((b) => (
              <li key={b.id}>
                <button
                  type="button"
                  onClick={() => openEdit(b)}
                  className="flex w-full items-center gap-3 rounded-lg border border-slate-200 bg-white p-3 text-left"
                >
                  <span className="h-10 w-1.5 rounded-full" style={{ backgroundColor: b.color }} aria-hidden />
                  <span className="flex-1">
                    <span className="block font-medium text-slate-900">{b.subject_name ?? b.title ?? AREA_LABEL[b.area_code ?? ""] ?? "Estudo"}</span>
                    <span className="block text-sm text-slate-600">
                      {toHHMM(toMin(b.start_time))}–{toHHMM(toMin(b.end_time))}
                      {b.reminder_minutes_before !== null && b.reminder_minutes_before !== undefined ? " · 🔔" : ""}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <Button onClick={() => openNew(mobileDay, 19 * 60, 20 * 60)}>Adicionar bloco</Button>
      </div>

      {summary ? (
        <section className="grid gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <p className="text-sm text-slate-500">Horas por semana</p>
            <p className="text-3xl font-semibold tabular-nums">{summary.total_hours.toLocaleString("pt-BR")} h</p>
            <ul className="mt-4 space-y-2">
              {summary.by_day.map((d) => (
                <li key={d.key} className="flex items-center gap-2 text-sm">
                  <span className="w-8 text-slate-600">{d.label}</span>
                  <span className="h-2 flex-1 rounded-full bg-slate-100" aria-hidden>
                    <span
                      className="block h-2 rounded-full bg-indigo-600"
                      style={{ width: `${summary.total_hours ? (100 * d.hours) / Math.max(...summary.by_day.map((x) => x.hours), 1) : 0}%` }}
                    />
                  </span>
                  <span className="w-12 text-right tabular-nums text-slate-700">{d.hours.toLocaleString("pt-BR")} h</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <p className="mb-3 text-sm text-slate-500">Por área</p>
            {summary.by_area.length === 0 ? (
              <p className="text-sm text-slate-600">Adicione blocos para ver a distribuição.</p>
            ) : (
              <ul className="space-y-3">
                {summary.by_area.map((a) => (
                  <li key={a.key}>
                    <div className="mb-1 flex justify-between text-sm">
                      <span>{AREA_LABEL[a.key] ?? a.label}</span>
                      <span className="tabular-nums text-slate-600">
                        {a.hours.toLocaleString("pt-BR")} h · {Math.round((100 * a.hours) / summary.total_hours)}%
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-slate-100" aria-hidden>
                      <div className="h-2 rounded-full bg-indigo-600" style={{ width: `${(100 * a.hours) / summary.total_hours}%` }} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      ) : null}

      {modal ? (
        <BlockModal
          key={modal.block?.id ?? "new"}
          initial={modal.draft}
          isNew={!modal.block}
          areas={areas}
          error={modalError}
          saving={saving}
          onSave={saveModal}
          onDelete={modal.block ? deleteBlock : undefined}
          onClose={() => setModal(null)}
        />
      ) : null}
    </div>
  );
}
