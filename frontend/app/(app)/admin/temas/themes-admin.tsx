"use client";

import { useEffect, useState } from "react";

import { Alert, Button, Spinner, TextField } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { components } from "@/lib/api-schema";

type Theme = components["schemas"]["AdminThemeOut"];

export function ThemesAdmin() {
  const [themes, setThemes] = useState<Theme[] | null>(null);
  const [editing, setEditing] = useState<Theme | null>(null);
  const [draft, setDraft] = useState({ title: "", year: "", motivating_texts: "" });
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  function load() {
    return api.GET("/api/v1/admin/essay-themes").then(({ data }) => setThemes(data ?? []));
  }
  useEffect(() => {
    load();
  }, []);

  function startEdit(t: Theme | null) {
    setEditing(t);
    setMessage(null);
    setDraft({ title: t?.title ?? "", year: t?.year ? String(t.year) : "", motivating_texts: t?.motivating_texts ?? "" });
  }

  async function save() {
    const body = {
      title: draft.title.trim(),
      year: draft.year ? Number(draft.year) : null,
      motivating_texts: draft.motivating_texts.trim() || null,
    };
    const res = editing
      ? await api.PATCH("/api/v1/admin/essay-themes/{theme_id}", { params: { path: { theme_id: editing.id } }, body })
      : await api.POST("/api/v1/admin/essay-themes", { body: { ...body, is_official: true } });
    if (!res.data) return setMessage({ kind: "error", text: errorMessage(res.error) });
    setMessage({ kind: "success", text: "Tema salvo." });
    setEditing(res.data);
    load();
  }

  return (
    <div className="grid max-w-6xl gap-6 lg:grid-cols-2">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Temas de redação</h1>
          <Button variant="secondary" onClick={() => startEdit(null)}>
            Novo tema
          </Button>
        </div>
        {!themes ? (
          <Spinner />
        ) : (
          <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
            {themes.map((t) => (
              <li key={t.id}>
                <button type="button" onClick={() => startEdit(t)} className="block w-full px-4 py-3 text-left hover:bg-slate-50">
                  <p className="text-xs text-slate-500">
                    {t.year ?? "sem ano"} · {t.motivating_texts ? "com textos motivadores" : "sem textos motivadores"}
                  </p>
                  <p className="text-slate-800">{t.title}</p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-5 lg:self-start">
        <h2 className="font-semibold">{editing ? "Editar tema" : "Novo tema"}</h2>
        <TextField label="Título" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
        <TextField label="Ano" type="number" value={draft.year} onChange={(e) => setDraft({ ...draft, year: e.target.value })} />
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-700">Textos motivadores (Markdown)</span>
          <textarea
            rows={12}
            value={draft.motivating_texts}
            onChange={(e) => setDraft({ ...draft, motivating_texts: e.target.value })}
            className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
          <span className="mt-1 block text-xs text-slate-500">
            Usados na correção e na detecção de cópia. Confira os direitos de uso antes de publicar.
          </span>
        </label>
        {message ? <Alert kind={message.kind}>{message.text}</Alert> : null}
        <Button onClick={save} disabled={draft.title.trim().length < 5}>
          Salvar
        </Button>
      </div>
    </div>
  );
}
