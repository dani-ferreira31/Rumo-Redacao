"use client";

import { useRef, useState } from "react";

import { Alert, Button } from "@/components/ui";
import { api, errorMessage, type Essay } from "@/lib/api";
import { findMarkers } from "@/lib/essays";

export function TranscriptionReview({
  essay,
  onChange,
}: {
  essay: Essay;
  onChange: (essay: Essay) => void;
}) {
  const [text, setText] = useState(essay.transcription_text ?? "");
  const [page, setPage] = useState(0);
  const [saving, setSaving] = useState<"draft" | "confirm" | null>(null);
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const markers = findMarkers(text);
  const info = essay.transcription;
  const image = essay.images[page];

  function jumpTo(line: number, marker: string) {
    const el = textareaRef.current;
    if (!el) return;
    const lines = text.split("\n");
    const start = lines.slice(0, line - 1).reduce((acc, l) => acc + l.length + 1, 0);
    const pos = start + lines[line - 1].indexOf(marker);
    el.focus();
    el.setSelectionRange(pos, pos + marker.length);
    // rola a caixa até a linha selecionada
    const lineHeight = parseFloat(getComputedStyle(el).lineHeight) || 24;
    el.scrollTop = Math.max(0, (line - 3) * lineHeight);
  }

  async function saveDraft() {
    setSaving("draft");
    setMessage(null);
    const { data, error } = await api.PUT("/api/v1/essays/{essay_id}/transcription", {
      params: { path: { essay_id: essay.id } },
      body: { text },
    });
    setSaving(null);
    if (data) {
      onChange(data);
      setMessage({ kind: "success", text: "Rascunho salvo." });
    } else setMessage({ kind: "error", text: errorMessage(error) });
  }

  async function confirm() {
    setSaving("confirm");
    setMessage(null);
    const { data, error } = await api.POST("/api/v1/essays/{essay_id}/confirm", {
      params: { path: { essay_id: essay.id } },
      body: { text },
    });
    setSaving(null);
    if (data) onChange(data);
    else setMessage({ kind: "error", text: errorMessage(error) });
  }

  return (
    <div className="space-y-4">
      <Alert kind="info">
        Confira a transcrição comparando com a foto. Corrija só o que a leitura errou:{" "}
        <strong>mantenha seus próprios erros de português</strong>, porque eles fazem parte da
        avaliação da Competência 1. Trechos marcados com <code>[ilegível]</code> ou{" "}
        <code>[?palavra]</code> precisam ser resolvidos antes de confirmar.
      </Alert>
      {info?.confidence === "baixa" ? (
        <Alert kind="warning">
          A leitura da foto teve baixa confiança. Se muitos trechos estiverem errados, considere
          excluir esta redação e enviar uma foto mais nítida.
        </Alert>
      ) : null}
      {info?.possible_identification ? (
        <Alert kind="warning">
          Parece haver nome, assinatura ou outra identificação no texto. No ENEM isso anula a
          redação.
        </Alert>
      ) : null}
      {info?.observations ? <p className="text-sm text-slate-600">Observações da leitura: {info.observations}</p> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-2">
          {essay.images.length > 1 ? (
            <div className="flex gap-2">
              {essay.images.map((img, i) => (
                <button
                  key={img.page}
                  type="button"
                  onClick={() => setPage(i)}
                  className={`rounded px-3 py-1 text-sm ${page === i ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-700"}`}
                >
                  Página {img.page}
                </button>
              ))}
            </div>
          ) : null}
          {image ? (
            <a href={image.original_url} target="_blank" rel="noreferrer" title="Abrir foto original em outra aba">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={image.url ?? image.original_url}
                alt={`Foto da página ${image.page}`}
                className="max-h-[75vh] w-full rounded-md border border-slate-200 bg-white object-contain"
              />
            </a>
          ) : null}
          <p className="text-xs text-slate-500">Clique na imagem para abrir a foto original.</p>
        </div>

        <div className="space-y-2">
          {info?.title ? (
            <p className="text-sm text-slate-600">
              Título identificado: <strong>{info.title}</strong> (não conta como linha)
            </p>
          ) : null}
          <label htmlFor="transcription" className="block text-sm font-medium text-slate-700">
            Transcrição (uma linha da folha por linha; linha em branco separa parágrafos)
          </label>
          <textarea
            id="transcription"
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={24}
            wrap="off"
            spellCheck={false}
            className="block w-full overflow-x-auto rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-sm leading-6 text-slate-900 shadow-sm"
          />
          {markers.length ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <p className="font-medium">{markers.length} trecho(s) para resolver:</p>
              <ul className="mt-1 flex flex-wrap gap-2">
                {markers.map((m, i) => (
                  <li key={i}>
                    <button
                      type="button"
                      onClick={() => jumpTo(m.line, m.marker)}
                      className="rounded bg-amber-200 px-2 py-0.5 font-mono text-xs hover:bg-amber-300"
                    >
                      linha {m.line}: {m.marker}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-sm text-green-700">Nenhum trecho duvidoso pendente.</p>
          )}
          {message ? <Alert kind={message.kind}>{message.text}</Alert> : null}
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={saveDraft} disabled={saving !== null}>
              {saving === "draft" ? "Salvando..." : "Salvar rascunho"}
            </Button>
            <Button onClick={confirm} disabled={saving !== null || markers.length > 0 || !text.trim()}>
              {saving === "confirm" ? "Enviando..." : "Confirmar e corrigir"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
