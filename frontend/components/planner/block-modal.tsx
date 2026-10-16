"use client";

import { useEffect, useRef, useState } from "react";

import { Alert, Button } from "@/components/ui";
import type { Area, StudyBlock } from "@/lib/api";
import { REMINDER_OPTIONS, SLOT, WEEKDAYS, toHHMM, toMin } from "@/lib/planner";

export type BlockDraft = {
  weekday: number;
  start: number; // minutos
  end: number;
  area_id: string;
  subject_id: string;
  title: string;
  color: string;
  notes: string;
  reminder: string;
};

export function draftFromBlock(b: StudyBlock): BlockDraft {
  return {
    weekday: b.weekday,
    start: toMin(b.start_time),
    end: toMin(b.end_time),
    area_id: b.area_id ? String(b.area_id) : "",
    subject_id: b.subject_id ? String(b.subject_id) : "",
    title: b.title ?? "",
    color: b.color,
    notes: b.notes ?? "",
    reminder: b.reminder_minutes_before !== null && b.reminder_minutes_before !== undefined ? String(b.reminder_minutes_before) : "",
  };
}

const selectCls = "w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm";

export function BlockModal({
  initial,
  isNew,
  areas,
  error,
  saving,
  onSave,
  onDelete,
  onClose,
}: {
  initial: BlockDraft;
  isNew: boolean;
  areas: Area[];
  error: string | null;
  saving: boolean;
  onSave: (draft: BlockDraft, colorTouched: boolean) => void;
  onDelete?: () => void;
  onClose: () => void;
}) {
  const [d, setD] = useState<BlockDraft>(initial);
  const [colorTouched, setColorTouched] = useState(!isNew);
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  const area = areas.find((a) => String(a.id) === d.area_id);
  const subjects = area ? area.subjects : areas.flatMap((a) => a.subjects);
  const times = Array.from({ length: (24 * 60) / SLOT + 1 }, (_, i) => i * SLOT);
  const valid = d.end > d.start && (d.area_id || d.subject_id || d.title.trim());

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-lg p-0 shadow-xl backdrop:bg-slate-900/40"
    >
      <form
        method="dialog"
        className="space-y-3 p-5"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) onSave(d, colorTouched);
        }}
      >
        <h2 className="text-lg font-semibold">{isNew ? "Novo bloco de estudo" : "Editar bloco"}</h2>
        <div className="grid grid-cols-3 gap-2">
          <label className="min-w-0 text-sm">
            <span className="mb-1 block text-slate-700">Dia</span>
            <select className={selectCls} value={d.weekday} onChange={(e) => setD({ ...d, weekday: Number(e.target.value) })}>
              {WEEKDAYS.map((w) => (
                <option key={w.n} value={w.n}>
                  {w.long}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-0 text-sm">
            <span className="mb-1 block text-slate-700">Início</span>
            <select className={selectCls} value={d.start} onChange={(e) => setD({ ...d, start: Number(e.target.value) })}>
              {times.slice(0, -1).map((t) => (
                <option key={t} value={t}>
                  {toHHMM(t)}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-0 text-sm">
            <span className="mb-1 block text-slate-700">Fim</span>
            <select className={selectCls} value={d.end} onChange={(e) => setD({ ...d, end: Number(e.target.value) })}>
              {times.slice(1, -1).map((t) => (
                <option key={t} value={t}>
                  {toHHMM(t)}
                </option>
              ))}
              <option value={23 * 60 + 55}>23:55</option>
            </select>
          </label>
        </div>
        {d.end <= d.start ? (
          <p className="text-sm text-red-600">O fim deve ser depois do início. Blocos não cruzam a meia-noite: divida em dois.</p>
        ) : null}
        <div className="grid grid-cols-2 gap-2">
          <label className="min-w-0 text-sm">
            <span className="mb-1 block text-slate-700">Área</span>
            <select
              className={selectCls}
              value={d.area_id}
              onChange={(e) => setD({ ...d, area_id: e.target.value, subject_id: "" })}
            >
              <option value="">—</option>
              {areas.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name.replace(" e suas Tecnologias", "")}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-0 text-sm">
            <span className="mb-1 block text-slate-700">Disciplina</span>
            <select className={selectCls} value={d.subject_id} onChange={(e) => setD({ ...d, subject_id: e.target.value })}>
              <option value="">—</option>
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="block text-sm">
          <span className="mb-1 block text-slate-700">Título (opcional)</span>
          <input
            className={selectCls}
            value={d.title}
            maxLength={120}
            placeholder="Ex.: Revisão de funções, Redação"
            onChange={(e) => setD({ ...d, title: e.target.value })}
          />
        </label>
        <div className="grid grid-cols-2 gap-2">
          <label className="min-w-0 text-sm">
            <span className="mb-1 block text-slate-700">Lembrete por e-mail</span>
            <select className={selectCls} value={d.reminder} onChange={(e) => setD({ ...d, reminder: e.target.value })}>
              {REMINDER_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-0 text-sm">
            <span className="mb-1 block text-slate-700">Cor</span>
            <span className="flex items-center gap-2">
              <input
                type="color"
                value={d.color}
                onChange={(e) => {
                  setColorTouched(true);
                  setD({ ...d, color: e.target.value });
                }}
                className="h-9 w-12 rounded border border-slate-300"
              />
              {!colorTouched ? <span className="text-xs text-slate-500">padrão da área</span> : null}
            </span>
          </label>
        </div>
        <label className="block text-sm">
          <span className="mb-1 block text-slate-700">Observações</span>
          <textarea className={selectCls} rows={2} maxLength={2000} value={d.notes} onChange={(e) => setD({ ...d, notes: e.target.value })} />
        </label>
        {error ? <Alert>{error}</Alert> : null}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button type="submit" disabled={!valid || saving}>
            {saving ? "Salvando..." : "Salvar"}
          </Button>
          <Button type="button" variant="secondary" onClick={() => dialogRef.current?.close()}>
            Cancelar
          </Button>
          {onDelete ? (
            <Button type="button" variant="ghost" className="ml-auto text-red-700" onClick={onDelete} disabled={saving}>
              Excluir bloco
            </Button>
          ) : null}
        </div>
      </form>
    </dialog>
  );
}

/** Corpo para a API: cor só vai se o aluno escolheu (senão usa a padrão da área). */
export function draftToBody(d: BlockDraft, sendColor: boolean) {
  return {
    weekday: d.weekday,
    start_time: toHHMM(d.start),
    end_time: toHHMM(d.end),
    area_id: d.area_id ? Number(d.area_id) : null,
    subject_id: d.subject_id ? Number(d.subject_id) : null,
    title: d.title.trim() || null,
    color: sendColor ? d.color : null,
    notes: d.notes.trim() || null,
    reminder_minutes_before: d.reminder === "" ? null : Number(d.reminder),
  };
}
