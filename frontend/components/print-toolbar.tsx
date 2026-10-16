"use client";

import { Printer } from "lucide-react";

import { Button } from "@/components/ui";

/** Barra que some na impressão. O PDF sai pelo "Salvar como PDF" do navegador. */
export function PrintToolbar({ children }: { children?: React.ReactNode }) {
  return (
    <div className="sticky top-0 z-10 border-b border-slate-200 bg-slate-50 px-4 py-3 print:hidden">
      <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-3">
        <Button onClick={() => window.print()}>
          <Printer aria-hidden className="mr-2 h-4 w-4" />
          Imprimir / salvar PDF
        </Button>
        <p className="text-sm text-slate-600">Na janela de impressão, escolha “Salvar como PDF” como destino.</p>
        {children}
      </div>
    </div>
  );
}
