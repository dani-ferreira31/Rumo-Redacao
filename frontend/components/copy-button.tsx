"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

/** Copia um texto (ex.: link de convite ou de prova) e confirma por 2 s. */
export function CopyButton({ text, label = "Copiar link" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt("Copie o link:", text);
    }
  }
  return (
    <button
      type="button"
      onClick={() => void copy()}
      className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
    >
      {copied ? <Check aria-hidden className="h-4 w-4 text-emerald-600" /> : <Copy aria-hidden className="h-4 w-4" />}
      <span aria-live="polite">{copied ? "Copiado" : label}</span>
    </button>
  );
}
