"use client";

import { useRef, useState } from "react";

import type { StudyBlock } from "@/lib/api";
import { SLOT, WEEKDAYS, toHHMM, toMin } from "@/lib/planner";

const ROW_H = 24; // px por faixa de 30 min
const LABEL_W = 52; // coluna dos horários
const DRAG_THRESHOLD = 4; // px: abaixo disso é clique, não arraste

type Drag =
  | { kind: "create"; weekday: number; anchor: number; current: number }
  | {
      kind: "move" | "resize";
      block: StudyBlock;
      startX: number;
      startY: number;
      moved: boolean;
      weekday: number;
      start: number;
      end: number;
    };

export type BlockChange = { weekday: number; start: number; end: number };

export function WeekGrid({
  blocks,
  gridStart,
  gridEnd,
  onCreate,
  onEdit,
  onChange,
}: {
  blocks: StudyBlock[];
  gridStart: number;
  gridEnd: number;
  onCreate: (weekday: number, start: number, end: number) => void;
  onEdit: (block: StudyBlock) => void;
  onChange: (block: StudyBlock, change: BlockChange) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<Drag | null>(null);

  const rows = Math.max(1, Math.round((gridEnd - gridStart) / SLOT));
  const height = rows * ROW_H;

  /** Posição do ponteiro → (dia, minuto arredondado à faixa). */
  function locate(clientX: number, clientY: number) {
    const rect = ref.current!.getBoundingClientRect();
    const colW = (rect.width - LABEL_W) / 7;
    const day = Math.min(7, Math.max(1, Math.floor((clientX - rect.left - LABEL_W) / colW) + 1));
    const y = Math.min(height - 1, Math.max(0, clientY - rect.top));
    const minute = gridStart + Math.floor(y / ROW_H) * SLOT;
    return { day, minute };
  }

  function onPointerDownEmpty(e: React.PointerEvent) {
    if (e.button !== 0) return;
    const { day, minute } = locate(e.clientX, e.clientY);
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    setDrag({ kind: "create", weekday: day, anchor: minute, current: minute });
  }

  function onPointerDownBlock(e: React.PointerEvent, block: StudyBlock, kind: "move" | "resize") {
    if (e.button !== 0) return;
    e.stopPropagation();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    setDrag({
      kind,
      block,
      startX: e.clientX,
      startY: e.clientY,
      moved: false,
      weekday: block.weekday,
      start: toMin(block.start_time),
      end: toMin(block.end_time),
    });
  }

  function onPointerMove(e: React.PointerEvent) {
    if (!drag) return;
    if (drag.kind === "create") {
      const { minute } = locate(e.clientX, e.clientY);
      if (minute !== drag.current) setDrag({ ...drag, current: minute });
      return;
    }
    const dx = e.clientX - drag.startX;
    const dy = e.clientY - drag.startY;
    const moved = drag.moved || Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD;
    const deltaSlots = Math.round(dy / ROW_H) * SLOT;
    const origStart = toMin(drag.block.start_time);
    const origEnd = toMin(drag.block.end_time);
    if (drag.kind === "move") {
      const duration = origEnd - origStart;
      let start = Math.max(0, Math.min(24 * 60 - duration - 5, origStart + deltaSlots));
      start = Math.round(start / 5) * 5;
      const { day } = locate(e.clientX, e.clientY);
      setDrag({ ...drag, moved, weekday: day, start, end: start + duration });
    } else {
      const end = Math.max(origStart + SLOT, Math.min(23 * 60 + 55, origEnd + deltaSlots));
      setDrag({ ...drag, moved, end });
    }
  }

  function onPointerUp() {
    if (!drag) return;
    if (drag.kind === "create") {
      const start = Math.min(drag.anchor, drag.current);
      const end = Math.max(drag.anchor, drag.current) + SLOT;
      onCreate(drag.weekday, start, Math.min(end, 23 * 60 + 55));
    } else if (!drag.moved) {
      onEdit(drag.block);
    } else {
      const changed =
        drag.weekday !== drag.block.weekday ||
        drag.start !== toMin(drag.block.start_time) ||
        drag.end !== toMin(drag.block.end_time);
      if (changed) onChange(drag.block, { weekday: drag.weekday, start: drag.start, end: drag.end });
    }
    setDrag(null);
  }

  const top = (min: number) => ((min - gridStart) / SLOT) * ROW_H;

  function renderBlock(b: StudyBlock) {
    const live = drag && drag.kind !== "create" && drag.block.id === b.id ? drag : null;
    const weekday = live ? live.weekday : b.weekday;
    const start = live ? live.start : toMin(b.start_time);
    const end = live ? live.end : toMin(b.end_time);
    const visStart = Math.max(start, gridStart);
    const visEnd = Math.min(end, gridEnd);
    if (visEnd <= visStart) return null;
    const label = b.subject_name ?? b.title ?? b.area_code ?? "Estudo";
    const short = visEnd - visStart <= SLOT;
    return (
      <div
        key={b.id}
        role="button"
        tabIndex={0}
        aria-label={`${label}, ${WEEKDAYS[b.weekday - 1].long} das ${toHHMM(start)} às ${toHHMM(end)}. Enter para editar.`}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onEdit(b);
          }
        }}
        onPointerDown={(e) => onPointerDownBlock(e, b, "move")}
        className={`absolute cursor-grab touch-none select-none overflow-hidden rounded-md px-1.5 text-xs text-white shadow-sm ring-2 ring-white ${
          live?.moved ? "z-20 opacity-90 shadow-lg" : "z-10"
        }`}
        style={{
          top: top(visStart) + 1,
          height: top(visEnd) - top(visStart) - 2,
          left: `calc(${LABEL_W}px + (100% - ${LABEL_W}px) * ${(weekday - 1) / 7} + 2px)`,
          width: `calc((100% - ${LABEL_W}px) / 7 - 4px)`,
          backgroundColor: b.color,
        }}
      >
        <p className={`truncate font-semibold ${short ? "leading-[22px]" : "pt-0.5"}`}>
          {short ? `${toHHMM(start)} ${label}` : label}
        </p>
        {!short ? (
          <p className="truncate opacity-90">
            {toHHMM(start)}–{toHHMM(end)}
            {b.reminder_minutes_before !== null && b.reminder_minutes_before !== undefined ? " · 🔔" : ""}
          </p>
        ) : null}
        {b.title && b.subject_name && !short ? <p className="truncate opacity-90">{b.title}</p> : null}
        <div
          aria-hidden
          onPointerDown={(e) => onPointerDownBlock(e, b, "resize")}
          className="absolute inset-x-0 bottom-0 h-2 cursor-ns-resize"
        />
      </div>
    );
  }

  const ghost =
    drag && drag.kind === "create"
      ? {
          weekday: drag.weekday,
          start: Math.min(drag.anchor, drag.current),
          end: Math.max(drag.anchor, drag.current) + SLOT,
        }
      : null;

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <div className="min-w-[720px]">
        <div className="flex border-b border-slate-200 text-center text-xs font-medium text-slate-600" style={{ paddingLeft: LABEL_W }}>
          {WEEKDAYS.map((w) => (
            <div key={w.n} className="flex-1 py-2">
              {w.short}
            </div>
          ))}
        </div>
        <div
          ref={ref}
          className="relative touch-none select-none"
          style={{ height }}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={() => setDrag(null)}
        >
          {/* linhas das faixas: hora cheia mais marcada */}
          {Array.from({ length: rows }, (_, i) => {
            const minute = gridStart + i * SLOT;
            return (
              <div
                key={i}
                className={`absolute inset-x-0 border-t ${minute % 60 === 0 ? "border-slate-200" : "border-slate-100"}`}
                style={{ top: i * ROW_H, height: ROW_H }}
              >
                {minute % 60 === 0 ? (
                  <span className="absolute -top-2 left-1 bg-white px-0.5 text-[10px] tabular-nums text-slate-500">
                    {toHHMM(minute)}
                  </span>
                ) : null}
              </div>
            );
          })}
          {/* colunas dos dias (área clicável para criar) */}
          <div
            className="absolute inset-y-0 right-0 flex cursor-cell"
            style={{ left: LABEL_W }}
            onPointerDown={onPointerDownEmpty}
            aria-hidden
          >
            {WEEKDAYS.map((w) => (
              <div key={w.n} className="h-full flex-1 border-l border-slate-100" />
            ))}
          </div>
          {ghost ? (
            <div
              className="pointer-events-none absolute z-30 rounded-md border-2 border-dashed border-indigo-500 bg-indigo-100/60 px-1 text-xs text-indigo-900"
              style={{
                top: top(ghost.start),
                height: top(ghost.end) - top(ghost.start),
                left: `calc(${LABEL_W}px + (100% - ${LABEL_W}px) * ${(ghost.weekday - 1) / 7} + 2px)`,
                width: `calc((100% - ${LABEL_W}px) / 7 - 4px)`,
              }}
            >
              {toHHMM(ghost.start)}–{toHHMM(ghost.end)}
            </div>
          ) : null}
          {blocks.map(renderBlock)}
        </div>
      </div>
    </div>
  );
}
