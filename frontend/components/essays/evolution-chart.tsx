"use client";

import { useState } from "react";

import type { EssayStats } from "@/lib/api";
import { formatDate } from "@/lib/essays";

type Point = EssayStats["points"][number];

const W = 640;
const H = 220;
const PAD = { top: 16, right: 16, bottom: 28, left: 40 };
const Y_TICKS = [0, 200, 400, 600, 800, 1000];

/** Nota total ao longo do tempo (uma série: sem legenda, o título diz o que é). */
export function EvolutionChart({ points }: { points: Point[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);

  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const x = (i: number) =>
    PAD.left + (points.length === 1 ? innerW / 2 : (i * innerW) / (points.length - 1));
  const y = (v: number) => PAD.top + innerH - (v / 1000) * innerH;
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.total)}`).join(" ");
  const active = hover !== null ? points[hover] : null;

  return (
    <figure className="rounded-lg border border-slate-200 bg-white p-4">
      <figcaption className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-slate-700">Nota total por redação</span>
        <button
          type="button"
          onClick={() => setShowTable((v) => !v)}
          className="text-sm text-indigo-700 hover:underline"
        >
          {showTable ? "Ver gráfico" : "Ver tabela"}
        </button>
      </figcaption>

      {showTable ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-slate-500">
              <tr>
                <th className="py-1 pr-3 font-medium">Data</th>
                <th className="py-1 pr-3 font-medium">Tema</th>
                {[1, 2, 3, 4, 5].map((n) => (
                  <th key={n} className="py-1 pr-3 text-right font-medium">C{n}</th>
                ))}
                <th className="py-1 text-right font-medium">Total</th>
              </tr>
            </thead>
            <tbody className="text-slate-800">
              {points.map((p) => (
                <tr key={p.essay_id} className="border-t border-slate-100">
                  <td className="py-1 pr-3 whitespace-nowrap">{formatDate(p.graded_at)}</td>
                  <td className="max-w-56 truncate py-1 pr-3" title={p.theme_title}>{p.theme_title}</td>
                  {[p.c1, p.c2, p.c3, p.c4, p.c5].map((v, i) => (
                    <td key={i} className="py-1 pr-3 text-right tabular-nums">{v}</td>
                  ))}
                  <td className="py-1 text-right font-medium tabular-nums">{p.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="relative">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="h-auto w-full"
            role="img"
            aria-label={`Evolução da nota total em ${points.length} redação(ões)`}
            onMouseLeave={() => setHover(null)}
          >
            {Y_TICKS.map((t) => (
              <g key={t}>
                <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="#e2e8f0" strokeWidth={1} />
                <text x={PAD.left - 6} y={y(t) + 4} textAnchor="end" className="fill-slate-500 text-[11px]">
                  {t}
                </text>
              </g>
            ))}
            {active ? (
              <line x1={x(hover!)} x2={x(hover!)} y1={PAD.top} y2={PAD.top + innerH} stroke="#94a3b8" strokeWidth={1} />
            ) : null}
            <path d={`${path} L${x(points.length - 1)},${y(0)} L${x(0)},${y(0)} Z`} fill="#4f46e5" opacity={0.08} />
            <path d={path} fill="none" stroke="#4f46e5" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            {points.map((p, i) => (
              <g key={p.essay_id}>
                <circle cx={x(i)} cy={y(p.total)} r={hover === i ? 6 : 4.5} fill="#4f46e5" stroke="#fff" strokeWidth={2} />
                {/* área de toque maior que o ponto */}
                <rect
                  x={x(i) - Math.max(12, innerW / Math.max(points.length, 1) / 2)}
                  y={PAD.top}
                  width={Math.max(24, innerW / Math.max(points.length, 1))}
                  height={innerH}
                  fill="transparent"
                  onMouseEnter={() => setHover(i)}
                  onFocus={() => setHover(i)}
                  tabIndex={0}
                  aria-label={`${formatDate(p.graded_at)}: ${p.total} pontos`}
                />
              </g>
            ))}
            {points.length > 0 ? (
              <text
                x={x(points.length - 1)}
                y={y(points[points.length - 1].total) - 10}
                textAnchor={points.length === 1 ? "middle" : "end"}
                className="fill-slate-700 text-[12px] font-medium"
              >
                {points[points.length - 1].total}
              </text>
            ) : null}
          </svg>
          {active ? (
            <div
              className="pointer-events-none absolute top-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow"
              style={{ left: `${Math.min(80, (x(hover!) / W) * 100)}%` }}
            >
              <p className="font-medium text-slate-900">{formatDate(active.graded_at)}</p>
              <p className="max-w-48 truncate text-slate-500">{active.theme_title}</p>
              <p className="mt-1 text-slate-800">
                Total <strong>{active.total}</strong>
                {active.annulled ? " (anulada)" : ""}
              </p>
              <p className="text-slate-600 tabular-nums">
                C1 {active.c1} · C2 {active.c2} · C3 {active.c3} · C4 {active.c4} · C5 {active.c5}
              </p>
            </div>
          ) : null}
        </div>
      )}
    </figure>
  );
}
