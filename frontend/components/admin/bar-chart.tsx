"use client";

import { useState } from "react";

export type Series = { id: string; label: string; color: string };
export type BarDatum = { key: string; label: string; values: Record<string, number> };

function niceMax(value: number) {
  if (value <= 0) return 1;
  const exp = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((s) => s * exp >= value) ?? 10;
  return step * exp;
}

/**
 * Barras verticais (empilhadas quando há mais de uma série), em HTML.
 * Um eixo só, grade discreta, dica ao passar o mouse ou focar a barra,
 * legenda quando há 2+ séries. Cada série mantém sempre a mesma cor.
 */
export function BarChart({
  data,
  series,
  format,
  height = 180,
  ariaLabel,
}: {
  data: BarDatum[];
  series: Series[];
  format: (n: number) => string;
  height?: number;
  ariaLabel: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const totals = data.map((d) => series.reduce((sum, s) => sum + (d.values[s.id] ?? 0), 0));
  const max = niceMax(Math.max(0, ...totals));
  const ticks = [max, max / 2, 0];
  const shown = series.filter((s) => data.some((d) => (d.values[s.id] ?? 0) > 0));
  const labelEvery = Math.max(1, Math.ceil(data.length / 8));

  return (
    <figure aria-label={ariaLabel} className="w-full">
      {shown.length > 1 ? (
        <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
          {shown.map((s) => (
            <li key={s.id} className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: s.color }} aria-hidden />
              {s.label}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="flex gap-2">
        {/* eixo y */}
        <div className="relative w-14 shrink-0 text-right text-[11px] tabular-nums text-slate-500" style={{ height }}>
          {ticks.map((t, i) => (
            <span key={t} className="absolute right-0 -translate-y-1/2" style={{ top: `${(i / 2) * 100}%` }}>
              {format(t)}
            </span>
          ))}
        </div>
        <div className="relative min-w-0 flex-1">
          <div className="relative" style={{ height }}>
            {ticks.map((t, i) => (
              <div
                key={t}
                aria-hidden
                className={`absolute inset-x-0 border-t ${i === 2 ? "border-slate-300" : "border-dashed border-slate-100"}`}
                style={{ top: `${(i / 2) * 100}%` }}
              />
            ))}
            <div className="absolute inset-0 flex items-end gap-[2px]">
              {data.map((d, i) => {
                const total = totals[i];
                return (
                  <div
                    key={d.key}
                    tabIndex={0}
                    role="img"
                    aria-label={`${d.label}: ${format(total)}`}
                    onMouseEnter={() => setHover(i)}
                    onMouseLeave={() => setHover(null)}
                    onFocus={() => setHover(i)}
                    onBlur={() => setHover(null)}
                    className="group relative flex h-full min-w-0 flex-1 flex-col justify-end outline-none"
                  >
                    <div
                      className={`flex flex-col-reverse gap-[2px] overflow-hidden rounded-t-[4px] ${hover === i ? "opacity-100" : hover === null ? "opacity-100" : "opacity-60"}`}
                      style={{ height: `${(total / max) * 100}%` }}
                    >
                      {series.map((s) => {
                        const v = d.values[s.id] ?? 0;
                        if (!v) return null;
                        return <div key={s.id} style={{ backgroundColor: s.color, flexGrow: v, minHeight: 2 }} />;
                      })}
                    </div>
                    {hover === i ? (
                      <div
                        className={`pointer-events-none absolute bottom-full z-10 mb-2 w-max min-w-36 rounded-lg border border-slate-200 bg-white p-2 text-xs shadow-lg ${
                          i > data.length / 2 ? "right-0" : "left-0"
                        }`}
                      >
                        <p className="mb-1 font-medium text-slate-900">{d.label}</p>
                        {series
                          .filter((s) => (d.values[s.id] ?? 0) > 0)
                          .map((s) => (
                            <p key={s.id} className="flex items-center justify-between gap-3 text-slate-600">
                              <span className="flex items-center gap-1.5">
                                <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: s.color }} aria-hidden />
                                {s.label}
                              </span>
                              <span className="tabular-nums text-slate-900">{format(d.values[s.id])}</span>
                            </p>
                          ))}
                        {series.length > 1 ? (
                          <p className="mt-1 flex justify-between border-t border-slate-100 pt-1 font-medium text-slate-900">
                            <span>Total</span>
                            <span className="tabular-nums">{format(total)}</span>
                          </p>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
          <div className="mt-1 flex gap-[2px] text-[11px] text-slate-500">
            {data.map((d, i) => (
              <span key={d.key} className="min-w-0 flex-1 truncate text-center">
                {i % labelEvery === 0 ? d.label : ""}
              </span>
            ))}
          </div>
        </div>
      </div>
    </figure>
  );
}

/** Lista de dias (AAAA-MM-DD) de `start` até `end`, para o eixo não pular dias vazios. */
export function dayRange(start: Date, end: Date): string[] {
  const out: string[] = [];
  const d = new Date(start.getFullYear(), start.getMonth(), start.getDate());
  const last = new Date(end.getFullYear(), end.getMonth(), end.getDate());
  while (d <= last) {
    out.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`);
    d.setDate(d.getDate() + 1);
  }
  return out;
}

export function shortDay(iso: string) {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}
