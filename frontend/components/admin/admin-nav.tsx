"use client";

import {
  Activity,
  CircleDollarSign,
  Landmark,
  LayoutDashboard,
  ListChecks,
  PenLine,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const GROUPS = [
  {
    label: "Gestão",
    items: [
      { href: "/admin", label: "Visão geral", icon: LayoutDashboard, exact: true },
      { href: "/admin/ia", label: "Inteligência artificial", icon: Sparkles },
      { href: "/admin/custos", label: "Custos", icon: CircleDollarSign },
      { href: "/admin/sistema", label: "Sistema", icon: Activity },
      { href: "/admin/modulos", label: "Módulos e limites", icon: SlidersHorizontal },
    ],
  },
  {
    label: "Conteúdo",
    items: [
      { href: "/admin/questoes", label: "Questões ENEM", icon: ListChecks },
      { href: "/admin/concursos", label: "Concursos", icon: Landmark },
      { href: "/admin/temas", label: "Temas de redação", icon: PenLine },
    ],
  },
];

export function AdminNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Administração" className="-mx-4 overflow-x-auto px-4 md:mx-0 md:overflow-visible md:px-0">
      <div className="flex gap-1 md:flex-col md:gap-5">
        {GROUPS.map((group) => (
          <div key={group.label} className="flex gap-1 md:flex-col">
            <p className="hidden px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-slate-400 md:block">
              {group.label}
            </p>
            {group.items.map(({ href, label, icon: Icon, ...rest }) => {
              const exact = "exact" in rest && rest.exact;
              const active = exact ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`flex shrink-0 items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    active ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`}
                >
                  <Icon aria-hidden className="h-4 w-4" />
                  {label}
                </Link>
              );
            })}
          </div>
        ))}
      </div>
    </nav>
  );
}
