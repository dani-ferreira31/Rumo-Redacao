"use client";

import { Heart } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { NAV_ITEMS } from "@/components/nav-items";
import { Alert } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ROUTE_FEATURES, isEnabled, useFeatures } from "@/lib/features";
import { UNPAID_ALLOWED } from "@/lib/payments";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const { user, logout } = useAuth();
  const features = useFeatures();
  const isAdmin = user?.role === "admin";
  const route = ROUTE_FEATURES.find((r) => pathname === r.prefix || pathname.startsWith(`${r.prefix}/`));
  const routeOff = route ? !isEnabled(features, route.features) : false;
  const router = useRouter();
  const [donations, setDonations] = useState(false);
  useEffect(() => {
    api.GET("/api/v1/billing").then(({ data }) => setDonations(Boolean(data?.donations_enabled)));
  }, []);
  // sem assinatura em dia, só as páginas de assinatura, doação e perfil
  const unpaid = user?.access_active === false;
  const blocked = unpaid && !UNPAID_ALLOWED.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  useEffect(() => {
    if (blocked) router.replace("/assinatura");
  }, [blocked, router]);

  const links = NAV_ITEMS.filter((item) => !unpaid && (isAdmin || isEnabled(features, item.features))).map((item) => {
    const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
    return (
      <Link
        key={item.href}
        href={item.href}
        onClick={() => setOpen(false)}
        aria-current={active ? "page" : undefined}
        className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
          active ? "bg-indigo-600 text-white" : "text-slate-700 hover:bg-slate-200"
        }`}
      >
        {item.label}
      </Link>
    );
  });

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="border-b border-slate-200 bg-white md:w-60 md:shrink-0 md:border-b-0 md:border-r">
        <div className="flex items-center justify-between px-4 py-4">
          <Link href="/painel" className="text-lg font-bold text-indigo-700">
            Rumo1000
          </Link>
          <button
            type="button"
            className="rounded-md px-2 py-1 text-sm text-slate-700 hover:bg-slate-100 md:hidden"
            aria-expanded={open}
            aria-controls="menu-principal"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? "Fechar" : "Menu"}
          </button>
        </div>
        <nav
          id="menu-principal"
          className={`${open ? "flex" : "hidden"} flex-col gap-1 px-3 pb-4 md:flex`}
        >
          {links}
          <div className="mt-4 border-t border-slate-200 pt-4">
            <p className="truncate px-3 text-xs text-slate-500" title={user?.email}>
              {user?.name}
            </p>
            {user?.role === "teacher" || user?.role === "admin" ? (
              <Link
                href="/professor"
                onClick={() => setOpen(false)}
                className={`mt-1 block rounded-md px-3 py-2 text-sm font-medium ${
                  pathname.startsWith("/professor") ? "bg-indigo-600 text-white" : "text-slate-700 hover:bg-slate-200"
                }`}
              >
                Professor
              </Link>
            ) : null}
            {user?.role === "admin" ? (
              <Link
                href="/admin"
                onClick={() => setOpen(false)}
                className={`mt-1 block rounded-md px-3 py-2 text-sm font-medium ${
                  pathname.startsWith("/admin") ? "bg-indigo-600 text-white" : "text-slate-700 hover:bg-slate-200"
                }`}
              >
                Admin
              </Link>
            ) : null}
            {user && !user.free_access && user.role === "student" ? (
              <Link
                href="/assinatura"
                onClick={() => setOpen(false)}
                className={`mt-1 block rounded-md px-3 py-2 text-sm font-medium ${
                  pathname.startsWith("/assinatura") ? "bg-indigo-600 text-white" : "text-slate-700 hover:bg-slate-200"
                }`}
              >
                Assinatura
              </Link>
            ) : null}
            {donations ? (
            <Link
              href="/apoiar"
              onClick={() => setOpen(false)}
              className={`mt-1 flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium ${
                pathname.startsWith("/apoiar") ? "bg-indigo-600 text-white" : "text-rose-700 hover:bg-rose-50"
              }`}
            >
              <Heart aria-hidden className="h-4 w-4" />
              Apoiar o projeto
            </Link>
            ) : null}
            <Link
              href="/perfil"
              onClick={() => setOpen(false)}
              aria-current={pathname === "/perfil" ? "page" : undefined}
              className={`mt-1 block rounded-md px-3 py-2 text-sm font-medium ${
                pathname === "/perfil" ? "bg-indigo-600 text-white" : "text-slate-700 hover:bg-slate-200"
              }`}
            >
              Perfil
            </Link>
            <button
              type="button"
              onClick={() => void logout()}
              className="block w-full rounded-md px-3 py-2 text-left text-sm font-medium text-slate-700 hover:bg-slate-200"
            >
              Sair
            </button>
          </div>
        </nav>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 md:px-8">
        {blocked ? null : routeOff && !isAdmin ? (
          <Alert kind="info">{route?.label} está temporariamente indisponível. Volte mais tarde.</Alert>
        ) : (
          <>
            {routeOff ? (
              <div className="mb-4">
                <Alert kind="warning">Este módulo está desligado para os alunos (você vê porque é admin).</Alert>
              </div>
            ) : null}
            {children}
          </>
        )}
      </main>
    </div>
  );
}
