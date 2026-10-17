"use client";

import { useCallback, useEffect, useState } from "react";

import { AdminHeader, EmptyState, Section, StatusBadge } from "@/components/admin/kit";
import { Alert, Button, Spinner } from "@/components/ui";
import { type AdminUser, ROLE_LABEL, dateTime } from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";

const selectCls = "rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900 shadow-sm";
type Role = "student" | "teacher" | "admin";

export function UsersAdmin() {
  const [items, setItems] = useState<AdminUser[] | null>(null);
  const [total, setTotal] = useState(0);
  const [cursor, setCursor] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [role, setRole] = useState<Role | "">("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const query = useCallback(
    (next?: string | null) => ({
      q: search || undefined,
      role: role || undefined,
      limit: 50,
      cursor: next ?? undefined,
    }),
    [search, role],
  );

  useEffect(() => {
    api.GET("/api/v1/admin/users", { params: { query: query() } }).then(({ data, error: e }) => {
      if (!data) {
        setError(errorMessage(e));
        return;
      }
      setItems(data.items);
      setTotal(data.total);
      setCursor(data.next_cursor ?? null);
    });
  }, [query]);

  async function loadMore() {
    if (!cursor) return;
    const { data } = await api.GET("/api/v1/admin/users", { params: { query: query(cursor) } });
    if (data) {
      setItems((prev) => [...(prev ?? []), ...data.items]);
      setCursor(data.next_cursor ?? null);
    }
  }

  async function patch(
    user: AdminUser,
    body: { role?: "student" | "teacher"; disabled?: boolean; free_access?: boolean },
  ) {
    if (body.disabled && !window.confirm(`Desativar a conta de ${user.name}? A pessoa sai na hora e não consegue mais entrar.`)) {
      return;
    }
    setBusy(user.id);
    setError(null);
    const { data, error: e } = await api.PATCH("/api/v1/admin/users/{user_id}", {
      params: { path: { user_id: user.id } },
      body,
    });
    setBusy(null);
    if (data) setItems((prev) => prev?.map((u) => (u.id === data.id ? data : u)) ?? prev);
    else setError(errorMessage(e));
  }

  return (
    <div className="max-w-5xl space-y-6">
      <AdminHeader
        title="Usuários"
        description="Contas da plataforma. Aqui você troca o tipo de conta e desativa quem não deve mais entrar. Redações e respostas dos alunos não aparecem no painel."
      />
      {error ? <Alert>{error}</Alert> : null}

      <Section>
        <form
          className="mb-4 flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setSearch(q.trim());
          }}
        >
          <label htmlFor="user-q" className="sr-only">
            Buscar por nome ou e-mail
          </label>
          <input
            id="user-q"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por nome ou e-mail"
            className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-sm"
          />
          <select aria-label="Tipo de conta" className={selectCls} value={role} onChange={(e) => setRole(e.target.value as Role | "")}>
            <option value="">Todos os tipos</option>
            <option value="student">Alunos</option>
            <option value="teacher">Professores</option>
            <option value="admin">Admins</option>
          </select>
          <Button type="submit" variant="secondary">
            Buscar
          </Button>
        </form>

        {!items ? (
          <Spinner />
        ) : items.length === 0 ? (
          <EmptyState>Nenhuma conta encontrada.</EmptyState>
        ) : (
          <>
            <p className="mb-2 text-sm text-slate-500">{total} conta(s)</p>
            <ul className="divide-y divide-slate-100">
              {items.map((u) => (
                <li key={u.id} className="flex flex-wrap items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-900">
                      {u.name}
                      {u.disabled_at ? <StatusBadge level="error">Desativada</StatusBadge> : null}
                      {!u.email_verified_at ? <span className="text-xs font-normal text-amber-700">e-mail não confirmado</span> : null}
                    </p>
                    <p className="truncate text-xs text-slate-500">
                      {u.email} · desde {dateTime(u.created_at)}
                      {u.role === "student"
                        ? u.free_access
                          ? " · acesso livre"
                          : u.paid_until && new Date(u.paid_until) > new Date()
                            ? ` · assinatura até ${dateTime(u.paid_until)}`
                            : " · sem assinatura"
                        : ""}
                    </p>
                  </div>
                  {u.role === "admin" ? (
                    <span className="text-sm text-slate-500">{ROLE_LABEL.admin}</span>
                  ) : (
                    <div className="flex items-center gap-2">
                      <select
                        aria-label={`Tipo de conta de ${u.name}`}
                        className={selectCls}
                        value={u.role}
                        disabled={busy === u.id}
                        onChange={(e) => void patch(u, { role: e.target.value as "student" | "teacher" })}
                      >
                        <option value="student">Aluno</option>
                        <option value="teacher">Professor</option>
                      </select>
                      {u.role === "student" ? (
                        <label className="flex items-center gap-1.5 text-sm text-slate-700" title="Usa a plataforma sem assinatura">
                          <input
                            type="checkbox"
                            checked={u.free_access}
                            disabled={busy === u.id}
                            onChange={(e) => void patch(u, { free_access: e.target.checked })}
                          />
                          Acesso livre
                        </label>
                      ) : null}
                      <Button
                        variant={u.disabled_at ? "secondary" : "ghost"}
                        disabled={busy === u.id}
                        onClick={() => void patch(u, { disabled: !u.disabled_at })}
                      >
                        {u.disabled_at ? "Reativar" : "Desativar"}
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
            {cursor ? (
              <div className="mt-4">
                <Button variant="secondary" onClick={() => void loadMore()}>
                  Carregar mais
                </Button>
              </div>
            ) : null}
          </>
        )}
      </Section>
    </div>
  );
}
