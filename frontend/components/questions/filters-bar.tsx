"use client";

import { useState } from "react";

import type { Area } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import {
  AREA_LABEL,
  DIFFICULTY_LABEL,
  ENEM_AREAS,
  FORMAT_LABEL,
  type FilterState,
  LEVEL_LABEL,
  YEARS,
} from "@/lib/questions";

export type ContestFilters = components["schemas"]["ContestFiltersOut"];

const selectCls =
  "rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900 shadow-sm";

function Select({
  label,
  value,
  onChange,
  all,
  options,
}: {
  label: string;
  value: string | undefined;
  onChange: (v: string) => void;
  all: string;
  options: { value: string; label: string }[];
}) {
  return (
    <select aria-label={label} className={selectCls} value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
      <option value="">{all}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function FiltersBar({
  areas,
  contest,
  value,
  onChange,
}: {
  areas: Area[];
  contest: ContestFilters | null;
  value: FilterState;
  onChange: (next: FilterState) => void;
}) {
  const [q, setQ] = useState(value.q ?? "");
  const isContest = value.track === "concurso";
  const enemAreas = areas.filter((a) => ENEM_AREAS.includes(a.code));
  const contestArea = areas.find((a) => a.code === "CP");
  const area = enemAreas.find((a) => a.code === value.area);
  const subjects = isContest
    ? (contestArea?.subjects ?? [])
    : area
      ? area.subjects
      : enemAreas.flatMap((a) => a.subjects);
  const subject = subjects.find((s) => String(s.id) === value.subject_id);

  function set(key: keyof FilterState, v: string) {
    const next: FilterState = { ...value, [key]: v || undefined };
    if (key === "area") {
      next.subject_id = undefined;
      next.topic_id = undefined;
    }
    if (key === "subject_id") next.topic_id = undefined;
    onChange(next);
  }

  const status = (
    <Select
      label="Situação"
      value={value.status}
      onChange={(v) => set("status", v)}
      all="Todas"
      options={[
        { value: "nao_respondidas", label: "Não respondidas" },
        { value: "erradas", label: "Que errei" },
        { value: "favoritas", label: "Favoritas" },
      ]}
    />
  );
  const subjectSelect = (
    <Select
      label="Disciplina"
      value={value.subject_id}
      onChange={(v) => set("subject_id", v)}
      all="Todas as disciplinas"
      options={subjects.map((s) => ({ value: String(s.id), label: s.name.replace(" (concursos)", "") }))}
    />
  );

  return (
    <div className="space-y-2">
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          set("q", q.trim());
        }}
      >
        <label htmlFor="q" className="sr-only">
          Buscar no enunciado
        </label>
        <input
          id="q"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={isContest ? "Buscar no enunciado (ex.: ato administrativo)" : "Buscar no enunciado (ex.: função quadrática)"}
          className="flex-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-sm"
        />
        <button type="submit" className="rounded-md bg-slate-800 px-3 py-1.5 text-sm text-white">
          Buscar
        </button>
      </form>
      {isContest ? (
        <div className="flex flex-wrap gap-2">
          {subjectSelect}
          <Select
            label="Banca"
            value={value.board}
            onChange={(v) => set("board", v)}
            all="Todas as bancas"
            options={(contest?.boards ?? []).map((b) => ({ value: b, label: b }))}
          />
          <Select
            label="Órgão"
            value={value.organization}
            onChange={(v) => set("organization", v)}
            all="Todos os órgãos"
            options={(contest?.organizations ?? []).map((b) => ({ value: b, label: b }))}
          />
          <Select
            label="Cargo"
            value={value.position}
            onChange={(v) => set("position", v)}
            all="Todos os cargos"
            options={(contest?.positions ?? []).map((b) => ({ value: b, label: b }))}
          />
          <Select
            label="Nível"
            value={value.level}
            onChange={(v) => set("level", v)}
            all="Qualquer nível"
            options={Object.entries(LEVEL_LABEL).map(([k, v]) => ({ value: k, label: v }))}
          />
          <Select
            label="Ano"
            value={value.year}
            onChange={(v) => set("year", v)}
            all="Todos os anos"
            options={(contest?.years ?? []).map((y) => ({ value: String(y), label: String(y) }))}
          />
          <Select
            label="Formato"
            value={value.format}
            onChange={(v) => set("format", v)}
            all="Todos os formatos"
            options={Object.entries(FORMAT_LABEL).map(([k, v]) => ({ value: k, label: v }))}
          />
          {status}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Select
            label="Área"
            value={value.area}
            onChange={(v) => set("area", v)}
            all="Todas as áreas"
            options={enemAreas.map((a) => ({ value: a.code, label: AREA_LABEL[a.code] ?? a.name }))}
          />
          {subjectSelect}
          {subject && subject.topics.length ? (
            <Select
              label="Tópico"
              value={value.topic_id}
              onChange={(v) => set("topic_id", v)}
              all="Todos os tópicos"
              options={subject.topics.map((t) => ({ value: String(t.id), label: t.name }))}
            />
          ) : null}
          <Select
            label="Ano"
            value={value.year}
            onChange={(v) => set("year", v)}
            all="Todos os anos"
            options={YEARS.map((y) => ({ value: String(y), label: String(y) }))}
          />
          <Select
            label="Dificuldade"
            value={value.difficulty}
            onChange={(v) => set("difficulty", v)}
            all="Qualquer dificuldade"
            options={Object.entries(DIFFICULTY_LABEL).map(([k, v]) => ({ value: k, label: v }))}
          />
          <Select
            label="Língua estrangeira"
            value={value.language}
            onChange={(v) => set("language", v)}
            all="Inglês e espanhol"
            options={[
              { value: "ingles", label: "Só inglês" },
              { value: "espanhol", label: "Só espanhol" },
            ]}
          />
          {status}
        </div>
      )}
    </div>
  );
}
