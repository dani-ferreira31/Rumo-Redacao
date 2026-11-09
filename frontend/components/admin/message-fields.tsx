"use client";

import { useId } from "react";

import { TextField } from "@/components/ui";

/** Assunto + texto de um e-mail personalizado. {nome} vira o primeiro nome da pessoa. */
export function MessageFields({
  subject,
  body,
  onSubject,
  onBody,
  rows = 9,
}: {
  subject: string;
  body: string;
  onSubject: (v: string) => void;
  onBody: (v: string) => void;
  rows?: number;
}) {
  const bodyId = useId();
  return (
    <div className="space-y-3">
      <TextField label="Assunto" value={subject} maxLength={150} onChange={(e) => onSubject(e.target.value)} />
      <div>
        <label htmlFor={bodyId} className="mb-1 block text-sm font-medium text-slate-700">
          Mensagem
        </label>
        <textarea
          id={bodyId}
          value={body}
          rows={rows}
          maxLength={5000}
          onChange={(e) => onBody(e.target.value)}
          className="block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <p className="mt-1 text-xs text-slate-500">
          Use <code>{"{nome}"}</code> para o primeiro nome da pessoa. Deixe uma linha em branco entre os parágrafos. O
          e-mail sai com o botão “Entrar no Rumo1000”.
        </p>
      </div>
    </div>
  );
}
