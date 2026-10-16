"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Alert, Button, Card } from "@/components/ui";
import { api, apiFetch, errorMessage, type Essay, type Theme } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPT = "image/jpeg,image/png,image/heic,image/heif,image/webp,.heic,.heif";

type Mode = "photo" | "text";

function wordCount(text: string) {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

export function NewEssayForm() {
  const router = useRouter();
  const { user } = useAuth();
  const [themes, setThemes] = useState<Theme[]>([]);
  const [themeId, setThemeId] = useState("");
  const [customTheme, setCustomTheme] = useState("");
  const [mode, setMode] = useState<Mode>("photo");
  const [files, setFiles] = useState<File[]>([]);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    api.GET("/api/v1/essay-themes").then(({ data }) => setThemes(data ?? []));
  }, []);

  const previews = useMemo(
    () => files.map((f) => ({ name: f.name, url: /hei[cf]$/i.test(f.name) ? null : URL.createObjectURL(f) })),
    [files],
  );
  useEffect(() => () => previews.forEach((p) => p.url && URL.revokeObjectURL(p.url)), [previews]);

  function addFiles(list: FileList | null) {
    if (!list) return;
    setError(null);
    const next = [...files, ...Array.from(list)].slice(0, 2);
    const tooBig = next.find((f) => f.size > MAX_BYTES);
    if (tooBig) {
      setError(`A imagem ${tooBig.name} passa de 10 MB.`);
      return;
    }
    setFiles(next);
  }

  const words = wordCount(text);
  const estimatedLines = text
    .split(/\n\s*\n/)
    .filter((p) => p.trim())
    .reduce((acc, p) => acc + Math.max(1, Math.ceil(wordCount(p) / 10)), 0);

  const canSubmit =
    !!user?.email_verified &&
    (themeId || customTheme.trim().length >= 5) &&
    (mode === "photo" ? files.length > 0 : words > 0);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSending(true);
    const form = new FormData();
    if (themeId) form.append("theme_id", themeId);
    else form.append("custom_theme", customTheme.trim());
    if (mode === "photo") files.forEach((f) => form.append("images", f, f.name));
    else form.append("text", text);
    const res = await apiFetch("/api/v1/essays", { method: "POST", body: form });
    const body = await res.json().catch(() => null);
    setSending(false);
    if (!res.ok) {
      setError(errorMessage(body));
      return;
    }
    router.push(`/redacoes/${(body as Essay).id}`);
  }

  return (
    <div className="max-w-3xl">
      <PageHeader title="Nova redação" />
      {!user?.email_verified ? (
        <div className="mb-4">
          <Alert kind="warning">Confirme seu e-mail para enviar redações (veja o aviso no topo).</Alert>
        </div>
      ) : null}

      <form onSubmit={submit} className="space-y-6">
        <Card>
          <h2 className="mb-3 text-lg font-semibold">1. Tema</h2>
          <label htmlFor="theme" className="mb-1 block text-sm font-medium text-slate-700">
            Tema oficial do ENEM
          </label>
          <select
            id="theme"
            value={themeId}
            onChange={(e) => setThemeId(e.target.value)}
            className="block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 shadow-sm"
          >
            <option value="">Nenhum: vou digitar um tema</option>
            {themes.map((t) => (
              <option key={t.id} value={t.id}>
                {t.year ? `ENEM ${t.year}: ` : ""}
                {t.title}
              </option>
            ))}
          </select>
          {!themeId ? (
            <div className="mt-3">
              <label htmlFor="custom" className="mb-1 block text-sm font-medium text-slate-700">
                Tema personalizado
              </label>
              <input
                id="custom"
                value={customTheme}
                onChange={(e) => setCustomTheme(e.target.value)}
                maxLength={300}
                placeholder="Ex.: Desafios para o combate à desinformação no Brasil"
                className="block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 shadow-sm"
              />
            </div>
          ) : null}
        </Card>

        <Card>
          <h2 className="mb-3 text-lg font-semibold">2. Sua redação</h2>
          <div role="tablist" className="mb-4 inline-flex rounded-md border border-slate-300 p-0.5">
            {(["photo", "text"] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                role="tab"
                aria-selected={mode === m}
                onClick={() => setMode(m)}
                className={`rounded px-3 py-1.5 text-sm font-medium ${
                  mode === m ? "bg-indigo-600 text-white" : "text-slate-700 hover:bg-slate-100"
                }`}
              >
                {m === "photo" ? "Enviar foto" : "Digitar texto"}
              </button>
            ))}
          </div>

          {mode === "photo" ? (
            <div className="space-y-4">
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
                <li>Fotografe com boa luz, de preferência luz natural, sem sombra sobre a folha.</li>
                <li>Enquadre a folha inteira, com as bordas visíveis, de frente e sem inclinação.</li>
                <li>Se a redação ocupar duas páginas, envie uma foto de cada (máximo 2).</li>
                <li>Formatos: JPEG, PNG, HEIC (iPhone) ou WebP, até 10 MB cada.</li>
              </ul>
              <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 p-6 text-center hover:border-indigo-400">
                <span className="text-sm font-medium text-indigo-700">
                  {files.length ? "Adicionar outra página" : "Escolher ou tirar foto"}
                </span>
                <span className="mt-1 text-xs text-slate-500">{files.length}/2 páginas</span>
                <input
                  type="file"
                  accept={ACCEPT}
                  multiple
                  className="sr-only"
                  disabled={files.length >= 2}
                  onChange={(e) => {
                    addFiles(e.target.files);
                    e.target.value = "";
                  }}
                />
              </label>
              {previews.length ? (
                <div className="grid grid-cols-2 gap-3">
                  {previews.map((p, i) => (
                    <div key={i} className="rounded-md border border-slate-200 p-2">
                      {p.url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={p.url} alt={`Página ${i + 1}`} className="h-48 w-full rounded object-contain" />
                      ) : (
                        <div className="flex h-48 items-center justify-center text-xs text-slate-500">
                          Prévia indisponível para HEIC
                        </div>
                      )}
                      <div className="mt-2 flex items-center justify-between text-xs">
                        <span className="truncate text-slate-600">
                          Página {i + 1}: {p.name}
                        </span>
                        <button
                          type="button"
                          onClick={() => setFiles(files.filter((_, j) => j !== i))}
                          className="text-red-700 hover:underline"
                        >
                          Remover
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : (
            <div>
              <label htmlFor="essay-text" className="sr-only">
                Texto da redação
              </label>
              <textarea
                id="essay-text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={18}
                placeholder="Cole ou digite sua redação. Deixe uma linha em branco entre os parágrafos."
                className="block w-full rounded-md border border-slate-300 bg-white px-3 py-2 font-serif text-slate-900 shadow-sm"
              />
              <p className="mt-1 text-sm text-slate-500">
                {words} palavras · cerca de {estimatedLines} linhas da folha oficial (estimativa: 10
                palavras por linha). O ENEM exige mais de 7 e considera até 30.
              </p>
            </div>
          )}
        </Card>

        {error ? <Alert>{error}</Alert> : null}
        <Button type="submit" disabled={!canSubmit || sending}>
          {sending ? "Enviando..." : mode === "photo" ? "Enviar e transcrever" : "Enviar para correção"}
        </Button>
      </form>
    </div>
  );
}
