"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Markdown } from "@/components/markdown";
import { Alert, Button, Spinner } from "@/components/ui";
import { api, errorMessage, type AdminQuestion, type Area } from "@/lib/api";
import { AREA_LABEL } from "@/lib/questions";

type Letter = "A" | "B" | "C" | "D" | "E";
type Format = "multiple_choice" | "true_false";

const LETTERS: Letter[] = ["A", "B", "C", "D", "E"];
const inputCls = "w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm";

type Form = {
  statement_md: string;
  format: Format;
  options: Record<Letter, string>;
  explanation_md: string;
  subject_id: string;
  topic_ids: number[];
  correct_option: Letter | "";
  is_annulled: boolean;
};

function formFrom(q: AdminQuestion): Form {
  const options = { A: "", B: "", C: "", D: "", E: "" } as Record<Letter, string>;
  for (const o of q.options) options[o.letter as Letter] = o.text_md;
  return {
    statement_md: q.statement_md,
    format: (q.format ?? "multiple_choice") as Format,
    options,
    explanation_md: q.explanation_md ?? "",
    subject_id: q.subject ? String(q.subject.id) : "",
    topic_ids: q.topics.map((t) => t.id),
    correct_option: (q.correct_option ?? "") as Letter | "",
    is_annulled: q.is_annulled,
  };
}

export function QuestionEditor() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const back = search.get("voltar");
  const [q, setQ] = useState<AdminQuestion | null>(null);
  const [areas, setAreas] = useState<Area[]>([]);
  const [form, setForm] = useState<Form | null>(null);
  const [editText, setEditText] = useState(false);
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.GET("/api/v1/catalog/areas").then(({ data }) => setAreas(data ?? []));
    api.GET("/api/v1/admin/questions/{question_id}", { params: { path: { question_id: Number(id) } } }).then(({ data, error }) => {
      if (!data) return setMessage({ kind: "error", text: errorMessage(error) });
      setQ(data);
      setForm(formFrom(data));
      setEditText(data.source === "concurso" && !data.is_published);
    });
  }, [id]);

  if (!q || !form) return message ? <Alert>{message.text}</Alert> : <Spinner />;

  const area = areas.find((a) => a.code === q.area_code);
  const subject = area?.subjects.find((s) => String(s.id) === form.subject_id);
  const trueFalse = form.format === "true_false";
  const answerChoices: { value: Letter; label: string }[] = trueFalse
    ? [
        { value: "C", label: "Certo" },
        { value: "E", label: "Errado" },
      ]
    : LETTERS.filter((l) => !editText || form.options[l].trim()).map((l) => ({ value: l, label: l }));

  async function save(markReviewed: boolean) {
    if (!form) return;
    setSaving(true);
    setMessage(null);
    const options = trueFalse
      ? []
      : LETTERS.filter((l) => form.options[l].trim()).map((l) => ({ letter: l, text_md: form.options[l].trim() }));
    const { data, error } = await api.PATCH("/api/v1/admin/questions/{question_id}", {
      params: { path: { question_id: q!.id } },
      body: {
        explanation_md: form.explanation_md || null,
        subject_id: form.subject_id ? Number(form.subject_id) : null,
        topic_ids: form.topic_ids,
        correct_option: form.correct_option || null,
        is_annulled: form.is_annulled,
        ...(editText ? { statement_md: form.statement_md, format: form.format, options } : {}),
        ...(markReviewed ? { reviewed: true } : {}),
      },
    });
    setSaving(false);
    if (data) {
      setQ(data);
      setForm(formFrom(data));
      setMessage({ kind: "success", text: markReviewed ? "Salva e marcada como revisada." : "Salva." });
    } else setMessage({ kind: "error", text: errorMessage(error) });
  }

  const origin =
    q.source === "concurso"
      ? `Concurso ${q.positions[0]?.label ?? ""}`
      : `${AREA_LABEL[q.area_code]} · ENEM ${q.year} · fonte ${q.source}`;

  return (
    <div className="grid max-w-6xl gap-6 lg:grid-cols-2">
      <div className="min-w-0 space-y-4">
        <Link href={back ?? "/admin/questoes"} className="text-sm text-indigo-700 hover:underline">
          ← {back ? "Voltar para a prova" : "Fila de revisão"}
        </Link>
        <p className="text-sm text-slate-600">
          #{q.id} · {origin}
          {q.inep_item_code ? ` · item INEP ${q.inep_item_code}` : ""}
          {q.irt_b !== null && q.irt_b !== undefined ? ` · b = ${q.irt_b}` : ""}
          {q.reviewed ? " · revisada" : " · não revisada"}
          {q.is_published ? "" : " · não publicada"}
        </p>
        {editText ? (
          <div className="space-y-3">
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">Formato</span>
              <select
                className={inputCls}
                value={form.format}
                onChange={(e) => setForm({ ...form, format: e.target.value as Format, correct_option: "" })}
              >
                <option value="multiple_choice">Múltipla escolha</option>
                <option value="true_false">Certo ou errado</option>
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">Enunciado (Markdown)</span>
              <textarea
                rows={12}
                value={form.statement_md}
                onChange={(e) => setForm({ ...form, statement_md: e.target.value })}
                className={`${inputCls} font-mono`}
              />
            </label>
            {!trueFalse
              ? LETTERS.map((l) => (
                  <label key={l} className="flex items-start gap-2 text-sm">
                    <span className="mt-1.5 w-4 font-semibold">{l}</span>
                    <textarea
                      rows={2}
                      value={form.options[l]}
                      placeholder={l === "E" ? "(deixe vazio se a prova tem só A–D)" : ""}
                      onChange={(e) => setForm({ ...form, options: { ...form.options, [l]: e.target.value } })}
                      className={inputCls}
                    />
                  </label>
                ))
              : null}
            <details className="rounded-md border border-slate-200 p-3 text-sm">
              <summary className="cursor-pointer text-slate-600">Pré-visualizar</summary>
              <div className="mt-2">
                <Markdown>{form.statement_md}</Markdown>
              </div>
            </details>
          </div>
        ) : (
          <>
            <Markdown>{q.statement_md}</Markdown>
            {trueFalse ? (
              <p className="text-sm text-slate-600">Item de julgar (Certo ou errado).</p>
            ) : (
              <ol className="space-y-2">
                {q.options.map((o) => (
                  <li key={o.letter} className={`flex gap-2 rounded border p-2 ${o.letter === q.correct_option ? "border-green-500 bg-green-50" : "border-slate-200"}`}>
                    <strong>{o.letter}</strong>
                    <Markdown className="flex-1">{o.text_md}</Markdown>
                  </li>
                ))}
              </ol>
            )}
            <button type="button" className="text-sm text-indigo-700 hover:underline" onClick={() => setEditText(true)}>
              Editar enunciado e alternativas
            </button>
          </>
        )}
      </div>

      <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-5 lg:sticky lg:top-4 lg:self-start">
        <h2 className="font-semibold">Classificação e gabarito</h2>
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-700">Disciplina</span>
          <select
            value={form.subject_id}
            onChange={(e) => setForm({ ...form, subject_id: e.target.value, topic_ids: [] })}
            className={inputCls}
          >
            <option value="">Sem disciplina</option>
            {area?.subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        {subject?.topics.length ? (
          <fieldset className="text-sm">
            <legend className="mb-1 font-medium text-slate-700">Tópicos</legend>
            <div className="grid max-h-48 grid-cols-2 gap-1 overflow-y-auto">
              {subject.topics.map((t) => (
                <label key={t.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={form.topic_ids.includes(t.id)}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        topic_ids: e.target.checked ? [...form.topic_ids, t.id] : form.topic_ids.filter((x) => x !== t.id),
                      })
                    }
                  />
                  {t.name}
                </label>
              ))}
            </div>
          </fieldset>
        ) : null}
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <label className="flex items-center gap-2">
            <span className="font-medium text-slate-700">Gabarito</span>
            <select
              value={form.correct_option}
              onChange={(e) => setForm({ ...form, correct_option: e.target.value as Letter | "" })}
              className="rounded-md border border-slate-300 px-2 py-1"
            >
              <option value="">—</option>
              {answerChoices.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={form.is_annulled} onChange={(e) => setForm({ ...form, is_annulled: e.target.checked })} />
            Anulada
          </label>
        </div>
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-700">Resolução comentada (Markdown)</span>
          <textarea
            rows={8}
            value={form.explanation_md}
            onChange={(e) => setForm({ ...form, explanation_md: e.target.value })}
            className={`${inputCls} font-mono`}
          />
        </label>
        {message ? <Alert kind={message.kind}>{message.text}</Alert> : null}
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => save(false)} disabled={saving}>
            Salvar
          </Button>
          <Button onClick={() => save(true)} disabled={saving}>
            Salvar e marcar revisada
          </Button>
        </div>
      </div>
    </div>
  );
}
