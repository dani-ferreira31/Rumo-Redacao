"use client";

import { ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AdminHeader, EmptyState, Section, StatCard, StatusBadge } from "@/components/admin/kit";
import { Alert, Button, Spinner } from "@/components/ui";
import { type SystemEvent, dateTime, relativeTime } from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";
import type { components } from "@/lib/api-schema";

type LogsOut = components["schemas"]["LogsOut"];
type LogItem = components["schemas"]["LogItem"];
type LogDetail = components["schemas"]["LogDetail"];
type Level = "" | "ERROR" | "WARNING";
type Source = "" | "api" | "worker";

const selectCls = "rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900 shadow-sm";
const SOURCE_LABEL: Record<string, string> = { api: "API", worker: "Worker" };

function LevelBadge({ level }: { level: string }) {
  return level === "WARNING" ? (
    <StatusBadge level="warning">Aviso</StatusBadge>
  ) : (
    <StatusBadge level="error">{level === "CRITICAL" ? "Crítico" : "Erro"}</StatusBadge>
  );
}

function LogRow({ item }: { item: LogItem }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<LogDetail | null>(null);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !detail) {
      const { data } = await api.GET("/api/v1/admin/logs/{log_id}", { params: { path: { log_id: item.id } } });
      setDetail(data ?? null);
    }
  }

  return (
    <li className="py-2">
      <button type="button" onClick={() => void toggle()} aria-expanded={open} className="flex w-full flex-wrap items-start gap-x-3 gap-y-1 rounded-md px-2 py-1 text-left hover:bg-slate-50">
        <span className="w-32 shrink-0 text-xs tabular-nums text-slate-500" title={dateTime(item.created_at)}>
          {dateTime(item.created_at)}
        </span>
        <LevelBadge level={item.level} />
        <span className="text-xs text-slate-500">{SOURCE_LABEL[item.source] ?? item.source}</span>
        <span className="min-w-0 flex-1">
          <span className="font-mono text-sm text-slate-900">{item.event}</span>
          {item.error ? <span className="block truncate text-sm text-red-700">{item.error}</span> : null}
          {item.path ? <span className="block truncate font-mono text-xs text-slate-500">{item.path}</span> : null}
        </span>
      </button>
      {open ? (
        <div className="mt-2 space-y-2 rounded-md border border-slate-200 bg-slate-50 p-3 text-xs">
          {!detail ? (
            <Spinner />
          ) : (
            <>
              <dl className="grid grid-cols-[8rem_minmax(0,1fr)] gap-x-3 gap-y-1">
                <dt className="text-slate-500">Componente</dt>
                <dd className="font-mono">{detail.logger}</dd>
                {detail.request_id ? (
                  <>
                    <dt className="text-slate-500">Requisição</dt>
                    <dd className="font-mono">{detail.request_id}</dd>
                  </>
                ) : null}
                {Object.entries(detail.details).map(([k, v]) => (
                  <div key={k} className="contents">
                    <dt className="text-slate-500">{k}</dt>
                    <dd className="break-all font-mono">{typeof v === "string" ? v : JSON.stringify(v)}</dd>
                  </div>
                ))}
              </dl>
              {detail.traceback ? (
                <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded bg-slate-900 p-3 font-mono text-[11px] leading-relaxed text-slate-100">
                  {detail.traceback}
                </pre>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </li>
  );
}

export function LogsAdmin() {
  const [tab, setTab] = useState<"logs" | "events">("logs");
  const [data, setData] = useState<LogsOut | null>(null);
  const [items, setItems] = useState<LogItem[]>([]);
  const [events, setEvents] = useState<SystemEvent[] | null>(null);
  const [level, setLevel] = useState<Level>("");
  const [source, setSource] = useState<Source>("");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [retention, setRetention] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const query = useCallback(
    (before?: number | null) => ({
      level: level || undefined,
      source: source || undefined,
      q: search || undefined,
      before_id: before ?? undefined,
      limit: 50,
    }),
    [level, source, search],
  );

  const load = useCallback(
    () =>
      api.GET("/api/v1/admin/logs", { params: { query: query() } }).then(({ data: d, error: e }) => {
        if (!d) return setError(errorMessage(e));
        setData(d);
        setItems(d.items);
        setRetention((prev) => prev || String(d.retention_days));
      }),
    [query],
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (tab === "events" && !events) {
      api.GET("/api/v1/admin/events", { params: { query: { limit: 200 } } }).then(({ data: d }) => setEvents(d ?? []));
    }
  }, [tab, events]);

  async function more() {
    if (!data?.next_before_id) return;
    const { data: d } = await api.GET("/api/v1/admin/logs", { params: { query: query(data.next_before_id) } });
    if (d) {
      setItems((prev) => [...prev, ...d.items]);
      setData({ ...d, summary: data.summary });
    }
  }

  async function saveRetention(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    const { data: d, error: err } = await api.PUT("/api/v1/admin/logs/settings", {
      body: { retention_days: Number(retention) },
    });
    if (d) {
      setMessage(`Os registros com mais de ${d.retention_days} dias foram apagados.`);
      void load();
    } else setError(errorMessage(err));
  }

  async function clearAll() {
    if (!window.confirm("Apagar todos os registros de avisos e erros? Não dá para desfazer.")) return;
    const { error: err } = await api.DELETE("/api/v1/admin/logs");
    if (err) setError(errorMessage(err));
    else {
      setMessage("Logs apagados.");
      void load();
    }
  }

  const summary = data?.summary;

  return (
    <div className="max-w-5xl space-y-6">
      <AdminHeader
        title="Logs"
        description="Avisos e erros da API e do worker, e o histórico de ações do painel."
        actions={
          <Button variant="secondary" onClick={() => void load()}>
            Atualizar
          </Button>
        }
      />
      {error ? <Alert>{error}</Alert> : null}

      <div className="flex gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
        <ShieldCheck aria-hidden className="mt-0.5 h-5 w-5 shrink-0" />
        <p>
          <strong>Protegido pela LGPD.</strong> Antes de gravar, o sistema remove nome, e-mail, senha, tokens, chaves
          de API, CPF, telefone, texto de redação e id de usuário. IP e conteúdo das requisições nunca são registrados.
          Os registros são apagados automaticamente após {data?.retention_days ?? "…"} dias e só administradores têm
          acesso.
        </p>
      </div>

      <div role="tablist" aria-label="Tipo de registro" className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5">
        {(
          [
            ["logs", "Avisos e erros"],
            ["events", "Ações do painel"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium ${tab === id ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "events" ? (
        <Section title="Ações do painel e eventos do sistema" description="Mudanças de configuração, convites, contas, pagamentos e limpezas. Últimos 200.">
          {!events ? (
            <Spinner />
          ) : events.length === 0 ? (
            <EmptyState>Nenhum evento ainda.</EmptyState>
          ) : (
            <ul className="divide-y divide-slate-100 text-sm">
              {events.map((ev) => (
                <li key={ev.id} className="flex flex-wrap gap-x-3 py-2">
                  <span className="w-32 shrink-0 text-xs tabular-nums text-slate-500">{dateTime(ev.created_at)}</span>
                  <span className="w-20 shrink-0 text-xs uppercase tracking-wide text-slate-400">{ev.kind}</span>
                  <span className="min-w-0 flex-1 text-slate-800">{ev.message}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>
      ) : (
        <>
          {summary ? (
            <div className="grid gap-3 sm:grid-cols-3">
              <StatCard label="Erros nas últimas 24 h" value={summary.errors_24h} tone={summary.errors_24h ? "error" : "default"} />
              <StatCard label="Avisos nas últimas 24 h" value={summary.warnings_24h} tone={summary.warnings_24h > 20 ? "warning" : "default"} />
              <StatCard label="Erros em 7 dias" value={summary.errors_7d} />
            </div>
          ) : null}

          {summary?.top_24h.length ? (
            <Section title="Erros mais frequentes (24 h)">
              <ul className="space-y-1 text-sm">
                {summary.top_24h.map((t, i) => (
                  <li key={i} className="flex flex-wrap items-baseline gap-x-3">
                    <span className="w-10 shrink-0 text-right font-semibold tabular-nums text-red-700">{t.count}×</span>
                    <span className="font-mono">{t.event}</span>
                    {t.error ? <span className="text-red-700">{t.error}</span> : null}
                    <span className="text-xs text-slate-500">último {relativeTime(t.last_at)}</span>
                  </li>
                ))}
              </ul>
            </Section>
          ) : null}

          <Section>
            <form
              className="mb-3 flex flex-wrap gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                setSearch(q.trim());
              }}
            >
              <select aria-label="Nível" className={selectCls} value={level} onChange={(e) => setLevel(e.target.value as Level)}>
                <option value="">Avisos e erros</option>
                <option value="ERROR">Só erros</option>
                <option value="WARNING">Só avisos</option>
              </select>
              <select aria-label="Origem" className={selectCls} value={source} onChange={(e) => setSource(e.target.value as Source)}>
                <option value="">API e worker</option>
                <option value="api">API</option>
                <option value="worker">Worker</option>
              </select>
              <label htmlFor="log-q" className="sr-only">
                Buscar
              </label>
              <input
                id="log-q"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Buscar evento, erro, rota ou id da requisição"
                className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-sm"
              />
              <Button type="submit" variant="secondary">
                Buscar
              </Button>
            </form>
            {!data ? (
              <Spinner />
            ) : items.length === 0 ? (
              <EmptyState>Nenhum aviso ou erro{search || level || source ? " com esses filtros" : ""}. Tudo certo por aqui.</EmptyState>
            ) : (
              <>
                <ul className="divide-y divide-slate-100">
                  {items.map((item) => (
                    <LogRow key={item.id} item={item} />
                  ))}
                </ul>
                {data.next_before_id ? (
                  <Button variant="secondary" className="mt-3" onClick={() => void more()}>
                    Carregar mais
                  </Button>
                ) : null}
              </>
            )}
          </Section>

          <Section title="Retenção">
            <form onSubmit={saveRetention} className="flex flex-wrap items-end gap-3">
              <div>
                <label htmlFor="retention" className="mb-1 block text-sm font-medium text-slate-700">
                  Apagar registros com mais de
                </label>
                <div className="flex items-center gap-2">
                  <input
                    id="retention"
                    type="number"
                    min={1}
                    max={180}
                    value={retention}
                    onChange={(e) => setRetention(e.target.value)}
                    className="w-24 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm"
                  />
                  <span className="text-sm text-slate-600">dias</span>
                </div>
              </div>
              <Button type="submit" variant="secondary">
                Salvar
              </Button>
              <Button type="button" variant="ghost" className="text-red-700" onClick={() => void clearAll()}>
                Apagar todos os logs
              </Button>
            </form>
            {message ? <p role="status" className="mt-2 text-sm text-emerald-700">{message}</p> : null}
            <p className="mt-2 text-xs text-slate-500">
              Guarde só o necessário para investigar problemas: 30 dias costuma bastar. O máximo é 180.
            </p>
          </Section>
        </>
      )}
    </div>
  );
}
